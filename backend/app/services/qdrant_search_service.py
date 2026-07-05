import logging

from app.core.settings import settings
from app.indexing.embedding_client import EmbeddingClient, create_embedding_client
from app.indexing.qdrant_store import QdrantVectorStore
from app.services.retrieval import (
    build_search_queries,
    merge_search_hits,
    rank_retrieval_hits,
    truncate_retrieval_hits,
)
from app.services.plan_scope import Scope, resolve_scope

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
    Returns list of {path, chunk, score?} where chunk is the stored text payload.
    """
    top_k = top_k or settings.CONTEXT_SEARCH_TOP_K_PER_QUERY
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


def search_for_plan(
    repo_full_name: str,
    plan: dict,
    *,
    repo_paths: list[str] | None = None,
    issue: dict | None = None,
) -> tuple[list[dict], list[str]]:
    """
    Multi-query retrieval with merge, entrypoint boost, and final top-k cap.
    Returns (ranked_chunks, queries_used).
    """
    scope: Scope = resolve_scope(plan, issue or {})
    queries = build_search_queries(plan)
    per_query_k = settings.CONTEXT_SEARCH_TOP_K_PER_QUERY
    hit_lists = [search_relevant_chunks(repo_full_name, q, top_k=per_query_k) for q in queries]
    merged = merge_search_hits(hit_lists)
    ranked = rank_retrieval_hits(merged, repo_paths=repo_paths, scope=scope)
    final = truncate_retrieval_hits(ranked)

    logger.info(
        "Multi-query retrieval repo=%s scope=%s queries=%s merged=%s final=%s",
        repo_full_name,
        scope,
        len(queries),
        len(merged),
        len(final),
    )
    return final, queries
