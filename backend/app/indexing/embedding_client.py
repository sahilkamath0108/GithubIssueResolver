from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.core.settings import Settings, settings as default_settings
from app.indexing.gemini_embeddings import GeminiEmbeddingClient
from app.indexing.jina_embeddings import JinaEmbeddingClient


@runtime_checkable
class EmbeddingClient(Protocol):
    def embed_query(self, text: str) -> list[float]: ...
    def embed_document(self, text: str, *, title: str | None = None) -> list[float]: ...
    def embed_text(self, text: str) -> list[float]: ...
    def embed_batch(self, texts: list[str]) -> list[list[float]]: ...
    def close(self) -> None: ...


def create_embedding_client(settings: Settings | None = None) -> EmbeddingClient:
    cfg = settings or default_settings
    provider = cfg.EMBEDDING_PROVIDER.strip().lower()
    if provider == "jina":
        return JinaEmbeddingClient(cfg)
    if provider == "gemini":
        return GeminiEmbeddingClient(cfg)
    raise ValueError(
        f"Unsupported EMBEDDING_PROVIDER={cfg.EMBEDDING_PROVIDER!r}. Use 'jina' or 'gemini'."
    )
