import secrets
from urllib.parse import urlencode

import redis as redis_lib
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, resolve_auth_context
from app.core.csrf import CSRF_COOKIE_NAME, new_csrf_token
from app.core.settings import settings
from app.repositories.github_user_repo import GitHubUserRepository
from app.schemas.auth import (
    AuthStatusResponse,
    GitHubRepoSummary,
    ProviderKeysStatus,
    ProviderKeysUpdate,
    UserProfile,
)
from app.services import auth_service
from app.services.provider_key_service import provider_keys_status

router = APIRouter()
_oauth_state = redis_lib.Redis.from_url(settings.REDIS_URL, decode_responses=True)
_STATE_TTL = 600


def _frontend_redirect(path: str = "/") -> str:
    base = (settings.FRONTEND_ORIGIN or "http://localhost:3000").rstrip("/")
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{base}{path}"


@router.get("/status", response_model=AuthStatusResponse)
def auth_status(request: Request, db: Session = Depends(get_db)):
    from app.api.deps import resolve_auth_context

    ctx = resolve_auth_context(request, db)
    return AuthStatusResponse(
        oauth_enabled=settings.oauth_enabled,
        authenticated=ctx.user is not None,
    )


@router.get("/me", response_model=UserProfile)
def auth_me(user=Depends(get_current_user)):
    return UserProfile(
        id=user.id,
        github_id=user.github_id,
        login=user.login,
        avatar_url=user.avatar_url,
    )


@router.get("/repos", response_model=list[GitHubRepoSummary])
def list_my_repos(
    page: int = Query(default=1, ge=1),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    token = GitHubUserRepository(db).get_access_token(user.id)
    if not token:
        raise HTTPException(status_code=401, detail="GitHub token not found. Sign in again.")
    repos = auth_service.list_user_repos(token, page=page)
    return [GitHubRepoSummary(**r) for r in repos]


@router.get("/provider-keys", response_model=ProviderKeysStatus)
def get_provider_keys(user=Depends(get_current_user), db: Session = Depends(get_db)):
    return ProviderKeysStatus(**provider_keys_status(db, user.id))


@router.put("/provider-keys", response_model=ProviderKeysStatus)
def update_provider_keys(
    payload: ProviderKeysUpdate,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = GitHubUserRepository(db)
    groq = payload.groq_api_key.strip() if isinstance(payload.groq_api_key, str) else None
    jina = payload.jina_api_key.strip() if isinstance(payload.jina_api_key, str) else None
    if payload.groq_api_key is not None and groq is not None and len(groq) < 8:
        raise HTTPException(status_code=400, detail="Groq API key looks too short.")
    if payload.jina_api_key is not None and jina is not None and len(jina) < 8:
        raise HTTPException(status_code=400, detail="Jina API key looks too short.")
    repo.set_provider_keys(
        user.id,
        groq_api_key=groq if payload.groq_api_key is not None else None,
        jina_api_key=jina if payload.jina_api_key is not None else None,
    )
    return ProviderKeysStatus(**provider_keys_status(db, user.id))


@router.get("/github/login")
def github_login():
    if not settings.oauth_enabled:
        raise HTTPException(status_code=503, detail="GitHub OAuth is not configured.")
    state = secrets.token_urlsafe(32)
    _oauth_state.setex(f"oauth:state:{state}", _STATE_TTL, "1")
    return RedirectResponse(auth_service.build_github_login_url(state), status_code=302)


@router.get("/github/callback")
async def github_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    if error:
        qs = urlencode({"auth_error": error})
        return RedirectResponse(f"{_frontend_redirect('/login')}?{qs}", status_code=302)
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing OAuth code or state.")
    if not _oauth_state.get(f"oauth:state:{state}"):
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state.")
    _oauth_state.delete(f"oauth:state:{state}")

    access_token, scope = await auth_service.exchange_code_for_token(code)
    profile = await auth_service.fetch_github_profile(access_token)
    github_id = profile.get("id")
    login = profile.get("login")
    if not github_id or not login:
        raise HTTPException(status_code=502, detail="GitHub profile response was incomplete.")

    user_repo = GitHubUserRepository(db)
    user = user_repo.upsert_oauth_user(
        github_id=int(github_id),
        login=str(login),
        avatar_url=profile.get("avatar_url"),
        access_token=access_token,
        token_scope=scope,
    )
    session = auth_service.create_session_token(user)

    response = RedirectResponse(_frontend_redirect("/"), status_code=302)
    response.set_cookie(
        key=settings.AUTH_COOKIE_NAME,
        value=session,
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite="lax",
        max_age=settings.JWT_EXPIRE_MINUTES * 60,
    )
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=new_csrf_token(),
        httponly=False,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite="lax",
        max_age=settings.JWT_EXPIRE_MINUTES * 60,
    )
    return response


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    """Clear app session and revoke stored GitHub token. Stays in the app (no GitHub redirect)."""
    ctx = resolve_auth_context(request, db)
    user_repo = GitHubUserRepository(db)

    if ctx.user is not None:
        token = user_repo.get_access_token(ctx.user.id)
        if token:
            auth_service.revoke_github_token(token)
        user_repo.clear_access_token(ctx.user.id)

    response.delete_cookie(
        key=settings.AUTH_COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="lax",
        secure=settings.AUTH_COOKIE_SECURE,
    )
    response.delete_cookie(CSRF_COOKIE_NAME, path="/")

    return {
        "message": "Logged out.",
        "redirect_url": _frontend_redirect("/login"),
    }
