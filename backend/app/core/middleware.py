from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.security import verify_api_key
from app.core.settings import settings
from app.services import auth_service

# Paths that don't require authentication
_PUBLIC_PATHS = {
    "/health",
    "/api/v1/webhooks/github/issues",
    "/api/v1/auth/status",
    "/api/v1/auth/github/login",
    "/api/v1/auth/github/callback",
    "/api/v1/auth/logout",
}

if settings.EXPOSE_DOCS:
    _PUBLIC_PATHS.update({"/docs", "/openapi.json", "/redoc"})


def _extract_session_token(request: Request) -> str | None:
    auth = request.headers.get("Authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.cookies.get(settings.AUTH_COOKIE_NAME)


class APIKeyMiddleware(BaseHTTPMiddleware):
    """
    When OAuth is configured: require GitHub session JWT (cookie or Bearer) or X-API-Key.
    When OAuth is not configured: legacy API key gate (empty API_KEY = open for local dev).
    Webhook route is always public (uses HMAC signature instead).
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in _PUBLIC_PATHS:
            return await call_next(request)

        if settings.oauth_enabled:
            token = _extract_session_token(request)
            if token:
                try:
                    payload = auth_service.decode_session_token(token)
                    request.state.user_id = int(payload["sub"])
                except Exception:
                    return JSONResponse(
                        status_code=401,
                        content={"detail": "Invalid or expired session."},
                    )
            elif settings.API_KEY and verify_api_key(request.headers.get("X-API-Key")):
                request.state.user_id = None
            else:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Sign in with GitHub or provide a valid API key."},
                )
            return await call_next(request)

        if not settings.API_KEY:
            return await call_next(request)

        api_key = request.headers.get("X-API-Key")
        if not verify_api_key(api_key):
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key."},
            )

        return await call_next(request)
