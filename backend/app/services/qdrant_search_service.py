import logging

from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import FieldCondition, Filter, MatchValue

from app.core.settings import settings
from app.indexing.ollama_embeddings import OllamaEmbeddingClient

logger = logging.getLogger(__name__)

_qdrant = QdrantClient(
    url=settings.QDRANT_URL,
    api_key=(settings.QDRANT_API_KEY or None),
    timeout=settings.QDRANT_TIMEOUT,
)
_embedder = OllamaEmbeddingClient()


def search_relevant_chunks(repo_full_name: str, query: str, top_k: int = 5) -> list[dict]:
    """
    Vector search in Qdrant for the repo's code chunks.
    Returns list of {path, chunk} where chunk is the stored text payload.
    """
    vector = _embedder.embed_text(query)
    try:
        # qdrant-client v1.16+ removed `.search` in favor of `.query_points`.
        response = _qdrant.query_points(
            collection_name=settings.QDRANT_COLLECTION,
            query=vector,
            limit=top_k,
            query_filter=Filter(
                must=[FieldCondition(key="repo", match=MatchValue(value=repo_full_name))]
            ),
            with_payload=True,
        )
        results = response.points
    except UnexpectedResponse as exc:
        # Managed Qdrant can require payload indexes for filtered search.
        if getattr(exc, "status_code", None) == 400:
            raise RuntimeError(
                "Qdrant rejected filtered search (400). Ensure payload indexes exist for `repo` (keyword). "
                "Create indexes for `repo` and `path` on your Qdrant collection."
            ) from exc
        raise

    out: list[dict] = []
    for r in results:
        payload = r.payload or {}
        path = payload.get("path")
        text = payload.get("text")
        if isinstance(path, str) and isinstance(text, str):
            out.append({"path": path, "chunk": text})

    logger.info(
        "Qdrant search returned chunks",
        extra={"repo": repo_full_name, "top_k": top_k, "returned": len(out)},
    )
    return out

