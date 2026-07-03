from __future__ import annotations

import logging
from typing import Any

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from app.core.settings import Settings, settings as default_settings

logger = logging.getLogger(__name__)


def _retryable_embedding_error(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TransportError, httpx.TimeoutException)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False


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

    def _prepare_text(self, text: str) -> str:
        cleaned = text.replace("\x00", "").strip()
        if not cleaned:
            raise ValueError("Cannot embed empty text.")
        max_chars = max(256, self._settings.OLLAMA_EMBED_MAX_CHARS)
        if len(cleaned) > max_chars:
            logger.warning(
                "Truncating text for Ollama embedding (len=%s max=%s)",
                len(cleaned),
                max_chars,
            )
            cleaned = cleaned[:max_chars]
        return cleaned

    def _parse_embedding_vector(self, data: dict[str, Any]) -> list[float]:
        vec = data.get("embedding")
        if isinstance(vec, list) and vec:
            return [float(x) for x in vec]
        emb = data.get("embeddings")
        if isinstance(emb, list) and emb and isinstance(emb[0], list):
            return [float(x) for x in emb[0]]
        return []

    def _request_embedding(self, text: str) -> list[float]:
        model = self._settings.OLLAMA_EMBEDDING_MODEL
        legacy_body = {"model": model, "prompt": text}
        modern_body = {"model": model, "input": text}

        r = self._client.post("/api/embeddings", json=legacy_body)
        if r.status_code == 200:
            return self._parse_embedding_vector(r.json())

        # Newer Ollama embedding models (e.g. embeddinggemma:300m) prefer /api/embed.
        if r.status_code in (404, 500, 501):
            alt = self._client.post("/api/embed", json=modern_body)
            if alt.status_code == 200:
                return self._parse_embedding_vector(alt.json())
            if alt.status_code >= 400:
                logger.error(
                    "Ollama /api/embed failed status=%s model=%s body=%s",
                    alt.status_code,
                    model,
                    alt.text[:500],
                )
            alt.raise_for_status()

        if r.status_code >= 400:
            logger.error(
                "Ollama /api/embeddings failed status=%s model=%s body=%s",
                r.status_code,
                model,
                r.text[:500],
            )
        r.raise_for_status()
        return self._parse_embedding_vector(r.json())

    @retry(
        retry=retry_if_exception(_retryable_embedding_error),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    def embed_text(self, text: str) -> list[float]:
        """Single-text embedding; used for queries or dimension probing."""
        prepared = self._prepare_text(text)
        vec = self._request_embedding(prepared)

        if not vec:
            raise RuntimeError(
                f"Ollama returned an empty embedding for model "
                f"{self._settings.OLLAMA_EMBEDDING_MODEL!r}. "
                "Use an embedding model (e.g. embeddinggemma:300m), "
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
