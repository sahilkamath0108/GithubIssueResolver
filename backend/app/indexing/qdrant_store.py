from __future__ import annotations

import logging
import uuid

from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)

from app.core.settings import Settings, settings as default_settings

logger = logging.getLogger(__name__)


class QdrantVectorStore:
    """Stores code chunk vectors + metadata in Qdrant."""

    def __init__(self, settings: Settings | None = None):
        self._settings = settings or default_settings
        self._client = QdrantClient(
            url=self._settings.QDRANT_URL,
            api_key=(self._settings.QDRANT_API_KEY or None),
            timeout=self._settings.QDRANT_TIMEOUT,
        )
        self._collection = self._settings.QDRANT_COLLECTION
        self._vector_size: int | None = self._settings.effective_embedding_dim
        self._ensured = False

    def close(self) -> None:
        self._client.close()

    def _raise_qdrant_hint(self, exc: UnexpectedResponse) -> None:
        status = getattr(exc, "status_code", None)
        hint = (
            "Qdrant returned 403 Forbidden. This usually means your Qdrant Cloud API key is missing/invalid "
            "(set QDRANT_API_KEY in `.env`) or your QDRANT_URL is incorrect (use the HTTPS cluster URL)."
            if status == 403
            else f"Qdrant request failed with status {status}."
        )
        raise RuntimeError(hint) from exc

    def _read_existing_vector_size(self) -> int | None:
        try:
            if not self._client.collection_exists(self._collection):
                return None
        except UnexpectedResponse as exc:
            self._raise_qdrant_hint(exc)
        info = self._client.get_collection(self._collection)
        params = info.config.params.vectors
        if params is None:
            return None
        if isinstance(params, dict):
            first = next(iter(params.values()), None)
            return getattr(first, "size", None) if first is not None else None
        return getattr(params, "size", None)

    def ensure_payload_indexes(self) -> None:
        """
        Ensure payload indexes exist for filter-heavy keys.

        Some managed Qdrant deployments enforce indexed filtering and will return 400
        if you filter on a field without an index.
        """
        try:
            if not self._client.collection_exists(self._collection):
                return
        except UnexpectedResponse as exc:
            self._raise_qdrant_hint(exc)

        for field in ("repo", "path"):
            try:
                self._client.create_payload_index(
                    collection_name=self._collection,
                    field_name=field,
                    field_schema=PayloadSchemaType.KEYWORD,
                )
            except UnexpectedResponse as exc:
                # If the server rejects index creation, surface a helpful message.
                self._raise_qdrant_hint(exc)
            except Exception:
                # Index likely already exists (or server doesn't require it) — ignore.
                continue

    def ensure_collection(self, vector_size: int) -> None:
        if self._ensured and self._vector_size == vector_size:
            return
        existing_dim = self._read_existing_vector_size()
        if existing_dim is None:
            logger.info(
                "Creating Qdrant collection",
                extra={"collection": self._collection, "size": vector_size},
            )
            self._client.create_collection(
                collection_name=self._collection,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )
            # Create payload indexes for strict / managed deployments
            self.ensure_payload_indexes()
        elif existing_dim != vector_size:
            raise RuntimeError(
                f"Qdrant collection {self._collection!r} uses vector size {existing_dim}, "
                f"but current embeddings have size {vector_size}."
            )
        else:
            self.ensure_payload_indexes()
        self._vector_size = vector_size
        self._ensured = True

    def search_repo_chunks(
        self,
        repo_full_name: str,
        vector: list[float],
        *,
        top_k: int,
    ) -> list[dict]:
        """Vector search filtered by repo; returns {path, chunk} dicts."""
        self.ensure_payload_indexes()
        try:
            response = self._client.query_points(
                collection_name=self._collection,
                query=vector,
                limit=top_k,
                query_filter=Filter(
                    must=[FieldCondition(key="repo", match=MatchValue(value=repo_full_name))]
                ),
                with_payload=True,
            )
        except UnexpectedResponse as exc:
            if getattr(exc, "status_code", None) == 400:
                raise RuntimeError(
                    "Qdrant rejected filtered search (400). Payload indexes for `repo` and `path` "
                    f"could not be used on collection {self._collection!r}. "
                    "Re-index the repo or recreate the collection."
                ) from exc
            self._raise_qdrant_hint(exc)
            raise

        out: list[dict] = []
        for point in response.points:
            payload = point.payload or {}
            path = payload.get("path")
            text = payload.get("text")
            if isinstance(path, str) and isinstance(text, str):
                item: dict = {"path": path, "chunk": text}
                if point.score is not None:
                    item["score"] = float(point.score)
                out.append(item)

        logger.info(
            "Qdrant search repo=%s raw_hits=%s usable_chunks=%s top_k=%s",
            repo_full_name,
            len(response.points),
            len(out),
            top_k,
        )
        return out

    def count_repo_points(self, repo_full_name: str) -> int:
        """How many vectors exist for this repo (0 if collection missing)."""
        try:
            if not self._client.collection_exists(self._collection):
                return 0
        except UnexpectedResponse as exc:
            self._raise_qdrant_hint(exc)
        self.ensure_payload_indexes()
        result = self._client.count(
            collection_name=self._collection,
            count_filter=Filter(
                must=[FieldCondition(key="repo", match=MatchValue(value=repo_full_name))]
            ),
            exact=True,
        )
        return int(result.count)

    def delete_repo(self, repo_full_name: str) -> None:
        try:
            if not self._client.collection_exists(self._collection):
                return
        except UnexpectedResponse as exc:
            self._raise_qdrant_hint(exc)
        self.ensure_payload_indexes()
        self._client.delete(
            collection_name=self._collection,
            points_selector=Filter(
                must=[FieldCondition(key="repo", match=MatchValue(value=repo_full_name))]
            ),
        )
        logger.info("Deleted vectors for repo", extra={"repo": repo_full_name})

    def delete_file(self, repo_full_name: str, path: str) -> None:
        try:
            if not self._client.collection_exists(self._collection):
                return
        except UnexpectedResponse as exc:
            self._raise_qdrant_hint(exc)
        self.ensure_payload_indexes()
        self._client.delete(
            collection_name=self._collection,
            points_selector=Filter(
                must=[
                    FieldCondition(key="repo", match=MatchValue(value=repo_full_name)),
                    FieldCondition(key="path", match=MatchValue(value=path)),
                ]
            ),
        )
        logger.debug("Deleted vectors for file", extra={"repo": repo_full_name, "path": path})

    def upsert_chunks(
        self,
        *,
        repo_full_name: str,
        commit_sha: str,
        path: str,
        blob_sha: str,
        vectors: list[tuple[str, list[float], str]],
    ) -> None:
        """
        vectors: list of (chunk_id, embedding, chunk_text)
        """
        if not vectors:
            return
        dim = len(vectors[0][1])
        self.ensure_collection(dim)

        batch_size = max(1, self._settings.INDEX_UPSERT_BATCH_SIZE)
        points: list[PointStruct] = []
        for chunk_id, vector, text in vectors:
            point_id = str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"{repo_full_name}:{path}:{chunk_id}:{blob_sha}",
                )
            )
            points.append(
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "repo": repo_full_name,
                        "path": path,
                        "chunk_id": chunk_id,
                        "blob_sha": blob_sha,
                        "commit_sha": commit_sha,
                        "text": text,
                    },
                )
            )

        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            self._client.upsert(collection_name=self._collection, points=batch)
        logger.debug(
            "Upserted chunk vectors",
            extra={"repo": repo_full_name, "path": path, "count": len(points)},
        )
