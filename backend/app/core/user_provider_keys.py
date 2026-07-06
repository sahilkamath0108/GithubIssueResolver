"""Per-request Groq/Jina API keys (OAuth users) with env fallback."""

from __future__ import annotations

import contextvars
from contextlib import contextmanager
from typing import Iterator

from app.core.settings import settings

_groq_api_key: contextvars.ContextVar[str | None] = contextvars.ContextVar("groq_api_key", default=None)
_jina_api_key: contextvars.ContextVar[str | None] = contextvars.ContextVar("jina_api_key", default=None)


def resolve_groq_api_key() -> str:
    override = _groq_api_key.get()
    if override:
        return override
    return (settings.GROQ_API_KEY or "").strip()


def resolve_jina_api_key() -> str:
    override = _jina_api_key.get()
    if override:
        return override
    return (settings.JINA_API_KEY or "").strip()


@contextmanager
def user_provider_keys_context(
    *,
    groq_api_key: str | None = None,
    jina_api_key: str | None = None,
) -> Iterator[None]:
    groq_tok = _groq_api_key.set(groq_api_key or None)
    jina_tok = _jina_api_key.set(jina_api_key or None)
    try:
        yield
    finally:
        _groq_api_key.reset(groq_tok)
        _jina_api_key.reset(jina_tok)
