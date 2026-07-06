"""BYOK: user-supplied Groq/Jina keys when server env keys are unset."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.settings import settings
from app.core.user_provider_keys import resolve_groq_api_key, resolve_jina_api_key
from app.repositories.github_user_repo import GitHubUserRepository


def user_must_supply_provider_keys() -> bool:
    """Hosted multi-tenant mode: OAuth on and no shared provider keys in env."""
    if not settings.oauth_enabled:
        return False
    needs_groq = not (settings.GROQ_API_KEY or "").strip()
    provider = (settings.EMBEDDING_PROVIDER or "jina").strip().lower()
    needs_jina = provider == "jina" and not (settings.JINA_API_KEY or "").strip()
    return needs_groq or needs_jina


def provider_keys_status(db: Session, user_id: int | None) -> dict:
    repo = GitHubUserRepository(db) if user_id else None
    user_groq = bool(repo and repo.get_groq_api_key(user_id))
    user_jina = bool(repo and repo.get_jina_api_key(user_id))
    server_groq = bool((settings.GROQ_API_KEY or "").strip())
    server_jina = bool((settings.JINA_API_KEY or "").strip())
    provider = (settings.EMBEDDING_PROVIDER or "jina").strip().lower()
    jina_needed = provider == "jina"
    return {
        "user_keys_required": user_must_supply_provider_keys(),
        "embedding_provider": provider,
        "groq_configured": server_groq or user_groq,
        "jina_configured": (not jina_needed) or server_jina or user_jina,
        "groq_user_configured": user_groq,
        "jina_user_configured": user_jina,
    }


def assert_provider_keys_for_user(db: Session, user_id: int) -> None:
    if not user_must_supply_provider_keys():
        return
    status = provider_keys_status(db, user_id)
    missing: list[str] = []
    if not status["groq_configured"]:
        missing.append("Groq")
    if status["embedding_provider"] == "jina" and not status["jina_configured"]:
        missing.append("Jina")
    if missing:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Add your {' and '.join(missing)} API key(s) in Settings before continuing. "
                "Keys are encrypted and tied to your account."
            ),
        )


def load_user_provider_keys(db: Session, user_id: int) -> tuple[str | None, str | None]:
    repo = GitHubUserRepository(db)
    return repo.get_groq_api_key(user_id), repo.get_jina_api_key(user_id)


def assert_resolved_provider_keys_available() -> None:
    """Called inside worker/request after context is set."""
    if not resolve_groq_api_key():
        raise RuntimeError("GROQ_API_KEY is not set. Add your Groq key in Settings.")
    provider = (settings.EMBEDDING_PROVIDER or "jina").strip().lower()
    if provider == "jina" and not resolve_jina_api_key():
        raise RuntimeError("JINA_API_KEY is not set. Add your Jina key in Settings.")
