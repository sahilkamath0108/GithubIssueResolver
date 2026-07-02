import json
import hashlib
import redis as redis_lib
from typing import Optional
from github import Github, GithubException
from app.core.settings import settings

_github = Github(settings.GITHUB_TOKEN)
_cache = redis_lib.Redis.from_url(settings.REDIS_URL, decode_responses=True)
_REPO_CACHE_TTL = 60 * 60 * 6  # 6 hours


def _parse_repo(repo_url: str):
    """Extract owner/repo from GitHub URL."""
    parts = repo_url.rstrip("/").split("/")
    return _github.get_repo(f"{parts[-2]}/{parts[-1]}")

def repo_full_name(repo_url: str) -> str:
    """
    Normalize a GitHub repository URL to "owner/name".
    Example: "https://github.com/owner/name" -> "owner/name"
    """
    parts = repo_url.rstrip("/").split("/")
    return f"{parts[-2]}/{parts[-1]}"


def repo_full_name_from_issue_url(issue_url: str) -> str:
    """
    Extract owner/name from a GitHub issue URL.
    Example: https://github.com/owner/repo/issues/1 -> owner/repo
    """
    parts = issue_url.rstrip("/").split("/")
    if len(parts) < 5 or parts[-2] != "issues":
        raise ValueError(f"Invalid GitHub issue URL: {issue_url}")
    return f"{parts[-4]}/{parts[-3]}"


def assert_issue_matches_repo(issue_url: str, repo_url: str) -> None:
    """Raise ValueError if issue and repo URLs refer to different repositories."""
    issue_repo = repo_full_name_from_issue_url(issue_url)
    target_repo = repo_full_name(repo_url)
    if issue_repo.lower() != target_repo.lower():
        raise ValueError(
            f"Issue repo ({issue_repo}) does not match repo_url ({target_repo}). "
            "Use the same repository for both URLs."
        )


def get_file_contents(repo_url: str, paths: list[str]) -> list[dict]:
    """Fetch full file contents for specific paths from the repo default branch."""
    if not paths:
        return []
    repo = _parse_repo(repo_url)
    branch = repo.default_branch
    files: list[dict] = []
    for path in paths:
        try:
            item = repo.get_contents(path, ref=branch)
            if isinstance(item, list):
                continue
            files.append(
                {
                    "path": path,
                    "content": item.decoded_content.decode("utf-8", errors="ignore"),
                }
            )
        except GithubException:
            continue
    return files


def merge_repo_files(existing: list[dict], extra: list[dict]) -> list[dict]:
    """Merge file lists by path; extra overwrites existing."""
    by_path = {f["path"]: f for f in existing}
    for f in extra:
        by_path[f["path"]] = f
    return list(by_path.values())


def get_issue(issue_url: str) -> dict:
    """
    Fetch GitHub issue details — no LLM needed.
    Returns title, body, labels, number.
    """
    parts = issue_url.rstrip("/").split("/")
    issue_number = int(parts[-1])
    repo = _parse_repo("/".join(parts[:-2]))
    issue = repo.get_issue(issue_number)
    return {
        "number": issue.number,
        "title": issue.title,
        "body": issue.body or "",
        "labels": [l.name for l in issue.labels],
        "url": issue_url,
    }


def get_repo_files(repo_url: str, extensions: tuple | None = None) -> list[dict]:
    """
    Fetch all source files from repo — deterministic, no LLM.
    Returns list of {path, content}.
    """
    extensions = extensions or settings.index_file_extensions
    repo = _parse_repo(repo_url)
    files = []
    contents = repo.get_contents("")

    while contents:
        item = contents.pop(0)
        if item.type == "dir":
            contents.extend(repo.get_contents(item.path))
        elif item.path.endswith(extensions):
            try:
                files.append({
                    "path": item.path,
                    "content": item.decoded_content.decode("utf-8", errors="ignore"),
                })
            except Exception:
                continue

    return files


def get_latest_commit_sha(repo_url: str, branch: str = "main") -> str:
    """Get the latest commit SHA for a branch — used as cache key."""
    repo = _parse_repo(repo_url)
    return repo.get_branch(branch).commit.sha


def get_default_branch(repo_url: str) -> str:
    """Return the repository's default branch name."""
    repo = _parse_repo(repo_url)
    return repo.default_branch


def get_repo_files_cached(repo_url: str, extensions: tuple | None = None) -> list[dict]:
    """
    Fetch repo files with Redis caching keyed by repo URL + latest commit SHA.

    Cache hit  → return files instantly, zero GitHub API file calls.
    Cache miss → fetch from GitHub, store in Redis for 6 hours.

    This means two tasks on the same repo at the same commit share one fetch.
    Cache is automatically invalidated when a new commit is pushed (SHA changes).
    """
    default_branch = get_default_branch(repo_url)
    sha = get_latest_commit_sha(repo_url, branch=default_branch)
    extensions = extensions or settings.index_file_extensions
    ext_key = ",".join(sorted(extensions))
    cache_key = f"repo:files:{hashlib.sha256(f'{repo_url}:{sha}:{ext_key}'.encode()).hexdigest()}"

    cached = _cache.get(cache_key)
    if cached:
        return json.loads(cached)

    files = get_repo_files(repo_url, extensions)
    _cache.setex(cache_key, _REPO_CACHE_TTL, json.dumps(files))
    return files


def create_pull_request(repo_url: str, branch: str, title: str, body: str, base: str | None = None) -> str:
    """Create a PR and return its URL."""
    repo = _parse_repo(repo_url)
    pr = repo.create_pull(title=title, body=body, head=branch, base=(base or repo.default_branch))
    return pr.html_url


def create_branch_and_commit(repo_url: str, branch: str, file_path: str, content: str, commit_message: str) -> None:
    """Create a branch and commit a file change."""
    repo = _parse_repo(repo_url)
    source = repo.get_branch(repo.default_branch)
    # Create the branch ref if it does not already exist.
    try:
        repo.create_git_ref(ref=f"refs/heads/{branch}", sha=source.commit.sha)
    except GithubException as exc:
        if exc.status != 422:
            raise

    try:
        existing = repo.get_contents(file_path, ref=branch)
        repo.update_file(file_path, commit_message, content, existing.sha, branch=branch)
    except GithubException:
        repo.create_file(file_path, commit_message, content, branch=branch)
