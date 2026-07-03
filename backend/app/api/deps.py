from dataclasses import dataclass
from typing import Generator, Optional

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.security import verify_api_key
from app.core.settings import settings
from app.db.session import SessionLocal
from app.models.github_user import GitHubUser
from app.repositories.github_user_repo import GitHubUserRepository
from app.services import auth_service


@dataclass
class AuthContext:
    user: GitHubUser | None
    is_service_account: bool


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency — yields a DB session and closes it after request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _token_from_request(request: Request) -> str | None:
    auth = request.headers.get("Authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.cookies.get(settings.AUTH_COOKIE_NAME)


def resolve_auth_context(request: Request, db: Session) -> AuthContext:
    cached = getattr(request.state, "auth_context", None)
    if cached is not None:
        return cached

    user: GitHubUser | None = getattr(request.state, "user", None)
    if user is None:
        token = _token_from_request(request)
        if token and settings.oauth_enabled:
            payload = auth_service.decode_session_token(token)
            user_id = int(payload["sub"])
            user = GitHubUserRepository(db).get_by_id(user_id)

    is_service = bool(settings.API_KEY and verify_api_key(request.headers.get("X-API-Key")))
    ctx = AuthContext(user=user, is_service_account=is_service)
    request.state.auth_context = ctx
    if user is not None:
        request.state.user = user
    return ctx


def get_optional_user(request: Request, db: Session = Depends(get_db)) -> Optional[GitHubUser]:
    ctx = resolve_auth_context(request, db)
    return ctx.user


def get_current_user(request: Request, db: Session = Depends(get_db)) -> GitHubUser:
    ctx = resolve_auth_context(request, db)
    if ctx.user is not None:
        return ctx.user
    if ctx.is_service_account:
        raise HTTPException(
            status_code=403,
            detail="This endpoint requires a GitHub user session, not only an API key.",
        )
    raise HTTPException(status_code=401, detail="Sign in with GitHub to continue.")


def require_authenticated(request: Request, db: Session = Depends(get_db)) -> AuthContext:
    ctx = resolve_auth_context(request, db)
    if ctx.user is not None or ctx.is_service_account:
        return ctx
    raise HTTPException(status_code=401, detail="Authentication required.")


def assert_task_visible(task, request: Request, db: Session) -> None:
    ctx = resolve_auth_context(request, db)
    if ctx.is_service_account:
        return
    if ctx.user is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    if task.github_user_id is not None and task.github_user_id != ctx.user.id:
        raise HTTPException(status_code=403, detail="You do not have access to this task.")

