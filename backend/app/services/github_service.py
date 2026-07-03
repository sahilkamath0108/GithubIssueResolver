import json
import hashlib
import redis as redis_lib
from typing import Optional
from github import Github, GithubException
from app.core.settings import settings
from app.core.security import (
    assert_repo_allowed,
    parse_github_issue_url,
    parse_github_repo_url,
    sanitize_repo_path,
)

_github = Github(settings.GITHUB_TOKEN)
_cache = redis_lib.Redis.from_url(settings.REDIS_URL, decode_responses=True)
_REPO_CACHE_TTL = 60 * 60 * 6  # 6 hours


def _get_repo(repo_url: str):
    slug = parse_github_repo_url(repo_url)
    assert_repo_allowed(slug)
    return _github.get_repo(slug), slug


def repo_full_name(repo_url: str) -> str:
    return parse_github_repo_url(repo_url)


def repo_full_name_from_issue_url(issue_url: str) -> str:
    slug, _ = parse_github_issue_url(issue_url)
    return slug


def assert_issue_matches_repo(issue_url: str, repo_url: str) -> None:
    issue_repo = repo_full_name_from_issue_url(issue_url)
    target_repo = repo_full_name(repo_url)
    if issue_repo.lower() != target_repo.lower():
        raise ValueError(
            f"Issue repo ({issue_repo}) does not match repo_url ({target_repo}). "
            "Use the same repository for both URLs."
        )
    assert_repo_allowed(target_repo)


def validate_repo_slug(repo: str) -> str:
    """Validate owner/name slug and allowlist."""
    repo = repo.strip()
    if not repo or "/" not in repo:
        raise ValueError('Repository must be in "owner/name" form')
    assert_repo_allowed(repo)
    return repo


def get_file_contents(repo_url: str, paths: list[str]) -> list[dict]:
    if not paths:
        return []
    repo, _ = _get_repo(repo_url)
    branch = repo.default_branch
    files: list[dict] = []
    for raw_path in paths:
        path = sanitize_repo_path(raw_path)
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
    by_path = {f["path"]: f for f in existing}
    for f in extra:
        by_path[f["path"]] = f
    return list(by_path.values())


def get_issue(issue_url: str) -> dict:
    slug, issue_number = parse_github_issue_url(issue_url)
    assert_repo_allowed(slug)
    repo = _github.get_repo(slug)
    issue = repo.get_issue(issue_number)
    return {
        "number": issue.number,
        "title": issue.title,
        "body": issue.body or "",
        "labels": [l.name for l in issue.labels],
        "url": issue_url,
    }


def get_repo_files(repo_url: str, extensions: tuple | None = None) -> list[dict]:
    extensions = extensions or settings.index_file_extensions
    repo, _ = _get_repo(repo_url)
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
    repo, _ = _get_repo(repo_url)
    return repo.get_branch(branch).commit.sha


def get_default_branch(repo_url: str) -> str:
    repo, _ = _get_repo(repo_url)
    return repo.default_branch


def get_repo_files_cached(repo_url: str, extensions: tuple | None = None) -> list[dict]:
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
    repo, _ = _get_repo(repo_url)
    pr = repo.create_pull(title=title, body=body, head=branch, base=(base or repo.default_branch))
    return pr.html_url


def create_branch_and_commit(
    repo_url: str, branch: str, file_path: str, content: str, commit_message: str
) -> None:
    safe_path = sanitize_repo_path(file_path)
    repo, _ = _get_repo(repo_url)
    source = repo.get_branch(repo.default_branch)
    try:
        repo.create_git_ref(ref=f"refs/heads/{branch}", sha=source.commit.sha)
    except GithubException as exc:
        if exc.status != 422:
            raise

    try:
        existing = repo.get_contents(safe_path, ref=branch)
        repo.update_file(safe_path, commit_message, content, existing.sha, branch=branch)
    except GithubException:
        repo.create_file(safe_path, commit_message, content, branch=branch)


def record_webhook_delivery(delivery_id: str) -> bool:
    """
    Return True if this delivery is new; False if duplicate (already processed).
    """
    if not delivery_id:
        return True
    key = f"webhook:delivery:{delivery_id}"
    return bool(_cache.set(key, "1", nx=True, ex=86400))
