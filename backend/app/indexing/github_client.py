from __future__ import annotations

import base64
import logging

from github import Github
from github.GithubException import GithubException
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.core.settings import Settings, settings as default_settings
from app.indexing.schemas import TreeBlobFile

logger = logging.getLogger(__name__)


def _github_retryable(exc: BaseException) -> bool:
    if isinstance(exc, GithubException):
        return exc.status in (403, 429, 500, 502, 503)
    return False


class GitHubRepoClient:
    """
    GitHub REST access via PyGithub with retries for rate limits and transient errors.
    Lists repository trees and fetches blob contents without cloning.
    """

    def __init__(self, settings: Settings | None = None, access_token: str | None = None):
        self._settings = settings or default_settings
        token = access_token or self._settings.GITHUB_TOKEN
        if not token:
            raise RuntimeError("GitHub access token is required for indexing.")
        self._gh = Github(
            login_or_token=token,
            per_page=100,
        )

    @staticmethod
    def parse_repo(repo: str) -> tuple[str, str]:
        repo = repo.strip().strip("/")
        if "/" not in repo or repo.count("/") != 1:
            raise ValueError('repo must be "owner/name" with exactly one slash')
        owner, name = repo.split("/", 1)
        if not owner or not name:
            raise ValueError("owner and name must be non-empty")
        return owner, name

    def get_default_branch_and_tip(self, repo_full_name: str) -> tuple[str, str, str]:
        """
        Returns (default_branch_name, commit_sha, root_tree_sha) for the repo tip.
        """
        owner, name = self.parse_repo(repo_full_name)
        gh_repo = self._gh.get_repo(f"{owner}/{name}", lazy=False)
        branch = gh_repo.default_branch
        # Some repos (or permission configurations) can 404 on get_git_ref even if the branch exists.
        # Fall back to the branches API which is commonly more reliable.
        try:
            ref = gh_repo.get_git_ref(f"heads/{branch}")
            commit_sha = ref.object.sha
        except GithubException as exc:
            if exc.status == 404:
                b = gh_repo.get_branch(branch)
                commit_sha = b.commit.sha
            else:
                raise
        commit = self._get_git_commit_retry(gh_repo, commit_sha)
        tree_sha = commit.tree.sha
        logger.info(
            "Resolved repo tip",
            extra={"repo": repo_full_name, "branch": branch, "commit": commit_sha},
        )
        return branch, commit_sha, tree_sha

    def get_commit_tree_sha(self, repo_full_name: str, commit_sha: str) -> str:
        """Returns the root tree SHA for an arbitrary commit."""
        owner, name = self.parse_repo(repo_full_name)
        gh_repo = self._gh.get_repo(f"{owner}/{name}", lazy=False)
        commit = self._get_git_commit_retry(gh_repo, commit_sha)
        return commit.tree.sha

    @retry(
        retry=retry_if_exception(_github_retryable),
        wait=wait_exponential(
            multiplier=1,
            min=default_settings.GITHUB_API_RETRY_MIN_WAIT,
            max=default_settings.GITHUB_API_RETRY_MAX_WAIT,
        ),
        stop=stop_after_attempt(default_settings.GITHUB_API_MAX_RETRIES),
        reraise=True,
    )
    def _get_git_commit_retry(self, gh_repo, commit_sha: str):
        return gh_repo.get_git_commit(commit_sha)

    def list_tree_blobs(
        self,
        repo_full_name: str,
        root_tree_sha: str,
        allowed_suffixes: tuple[str, ...],
        max_file_bytes: int,
    ) -> list[TreeBlobFile]:
        """
        Walk the git tree and return blob files filtered by extension and size.
        Uses recursive tree API when possible; falls back to manual traversal if truncated.
        """
        owner, name = self.parse_repo(repo_full_name)
        gh_repo = self._gh.get_repo(f"{owner}/{name}", lazy=False)

        tree = self._get_git_tree_retry(gh_repo, root_tree_sha, recursive=True)
        raw = getattr(tree, "raw_data", None) or getattr(tree, "_rawData", {}) or {}
        truncated = bool(raw.get("truncated", False)) if isinstance(raw, dict) else False
        entries = list(tree.tree)
        if truncated:
            logger.warning(
                "Recursive tree response truncated; falling back to iterative tree walk",
                extra={"repo": repo_full_name, "tree": root_tree_sha},
            )
            entries = self._walk_tree_iterative(gh_repo, root_tree_sha)

        out: list[TreeBlobFile] = []
        for el in entries:
            if el.type != "blob" or not el.path:
                continue
            lower = el.path.lower()
            if not any(lower.endswith(suf) for suf in allowed_suffixes):
                continue
            size = int(el.size or 0)
            if size > max_file_bytes:
                logger.debug("Skipping oversized blob", extra={"path": el.path, "size": size})
                continue
            out.append(TreeBlobFile(path=el.path, blob_sha=el.sha, size=size))
        logger.info(
            "Collected tree blobs",
            extra={"repo": repo_full_name, "count": len(out)},
        )
        return out

    def _walk_tree_iterative(self, gh_repo, root_tree_sha: str) -> list:
        """Breadth-first walk of git trees when recursive=1 is truncated."""
        collected: list = []
        stack: list[str] = [root_tree_sha]
        while stack:
            sha = stack.pop()
            tree = self._get_git_tree_retry(gh_repo, sha, recursive=False)
            for el in tree.tree:
                if el.type == "tree":
                    stack.append(el.sha)
                elif el.type == "blob":
                    collected.append(el)
        return collected

    @retry(
        retry=retry_if_exception(_github_retryable),
        wait=wait_exponential(
            multiplier=1,
            min=default_settings.GITHUB_API_RETRY_MIN_WAIT,
            max=default_settings.GITHUB_API_RETRY_MAX_WAIT,
        ),
        stop=stop_after_attempt(default_settings.GITHUB_API_MAX_RETRIES),
        reraise=True,
    )
    def _get_git_tree_retry(self, gh_repo, tree_sha: str, *, recursive: bool):
        return gh_repo.get_git_tree(tree_sha, recursive=recursive)

    @retry(
        retry=retry_if_exception(_github_retryable),
        wait=wait_exponential(
            multiplier=1,
            min=default_settings.GITHUB_API_RETRY_MIN_WAIT,
            max=default_settings.GITHUB_API_RETRY_MAX_WAIT,
        ),
        stop=stop_after_attempt(default_settings.GITHUB_API_MAX_RETRIES),
        reraise=True,
    )
    def get_blob_text(self, repo_full_name: str, blob_sha: str) -> str:
        owner, name = self.parse_repo(repo_full_name)
        gh_repo = self._gh.get_repo(f"{owner}/{name}", lazy=False)
        blob = gh_repo.get_git_blob(blob_sha)
        raw = base64.b64decode(blob.content)
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("utf-8", errors="ignore")
            logger.warning(
                "Blob decoded with replacement characters",
                extra={"repo": repo_full_name, "blob": blob_sha},
            )
            return text

    def path_blob_map(
        self,
        repo_full_name: str,
        root_tree_sha: str,
        allowed_suffixes: tuple[str, ...],
        max_file_bytes: int,
    ) -> dict[str, str]:
        """Convenience map path -> blob_sha for incremental diffing."""
        files = self.list_tree_blobs(repo_full_name, root_tree_sha, allowed_suffixes, max_file_bytes)
        return {f.path: f.blob_sha for f in files}
