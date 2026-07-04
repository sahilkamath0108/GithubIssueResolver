from __future__ import annotations

import logging
from typing import Any

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from app.core.settings import Settings, settings as default_settings

logger = logging.getLogger(__name__)


def format_code_retrieval_query(content: str) -> str:
    """Gemini Embedding 2 asymmetric query format for code search."""
    return f"task: code retrieval | query: {content}"


def format_retrieval_document(content: str, *, title: str | None = None) -> str:
    """Gemini Embedding 2 document format for indexed code chunks."""
    doc_title = title if title else "none"
    return f"title: {doc_title} | text: {content}"


def _retryable_embedding_error(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TransportError, httpx.TimeoutException)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return code >= 500 or code == 429
    return False


class GeminiEmbeddingClient:
    """Calls the Gemini API embedContent endpoint for dense text vectors."""

    def __init__(self, settings: Settings | None = None):
        self._settings = settings or default_settings
        if not self._settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY must be set for Gemini embeddings.")
        base = self._settings.GEMINI_API_BASE_URL.rstrip("/")
        self._client = httpx.Client(
            base_url=base,
            timeout=httpx.Timeout(120.0, connect=10.0),
            headers={"x-goog-api-key": self._settings.GEMINI_API_KEY},
        )
        self._dim: int | None = self._settings.GEMINI_EMBED_OUTPUT_DIMENSION or None

    def close(self) -> None:
        self._client.close()

    @property
    def vector_size(self) -> int | None:
        return self._dim

    def _prepare_text(self, text: str) -> str:
        cleaned = text.replace("\x00", "").strip()
        if not cleaned:
            raise ValueError("Cannot embed empty text.")
        max_chars = max(256, self._settings.GEMINI_EMBED_MAX_CHARS)
        if len(cleaned) > max_chars:
            logger.warning(
                "Truncating text for Gemini embedding (len=%s max=%s)",
                len(cleaned),
                max_chars,
            )
            cleaned = cleaned[:max_chars]
        return cleaned

    def _parse_embedding_vector(self, data: dict[str, Any]) -> list[float]:
        embedding = data.get("embedding")
        if isinstance(embedding, dict):
            values = embedding.get("values")
            if isinstance(values, list) and values:
                return [float(x) for x in values]

        embeddings = data.get("embeddings")
        if isinstance(embeddings, list) and embeddings:
            first = embeddings[0]
            if isinstance(first, dict):
                values = first.get("values")
                if isinstance(values, list) and values:
                    return [float(x) for x in values]
        return []

    def _request_embedding(self, text: str) -> list[float]:
        model = self._settings.GEMINI_EMBEDDING_MODEL
        body: dict[str, Any] = {
            "model": f"models/{model}",
            "content": {"parts": [{"text": text}]},
        }
        dim = self._settings.GEMINI_EMBED_OUTPUT_DIMENSION
        if dim:
            body["output_dimensionality"] = dim

        response = self._client.post(f"/models/{model}:embedContent", json=body)
        if response.status_code >= 400:
            logger.error(
                "Gemini embedContent failed status=%s model=%s body=%s",
                response.status_code,
                model,
                response.text[:500],
            )
        response.raise_for_status()
        return self._parse_embedding_vector(response.json())

    @retry(
        retry=retry_if_exception(_retryable_embedding_error),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    def _embed(self, text: str) -> list[float]:
        prepared = self._prepare_text(text)
        vec = self._request_embedding(prepared)

        if not vec:
            raise RuntimeError(
                f"Gemini returned an empty embedding for model "
                f"{self._settings.GEMINI_EMBEDDING_MODEL!r}."
            )
        if self._dim is None:
            self._dim = len(vec)
            logger.info("Inferred embedding dimension from Gemini", extra={"dim": self._dim})
        elif len(vec) != self._dim:
            raise RuntimeError(
                f"Embedding length mismatch: expected {self._dim}, got {len(vec)}. "
                "Use a single embedding model per Qdrant collection, or recreate the collection."
            )
        return vec

    def embed_query(self, text: str) -> list[float]:
        """Embed a search query (asymmetric code-retrieval task format)."""
        return self._embed(format_code_retrieval_query(text))

    def embed_document(self, text: str, *, title: str | None = None) -> list[float]:
        """Embed an indexed document/chunk (asymmetric document format)."""
        return self._embed(format_retrieval_document(text, title=title))

    def embed_text(self, text: str) -> list[float]:
        """Backward-compatible alias — embeds as a retrieval document without title."""
        return self.embed_document(text)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embeds each string individually (Gemini Embedding 2 requires separate requests)."""
        return [self.embed_document(t) for t in texts]
