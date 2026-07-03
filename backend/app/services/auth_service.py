from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import HTTPException
from github import Github, GithubException

from app.core.settings import settings
from app.models.github_user import GitHubUser
from app.repositories.github_user_repo import GitHubUserRepository

_GITHUB_AUTHORIZE = "https://github.com/login/oauth/authorize"
_GITHUB_TOKEN = "https://github.com/login/oauth/access_token"
_GITHUB_USER = "https://api.github.com/user"
_OAUTH_SCOPES = "read:user repo"


def oauth_enabled() -> bool:
    return settings.oauth_enabled


def create_session_token(user: GitHubUser) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "login": user.login,
        "github_id": user.github_id,
        "iat": now,
        "exp": now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def decode_session_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired session.") from exc


def build_github_login_url(state: str) -> str:
    params = {
        "client_id": settings.GITHUB_OAUTH_CLIENT_ID,
        "redirect_uri": settings.GITHUB_OAUTH_CALLBACK_URL,
        "scope": _OAUTH_SCOPES,
        "state": state,
    }
    return f"{_GITHUB_AUTHORIZE}?{urlencode(params)}"


async def exchange_code_for_token(code: str) -> tuple[str, str | None]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            _GITHUB_TOKEN,
            headers={"Accept": "application/json"},
            data={
                "client_id": settings.GITHUB_OAUTH_CLIENT_ID,
                "client_secret": settings.GITHUB_OAUTH_CLIENT_SECRET,
                "code": code,
                "redirect_uri": settings.GITHUB_OAUTH_CALLBACK_URL,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        access_token = data.get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="GitHub did not return an access token.")
        return access_token, data.get("scope")


async def fetch_github_profile(access_token: str) -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            _GITHUB_USER,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
            },
        )
        resp.raise_for_status()
        return resp.json()


def verify_repo_access(access_token: str, repo_slug: str, *, require_push: bool = True) -> None:
    gh = Github(access_token)
    try:
        repo = gh.get_repo(repo_slug)
    except GithubException as exc:
        if exc.status == 404:
            raise ValueError(
                f"You do not have access to repository '{repo_slug}' or it does not exist."
            ) from exc
        raise ValueError(f"GitHub API error checking repository access: {exc.data}") from exc

    if require_push:
        perms = getattr(repo, "permissions", None)
        if perms and not (getattr(perms, "push", False) or getattr(perms, "admin", False)):
            raise ValueError(
                f"GitHub token lacks push access to '{repo_slug}'. "
                "Re-authorize the app with repo scope."
            )


def list_user_repos(access_token: str, *, page: int = 1, per_page: int = 100) -> list[dict]:
    gh = Github(access_token)
    repos = gh.get_user().get_repos(
        affiliation="owner,collaborator,organization_member",
        sort="updated",
        direction="desc",
    )
    start = (page - 1) * per_page
    end = start + per_page
    out: list[dict] = []
    for idx, repo in enumerate(repos):
        if idx < start:
            continue
        if idx >= end:
            break
        perms = getattr(repo, "permissions", None)
        out.append(
            {
                "full_name": repo.full_name,
                "private": repo.private,
                "html_url": repo.html_url,
                "default_branch": repo.default_branch,
                "permissions_push": bool(
                    perms and (getattr(perms, "push", False) or getattr(perms, "admin", False))
                ),
            }
        )
    return out


def load_user_from_repo(db_repo: GitHubUserRepository, user_id: int) -> GitHubUser:
    user = db_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User session is no longer valid.")
    return user
