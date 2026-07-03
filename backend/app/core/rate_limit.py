import redis as redis_lib
from fastapi import Depends, HTTPException, Request

from app.core.settings import settings

_redis: redis_lib.Redis | None = None


def _redis_client() -> redis_lib.Redis:
    global _redis
    if _redis is None:
        _redis = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


def _client_key(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _rate_limit_factory(times: int | None, seconds: int):
    limit = times if times is not None else settings.RATE_LIMIT_PER_MINUTE

    async def _check(request: Request) -> None:
        if not settings.RATE_LIMIT_ENABLED:
            return
        key = f"rate:{request.url.path}:{_client_key(request)}"
        r = _redis_client()
        count = r.incr(key)
        if count == 1:
            r.expire(key, seconds)
        if count > limit:
            raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again later.")

    return _check


def rate_limit_dep(times: int | None = None, seconds: int = 60):
    if not settings.RATE_LIMIT_ENABLED:
        async def _noop() -> None:
            return None

        return [Depends(_noop)]
    return [Depends(_rate_limit_factory(times, seconds))]
