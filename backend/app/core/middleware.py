from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.settings import settings

# Paths that don't require authentication
_PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


class APIKeyMiddleware(BaseHTTPMiddleware):
    """
    Simple API key authentication middleware.
    Expects header: X-API-Key: <key>
    """

    async def dispatch(self, request: Request, call_next):
        # If no API key configured, allow all requests (local dev)
        if not settings.API_KEY:
            return await call_next(request)

        # Allow public paths through without auth
        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)

        api_key = request.headers.get("X-API-Key")
        if not api_key or api_key != settings.API_KEY:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key."},
            )

        return await call_next(request)
