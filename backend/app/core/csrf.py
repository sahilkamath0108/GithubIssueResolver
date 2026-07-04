import secrets

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.settings import settings

CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"
_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

_CSRF_EXEMPT = {
    "/api/v1/webhooks/github/issues",
    "/api/v1/auth/github/login",
    "/api/v1/auth/github/callback",
    "/api/v1/auth/logout",
}


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def _origin_allowed(origin: str) -> bool:
    if not origin:
        return False
    allowed = [settings.FRONTEND_ORIGIN.rstrip("/")] if settings.FRONTEND_ORIGIN else []
    allowed.extend(
        [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
        ]
    )
    origin = origin.rstrip("/")
    return any(origin == base or origin.startswith(f"{base}/") for base in allowed if base)


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    Double-submit cookie CSRF protection for browser sessions (OAuth cookie auth).
    Skipped when no session cookie or when X-API-Key is used.
    """

    async def dispatch(self, request: Request, call_next):
        if request.method not in _UNSAFE_METHODS:
            return await call_next(request)
        if request.url.path in _CSRF_EXEMPT:
            return await call_next(request)

        session = request.cookies.get(settings.AUTH_COOKIE_NAME)
        if not session:
            return await call_next(request)
        if request.headers.get("X-API-Key"):
            return await call_next(request)

        cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
        header_token = request.headers.get(CSRF_HEADER_NAME)
        if cookie_token and header_token and secrets.compare_digest(cookie_token, header_token):
            return await call_next(request)

        origin = request.headers.get("Origin") or request.headers.get("Referer", "")
        if _origin_allowed(origin):
            return await call_next(request)

        return JSONResponse(status_code=403, content={"detail": "CSRF validation failed."})
