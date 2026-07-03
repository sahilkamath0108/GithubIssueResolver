from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, resolve_auth_context, assert_task_visible
from app.core.rate_limit import rate_limit_dep
from app.core.settings import settings
from app.repositories.github_user_repo import GitHubUserRepository
from app.repositories.task_repo import TaskRepository
from app.schemas.workflow import WorkflowSubmitRequest, WorkflowSubmitResponse, TaskStatusResponse
from app.models.task import TaskStatus
from app.services import auth_service, github_service
from app.tasks.workflow_tasks import run_workflow_task
from fastapi import Request

router = APIRouter()


@router.post("/submit", response_model=WorkflowSubmitResponse, dependencies=rate_limit_dep())
def submit_workflow(
    payload: WorkflowSubmitRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Submit a GitHub issue for agent processing (requires GitHub OAuth user or API key)."""
    ctx = resolve_auth_context(request, db)
    if ctx.user is None and not ctx.is_service_account:
        if settings.oauth_enabled:
            raise HTTPException(status_code=401, detail="Sign in with GitHub to submit issues.")
        raise HTTPException(status_code=401, detail="Authentication required.")

    try:
        github_service.assert_issue_matches_repo(payload.issue_url, payload.repo_url)
        repo_slug = github_service.repo_full_name(payload.repo_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    github_user_id = None
    if ctx.user is not None:
        token = GitHubUserRepository(db).get_access_token(ctx.user.id)
        if not token:
            raise HTTPException(status_code=401, detail="GitHub token missing. Sign in again.")
        try:
            auth_service.verify_repo_access(token, repo_slug, require_push=True)
        except ValueError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        github_user_id = ctx.user.id
    elif settings.oauth_enabled and not settings.GITHUB_TOKEN:
        raise HTTPException(
            status_code=403,
            detail="API key submissions require GITHUB_TOKEN when OAuth is enabled.",
        )

    task_repo = TaskRepository(db)
    task = task_repo.create(
        issue_url=payload.issue_url,
        repo_url=payload.repo_url,
        github_user_id=github_user_id,
    )

    run_workflow_task.apply_async(
        args=[task.id, payload.issue_url, payload.repo_url, github_user_id],
        queue="main_queue",
    )

    return WorkflowSubmitResponse(
        task_id=task.id,
        task_uuid=task.uuid,
        status=task.status.value,
        message="Task queued successfully.",
    )


@router.get("/{task_uuid}/status", response_model=TaskStatusResponse)
def get_task_status(task_uuid: str, request: Request, db: Session = Depends(get_db)):
    """Poll task status by UUID."""
    task_repo = TaskRepository(db)
    task = task_repo.get_by_uuid(task_uuid)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    assert_task_visible(task, request, db)

    return TaskStatusResponse(
        task_id=task.id,
        task_uuid=task.uuid,
        status=task.status.value,
        current_step=task.current_step,
        retry_count=task.retry_count,
        result_pr_url=task.result_pr_url,
        error=task.error,
    )


@router.post("/{task_uuid}/retry", dependencies=rate_limit_dep(times=10))
def retry_task(task_uuid: str, request: Request, db: Session = Depends(get_db)):
    """Manually retry a failed task."""
    from app.tasks.retry_tasks import retry_failed_task
    task_repo = TaskRepository(db)
    task = task_repo.get_by_uuid(task_uuid)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    assert_task_visible(task, request, db)
    if task.status != TaskStatus.failed:
        raise HTTPException(status_code=400, detail="Only failed tasks can be retried.")

    retry_failed_task.apply_async(args=[task.id], queue="retry_queue")
    return {"message": "Retry queued."}
