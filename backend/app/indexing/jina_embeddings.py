from __future__ import annotations

import logging
from typing import Any

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from app.core.settings import Settings, settings as default_settings
from app.core.user_provider_keys import resolve_jina_api_key

logger = logging.getLogger(__name__)


def _retryable_embedding_error(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TransportError, httpx.TimeoutException)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return code >= 500 or code == 429
    return False


class JinaEmbeddingClient:
    """Calls Jina Embeddings API (https://api.jina.ai/v1/embeddings)."""

    def __init__(self, settings: Settings | None = None):
        self._settings = settings or default_settings
        api_key = resolve_jina_api_key() or (self._settings.JINA_API_KEY or "").strip()
        if not api_key:
            raise ValueError("JINA_API_KEY must be set for Jina embeddings.")
        base = self._settings.JINA_API_BASE_URL.rstrip("/")
        self._client = httpx.Client(
            base_url=base,
            timeout=httpx.Timeout(120.0, connect=10.0),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        self._dim: int | None = self._settings.JINA_EMBED_OUTPUT_DIMENSION

    def close(self) -> None:
        self._client.close()

    @property
    def vector_size(self) -> int | None:
        return self._dim

    def _prepare_text(self, text: str) -> str:
        cleaned = text.replace("\x00", "").strip()
        if not cleaned:
            raise ValueError("Cannot embed empty text.")
        max_chars = max(256, self._settings.JINA_EMBED_MAX_CHARS)
        if len(cleaned) > max_chars:
            logger.warning(
                "Truncating text for Jina embedding (len=%s max=%s)",
                len(cleaned),
                max_chars,
            )
            cleaned = cleaned[:max_chars]
        return cleaned

    def _parse_embeddings(self, data: dict[str, Any]) -> list[list[float]]:
        rows = data.get("data")
        if not isinstance(rows, list):
            return []
        vectors: list[list[float]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            embedding = row.get("embedding")
            if isinstance(embedding, list) and embedding:
                vectors.append([float(x) for x in embedding])
        return vectors

    def _request_embeddings(self, texts: list[str], *, task: str) -> list[list[float]]:
        if not texts:
            return []
        model = self._settings.JINA_EMBEDDING_MODEL
        body: dict[str, Any] = {
            "model": model,
            "input": texts,
            "task": task,
        }
        if self._settings.JINA_EMBED_NORMALIZED:
            body["normalized"] = True
        dim = self._settings.JINA_EMBED_OUTPUT_DIMENSION
        if dim:
            body["dimensions"] = dim

        response = self._client.post("/embeddings", json=body)
        if response.status_code >= 400:
            logger.error(
                "Jina embeddings failed status=%s model=%s task=%s body=%s",
                response.status_code,
                model,
                task,
                response.text[:500],
            )
        response.raise_for_status()
        vectors = self._parse_embeddings(response.json())
        if len(vectors) != len(texts):
            raise RuntimeError(
                f"Jina returned {len(vectors)} embeddings for {len(texts)} inputs."
            )
        return vectors

    def _validate_vector(self, vec: list[float]) -> list[float]:
        if not vec:
            raise RuntimeError(
                f"Jina returned an empty embedding for model "
                f"{self._settings.JINA_EMBEDDING_MODEL!r}."
            )
        if self._dim is None:
            self._dim = len(vec)
            logger.info("Inferred embedding dimension from Jina", extra={"dim": self._dim})
        elif len(vec) != self._dim:
            raise RuntimeError(
                f"Embedding length mismatch: expected {self._dim}, got {len(vec)}. "
                "Use a single embedding model per Qdrant collection, or recreate the collection."
            )
        return vec

    @retry(
        retry=retry_if_exception(_retryable_embedding_error),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    def _embed_one(self, text: str, *, task: str) -> list[float]:
        prepared = self._prepare_text(text)
        vec = self._request_embeddings([prepared], task=task)[0]
        return self._validate_vector(vec)

    def embed_query(self, text: str) -> list[float]:
        """Embed a search query (retrieval.query by default)."""
        return self._embed_one(text, task=self._settings.JINA_QUERY_TASK)

    def embed_document(self, text: str, *, title: str | None = None) -> list[float]:
        """Embed an indexed code chunk (retrieval.passage by default)."""
        payload = f"{title}\n{text}" if title else text
        return self._embed_one(payload, task=self._settings.JINA_DOCUMENT_TASK)

    def embed_text(self, text: str) -> list[float]:
        return self.embed_document(text)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple documents in one API call when possible."""
        if not texts:
            return []
        prepared = [self._prepare_text(t) for t in texts]
        batch_size = max(1, self._settings.JINA_EMBED_BATCH_SIZE)
        task = self._settings.JINA_DOCUMENT_TASK
        out: list[list[float]] = []
        for i in range(0, len(prepared), batch_size):
            batch = prepared[i : i + batch_size]
            vectors = self._request_embeddings(batch, task=task)
            for vec in vectors:
                out.append(self._validate_vector(vec))
        return out
