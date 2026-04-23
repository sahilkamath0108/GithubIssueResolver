"""GitHub API → chunk → Ollama embeddings → Qdrant indexing."""

from app.indexing.indexer import RepoIndexer
from app.indexing.schemas import IndexRunResult, TextChunk, TreeBlobFile

__all__ = [
    "RepoIndexer",
    "IndexRunResult",
    "TextChunk",
    "TreeBlobFile",
]

# Primary workflow: RepoIndexer(db).sync_repo("owner/repo")
