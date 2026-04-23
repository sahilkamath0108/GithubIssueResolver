from __future__ import annotations

import logging
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.settings import Settings, settings as default_settings

logger = logging.getLogger(__name__)


class OllamaEmbeddingClient:
    """Calls Ollama's HTTP API to produce dense vectors for text chunks."""

    def __init__(self, settings: Settings | None = None):
        self._settings = settings or default_settings
        base = self._settings.OLLAMA_BASE_URL.rstrip("/")
        self._client = httpx.Client(
            base_url=base,
            timeout=httpx.Timeout(120.0, connect=10.0),
        )
        self._dim: int | None = self._settings.QDRANT_EMBEDDING_DIM

    def close(self) -> None:
        self._client.close()

    @property
    def vector_size(self) -> int | None:
        return self._dim

    def _parse_embedding_vector(self, data: dict[str, Any]) -> list[float]:
        vec = data.get("embedding")
        if isinstance(vec, list) and vec:
            return [float(x) for x in vec]
        emb = data.get("embeddings")
        if isinstance(emb, list) and emb and isinstance(emb[0], list):
            return [float(x) for x in emb[0]]
        return []

    @retry(
        retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
        wait=wait_exponential(multiplier=1, min=1, max=20),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    def embed_text(self, text: str) -> list[float]:
        """Single-text embedding; used for queries or dimension probing."""
        body = {
            "model": self._settings.OLLAMA_EMBEDDING_MODEL,
            "prompt": text,
        }
        r = self._client.post("/api/embeddings", json=body)
        if r.status_code == 404:
            alt = self._client.post(
                "/api/embed",
                json={"model": self._settings.OLLAMA_EMBEDDING_MODEL, "input": text},
            )
            alt.raise_for_status()
            vec = self._parse_embedding_vector(alt.json())
        else:
            r.raise_for_status()
            vec = self._parse_embedding_vector(r.json())

        if not vec:
            raise RuntimeError(
                f"Ollama returned an empty embedding for model "
                f"{self._settings.OLLAMA_EMBEDDING_MODEL!r}. "
                "Use a model that supports embeddings (for example nomic-embed-text), "
                "or verify the model name matches `ollama list`."
            )
        if self._dim is None:
            self._dim = len(vec)
            logger.info("Inferred embedding dimension from Ollama", extra={"dim": self._dim})
        elif len(vec) != self._dim:
            raise RuntimeError(
                f"Embedding length mismatch: expected {self._dim}, got {len(vec)}. "
                "Use a single embedding model per Qdrant collection, or set QDRANT_EMBEDDING_DIM=null "
                "only when the collection is empty or recreated."
            )
        return vec

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embeds each string (Ollama embeddings API is per-request)."""
        return [self.embed_text(t) for t in texts]
