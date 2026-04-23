import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.indexing import RepoIndexer
from app.indexing.schemas import IndexRunResult
from app.schemas.indexing import RepoIndexResponse, RepoSyncRequest

logger = logging.getLogger(__name__)

router = APIRouter()


def _to_response(result: IndexRunResult) -> RepoIndexResponse:
    return RepoIndexResponse(
        repo=result.repo,
        mode=result.mode,
        commit_sha=result.commit_sha,
        files_indexed=result.files_indexed,
        chunks_written=result.chunks_written,
        files_deleted=result.files_deleted,
        files_skipped_unchanged=result.files_skipped_unchanged,
        message=result.message,
    )


@router.post("/sync", response_model=RepoIndexResponse)
def sync_repo_index(payload: RepoSyncRequest, db: Session = Depends(get_db)):
    """
    Single indexing endpoint: compares GitHub's latest default-branch commit to the commit
    stored for this repo (Postgres ``repo_index_state``), then full-indexes, incrementally
    updates by blob SHA diff, or skips. Use ``force_full`` to wipe Qdrant vectors for the
    repo and rebuild from scratch.
    """
    indexer = RepoIndexer(db)
    try:
        try:
            result = indexer.sync_repo(payload.repo, force_full=payload.force_full)
        except RuntimeError as exc:
            # Commonly Qdrant auth/URL issues – return a clear API error
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return _to_response(result)
    finally:
        indexer.close()
