import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.rate_limit import rate_limit_dep
from app.core.settings import settings
from app.indexing import RepoIndexer
from app.indexing.schemas import IndexRunResult
from app.schemas.indexing import RepoIndexResponse, RepoSyncRequest
from app.services import github_service

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


@router.post("/sync", response_model=RepoIndexResponse, dependencies=rate_limit_dep(times=10))
def sync_repo_index(payload: RepoSyncRequest, db: Session = Depends(get_db)):
    """Sync repository index (full / incremental / skip by commit SHA)."""
    try:
        repo = github_service.validate_repo_slug(payload.repo)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    indexer = RepoIndexer(db)
    try:
        try:
            result = indexer.sync_repo(repo, force_full=payload.force_full)
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return _to_response(result)
    finally:
        indexer.close()
