import logging

from app.core.settings import settings
from app.indexing.embedding_client import EmbeddingClient, create_embedding_client
from app.indexing.qdrant_store import QdrantVectorStore

logger = logging.getLogger(__name__)

_vector_store: QdrantVectorStore | None = None
_embedder: EmbeddingClient | None = None


def _get_vector_store() -> QdrantVectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = QdrantVectorStore()
    return _vector_store


def _get_embedder() -> EmbeddingClient:
    global _embedder
    if _embedder is None:
        _embedder = create_embedding_client()
    return _embedder


def search_relevant_chunks(
    repo_full_name: str, query: str, top_k: int | None = None
) -> list[dict]:
    """
    Vector search in Qdrant for the repo's code chunks (payload.repo = owner/name).
    Returns list of {path, chunk} where chunk is the stored text payload.
    """
    top_k = top_k or settings.CONTEXT_SEARCH_TOP_K
    vector = _get_embedder().embed_query(query)
    out = _get_vector_store().search_repo_chunks(
        repo_full_name,
        vector,
        top_k=top_k,
    )

    logger.info(
        "Qdrant search returned %s chunks for repo=%s query=%r",
        len(out),
        repo_full_name,
        query[:200],
    )
    return out
