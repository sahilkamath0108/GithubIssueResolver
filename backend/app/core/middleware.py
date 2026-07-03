import hmac

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.security import verify_api_key
from app.core.settings import settings

# Paths that don't require API key authentication
_PUBLIC_PATHS = {
    "/health",
    "/api/v1/webhooks/github/issues",
}

if settings.EXPOSE_DOCS:
    _PUBLIC_PATHS.update({"/docs", "/openapi.json", "/redoc"})


class APIKeyMiddleware(BaseHTTPMiddleware):
    """
    API key authentication via X-API-Key header.
    Webhook route is public (uses HMAC signature instead).
    When API_KEY is empty, all requests are allowed (local dev only).
    """

    async def dispatch(self, request: Request, call_next):
        if not settings.API_KEY:
            return await call_next(request)

        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)

        api_key = request.headers.get("X-API-Key")
        if not verify_api_key(api_key):
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key."},
            )

        return await call_next(request)
