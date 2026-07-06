import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db, resolve_auth_context
from app.core.rate_limit import rate_limit_dep
from app.core.settings import settings
from app.indexing import RepoIndexer
from app.indexing.github_client import GitHubRepoClient
from app.indexing.schemas import IndexRunResult
from app.repositories.github_user_repo import GitHubUserRepository
from app.schemas.indexing import RepoIndexResponse, RepoSyncRequest
from app.services import auth_service, github_service
from app.core.user_provider_keys import user_provider_keys_context
from app.services.provider_key_service import (
    assert_provider_keys_for_user,
    assert_resolved_provider_keys_available,
    load_user_provider_keys,
)

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
def sync_repo_index(payload: RepoSyncRequest, request: Request, db: Session = Depends(get_db)):
    """Sync repository index (full / incremental / skip by commit SHA)."""
    ctx = resolve_auth_context(request, db)
    if ctx.user is None and not ctx.is_service_account:
        if settings.oauth_enabled:
            raise HTTPException(status_code=401, detail="Sign in with GitHub to index repositories.")
        raise HTTPException(status_code=401, detail="Authentication required.")

    try:
        repo = github_service.validate_repo_slug(payload.repo)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    access_token = None
    groq_key = None
    jina_key = None
    if ctx.user is not None:
        access_token = GitHubUserRepository(db).get_access_token(ctx.user.id)
        if not access_token:
            raise HTTPException(status_code=401, detail="GitHub token missing. Sign in again.")
        assert_provider_keys_for_user(db, ctx.user.id)
        groq_key, jina_key = load_user_provider_keys(db, ctx.user.id)
        try:
            auth_service.verify_repo_access(access_token, repo, require_push=False)
        except ValueError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
    elif settings.oauth_enabled and not settings.GITHUB_TOKEN:
        raise HTTPException(
            status_code=403,
            detail="API key indexing requires GITHUB_TOKEN when OAuth is enabled.",
        )

    github_client = GitHubRepoClient(access_token=access_token) if access_token else None
    with user_provider_keys_context(groq_api_key=groq_key, jina_api_key=jina_key):
        assert_resolved_provider_keys_available()
        indexer = RepoIndexer(db, github=github_client)
        try:
            try:
                result = indexer.sync_repo(repo, force_full=payload.force_full)
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc
            return _to_response(result)
        finally:
            indexer.close()
