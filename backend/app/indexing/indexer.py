from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from sqlalchemy.orm import Session

from app.core.settings import Settings, settings as default_settings
from app.indexing.chunker import CodeChunker
from app.indexing.github_client import GitHubRepoClient
from app.indexing.ollama_embeddings import OllamaEmbeddingClient
from app.indexing.qdrant_store import QdrantVectorStore
from app.indexing.schemas import IndexRunResult, TreeBlobFile
from app.models.repo_index_state import RepoIndexState

logger = logging.getLogger(__name__)


def _fetch_blob_text(repo: str, blob_sha: str, settings: Settings, access_token: str | None = None) -> str:
    """Worker-safe: each call uses its own GitHub client (PyGithub is not documented as thread-safe)."""
    return GitHubRepoClient(settings, access_token=access_token).get_blob_text(repo, blob_sha)


class RepoIndexer:
    """
    GitHub API → chunk → Ollama → Qdrant indexing.

    **Single entrypoint for callers (issues, jobs, API):** :meth:`sync_repo` compares the
    default-branch **tip commit** from GitHub with the commit stored in ``repo_index_state``
    (the commit the vector index was last aligned to). It then runs a **full** index,
    **incremental** blob-level diff, or **skips** if nothing changed.

    ``RepoIndexState.commit_sha`` is the source of truth for "indexed commit"; chunk payloads
    in Qdrant also carry ``commit_sha`` for traceability.
    """

    def __init__(
        self,
        db: Session,
        *,
        settings: Settings | None = None,
        github: GitHubRepoClient | None = None,
        chunker: CodeChunker | None = None,
        embedder: OllamaEmbeddingClient | None = None,
        vector_store: QdrantVectorStore | None = None,
    ):
        self._db = db
        self._settings = settings or default_settings
        self._github = github or GitHubRepoClient(self._settings)
        self._chunker = chunker or CodeChunker(self._settings)
        self._embedder = embedder or OllamaEmbeddingClient(self._settings)
        self._qdrant = vector_store or QdrantVectorStore(self._settings)

    def close(self) -> None:
        self._embedder.close()
        self._qdrant.close()

    def count_vectors(self, repo: str) -> int:
        return self._qdrant.count_repo_points(repo)

    def _load_state(self, repo_full_name: str) -> RepoIndexState | None:
        return (
            self._db.query(RepoIndexState)
            .filter(RepoIndexState.repo_full_name == repo_full_name)
            .one_or_none()
        )

    def _persist_state(self, repo_full_name: str, commit_sha: str) -> None:
        row = self._load_state(repo_full_name)
        if row is None:
            row = RepoIndexState(repo_full_name=repo_full_name, commit_sha=commit_sha)
            self._db.add(row)
        else:
            row.commit_sha = commit_sha
        self._db.commit()
        logger.info("Updated repo index state", extra={"repo": repo_full_name, "commit": commit_sha})

    def sync_repo(self, repo: str, *, force_full: bool = False) -> IndexRunResult:
        """
        Compare latest GitHub default-branch commit to the stored indexed commit, then:

        - ``force_full`` → wipe repo vectors in Qdrant and reindex all files.
        - No DB row yet → full index (first time).
        - Stored commit == latest → skip.
        - DB says indexed but Qdrant has no points for this repo → full index (heal drift).
        - Otherwise → incremental diff by **path + blob SHA** (add/change/delete), then
          update stored commit to latest.

        Call this when an issue arrives (or on a schedule); do not split callers across
        separate "full" vs "incremental" APIs.
        """
        repo = repo.strip()
        GitHubRepoClient.parse_repo(repo)

        _, latest_sha, latest_tree_sha = self._github.get_default_branch_and_tip(repo)
        state = self._load_state(repo)

        if force_full:
            logger.info("Force full reindex requested", extra={"repo": repo})
            return self._execute_full_index(repo, latest_sha, latest_tree_sha)

        if state is None:
            logger.info("No index state; running first-time full index", extra={"repo": repo})
            return self._execute_full_index(repo, latest_sha, latest_tree_sha)

        if state.commit_sha == latest_sha:
            logger.info("Indexed commit matches GitHub tip; skipping", extra={"repo": repo, "commit": latest_sha})
            return IndexRunResult(
                repo=repo,
                mode="skipped",
                commit_sha=latest_sha,
                message="Stored commit matches latest default-branch commit",
            )

        vec_count = self._qdrant.count_repo_points(repo)
        if vec_count == 0:
            logger.warning(
                "Index state exists but Qdrant has no vectors for repo; rebuilding full index",
                extra={"repo": repo, "stored_commit": state.commit_sha},
            )
            return self._execute_full_index(repo, latest_sha, latest_tree_sha)

        return self._execute_incremental_index(repo, state, latest_sha, latest_tree_sha)

    def index_full_repo(self, repo: str) -> IndexRunResult:
        """Force a full reindex. Prefer :meth:`sync_repo` with ``force_full=True`` in new code."""
        return self.sync_repo(repo, force_full=True)

    def update_incremental(self, repo: str) -> IndexRunResult:
        """Deprecated for HTTP use; calls :meth:`sync_repo` (full/skip/incremental as needed)."""
        return self.sync_repo(repo, force_full=False)

    def _execute_full_index(self, repo: str, commit_sha: str, tree_sha: str) -> IndexRunResult:
        blobs = self._github.list_tree_blobs(
            repo,
            tree_sha,
            self._settings.index_file_extensions,
            self._settings.INDEX_MAX_FILE_BYTES,
        )

        logger.info("Starting full index", extra={"repo": repo, "files": len(blobs), "commit": commit_sha})
        # Some Qdrant deployments require indexes for filtered deletes/counts.
        self._qdrant.ensure_payload_indexes()
        self._qdrant.delete_repo(repo)

        chunks_written = 0
        files_indexed = 0

        workers = max(1, self._settings.INDEX_BLOB_FETCH_WORKERS)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            future_map = {
                pool.submit(_fetch_blob_text, repo, b.blob_sha, self._settings): b
                for b in blobs
            }
            for fut in as_completed(future_map):
                meta: TreeBlobFile = future_map[fut]
                try:
                    text = fut.result()
                except Exception as exc:  # noqa: BLE001
                    logger.error(
                        "Failed to fetch blob; skipping file",
                        extra={"repo": repo, "path": meta.path, "error": str(exc)},
                    )
                    continue
                n = self._index_file_text(repo, commit_sha, meta.path, meta.blob_sha, text)
                if n:
                    files_indexed += 1
                    chunks_written += n

        self._persist_state(repo, commit_sha)
        return IndexRunResult(
            repo=repo,
            mode="full",
            commit_sha=commit_sha,
            files_indexed=files_indexed,
            chunks_written=chunks_written,
            message="Full index completed",
        )

    def _execute_incremental_index(
        self,
        repo: str,
        state: RepoIndexState,
        new_sha: str,
        new_tree_sha: str,
    ) -> IndexRunResult:
        new_map = self._github.path_blob_map(
            repo,
            new_tree_sha,
            self._settings.index_file_extensions,
            self._settings.INDEX_MAX_FILE_BYTES,
        )
        old_tree_sha = self._github.get_commit_tree_sha(repo, state.commit_sha)
        old_map = self._github.path_blob_map(
            repo,
            old_tree_sha,
            self._settings.index_file_extensions,
            self._settings.INDEX_MAX_FILE_BYTES,
        )

        deleted_paths = set(old_map) - set(new_map)
        for path in deleted_paths:
            self._qdrant.delete_file(repo, path)

        targets: list[tuple[str, str]] = []
        for path, blob_sha in new_map.items():
            if path not in old_map or old_map[path] != blob_sha:
                targets.append((path, blob_sha))

        unchanged = len(new_map) - len(targets)
        chunks_written = 0
        files_indexed = 0

        workers = max(1, self._settings.INDEX_BLOB_FETCH_WORKERS)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            future_map = {
                pool.submit(_fetch_blob_text, repo, blob_sha, self._settings): (path, blob_sha)
                for path, blob_sha in targets
            }
            for fut in as_completed(future_map):
                path, blob_sha = future_map[fut]
                try:
                    text = fut.result()
                except Exception as exc:  # noqa: BLE001
                    logger.error(
                        "Failed to fetch blob during incremental update",
                        extra={"repo": repo, "path": path, "error": str(exc)},
                    )
                    continue
                self._qdrant.delete_file(repo, path)
                n = self._index_file_text(repo, new_sha, path, blob_sha, text)
                if n:
                    files_indexed += 1
                    chunks_written += n

        self._persist_state(repo, new_sha)
        return IndexRunResult(
            repo=repo,
            mode="incremental",
            commit_sha=new_sha,
            files_indexed=files_indexed,
            chunks_written=chunks_written,
            files_deleted=len(deleted_paths),
            files_skipped_unchanged=unchanged,
            message="Incremental index completed (blob SHA diff vs stored commit)",
        )

    def _index_file_text(self, repo: str, commit_sha: str, path: str, blob_sha: str, text: str) -> int:
        chunks = self._chunker.chunk_file(path, text)
        if not chunks:
            return 0

        tuples: list[tuple[str, list[float], str]] = []
        for chunk in chunks:
            try:
                vec = self._embedder.embed_text(chunk.text)
                tuples.append((chunk.chunk_id, vec, chunk.text))
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Skipping chunk after embedding failure",
                    extra={"repo": repo, "path": path, "chunk_id": chunk.chunk_id, "error": str(exc)},
                )

        if not tuples:
            return 0

        self._qdrant.upsert_chunks(
            repo_full_name=repo,
            commit_sha=commit_sha,
            path=path,
            blob_sha=blob_sha,
            vectors=tuples,
        )
        return len(tuples)
