import hmac
import re
from urllib.parse import urlparse

from fastapi import HTTPException

from app.core.settings import settings

_GITHUB_HOSTS = frozenset({"github.com", "www.github.com"})
_REPO_SLUG = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def verify_api_key(provided: str | None) -> bool:
    expected = settings.API_KEY
    if not expected:
        return True
    if not provided:
        return False
    return hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))


def validate_production_settings() -> list[str]:
    """Return list of misconfiguration warnings/errors for startup."""
    issues: list[str] = []
    if settings.ENVIRONMENT.lower() != "production":
        return issues
    if settings.oauth_enabled:
        if not settings.JWT_SECRET or len(settings.JWT_SECRET) < 32:
            issues.append("JWT_SECRET must be at least 32 characters when OAuth is enabled in production")
        origin = (settings.FRONTEND_ORIGIN or "").strip().lower()
        if origin.startswith("https://") and not settings.AUTH_COOKIE_SECURE:
            issues.append("AUTH_COOKIE_SECURE must be true when FRONTEND_ORIGIN uses HTTPS")
        elif origin.startswith("http://") and settings.AUTH_COOKIE_SECURE:
            issues.append("AUTH_COOKIE_SECURE should be false when FRONTEND_ORIGIN uses HTTP")
    elif not settings.API_KEY:
        issues.append("API_KEY must be set when ENVIRONMENT=production and OAuth is not configured")
    if settings.REQUIRE_WEBHOOK_SECRET and not settings.GITHUB_WEBHOOK_SECRET:
        issues.append("GITHUB_WEBHOOK_SECRET must be set when REQUIRE_WEBHOOK_SECRET=true")
    if settings.oauth_enabled and not settings.GITHUB_TOKEN:
        issues.append(
            "GITHUB_TOKEN is recommended for webhooks/background jobs when OAuth is enabled"
        )
    # Empty REPO_ALLOWLIST = any repo the authenticated user's GitHub token can access.
    # Set a comma-separated list only to cap which repos this server will touch.
    if not settings.SANDBOX_RUNNER_URL:
        issues.append("SANDBOX_RUNNER_URL must be set when ENVIRONMENT=production")
    if not settings.SANDBOX_RUNNER_SECRET:
        issues.append("SANDBOX_RUNNER_SECRET must be set when ENVIRONMENT=production")
    return issues


def assert_repo_allowed(repo_full_name: str) -> None:
    """Raise ValueError if repo is not in allowlist (when allowlist is configured)."""
    allowed = settings.repo_allowlist
    if not allowed:
        return
    normalized = repo_full_name.strip().lower()
    if normalized not in allowed:
        raise ValueError(
            f"Repository '{repo_full_name}' is not in REPO_ALLOWLIST. "
            f"Allowed: {', '.join(sorted(settings.repo_allowlist_raw))}"
        )


def parse_github_repo_url(url: str) -> str:
    """
    Validate a GitHub repository URL and return owner/name.
    Raises ValueError on invalid host or shape.
    """
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Repository URL must use http(s): {url}")
    host = (parsed.hostname or "").lower()
    if host not in _GITHUB_HOSTS:
        raise ValueError(f"Repository URL must be on github.com, got host '{host}'")
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2:
        raise ValueError(f"Invalid GitHub repository URL: {url}")
    slug = f"{parts[0]}/{parts[1]}"
    if not _REPO_SLUG.match(slug):
        raise ValueError(f"Invalid repository slug: {slug}")
    return slug


def parse_github_issue_url(url: str) -> tuple[str, int]:
    """Validate issue URL; return (owner/name, issue_number)."""
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Issue URL must use http(s): {url}")
    host = (parsed.hostname or "").lower()
    if host not in _GITHUB_HOSTS:
        raise ValueError(f"Issue URL must be on github.com, got host '{host}'")
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 4 or parts[2] != "issues":
        raise ValueError(f"Invalid GitHub issue URL: {url}")
    try:
        issue_number = int(parts[3])
    except ValueError as exc:
        raise ValueError(f"Invalid issue number in URL: {url}") from exc
    slug = f"{parts[0]}/{parts[1]}"
    if not _REPO_SLUG.match(slug):
        raise ValueError(f"Invalid repository slug in issue URL: {slug}")
    return slug, issue_number


def sanitize_repo_path(path: str) -> str:
    """
    Normalize and reject path traversal / absolute paths for GitHub commits.
    """
    if not path or not isinstance(path, str):
        raise ValueError("File path must be a non-empty string")
    normalized = path.replace("\\", "/").strip()
    if normalized.startswith("/") or ".." in normalized.split("/"):
        raise ValueError(f"Unsafe file path rejected: {path}")
    return normalized.lstrip("./")


def require_webhook_secret() -> None:
    if settings.REQUIRE_WEBHOOK_SECRET and not settings.GITHUB_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=503,
            detail="GITHUB_WEBHOOK_SECRET is required but not configured.",
        )
