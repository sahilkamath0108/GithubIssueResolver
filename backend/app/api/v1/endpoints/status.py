from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db, resolve_auth_context
from app.core.settings import settings
from app.repositories.task_repo import TaskRepository
from app.models.task import TaskStatus

router = APIRouter()


@router.get("/tasks")
def list_tasks_by_status(
    request: Request,
    status: str | None = None,
    limit: int = Query(default=None, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """List tasks with pagination, optionally filtered by status."""
    ctx = resolve_auth_context(request, db)
    task_repo = TaskRepository(db)
    cap = min(limit or settings.TASK_LIST_DEFAULT_LIMIT, settings.TASK_LIST_MAX_LIMIT)

    task_status = None
    if status:
        try:
            task_status = TaskStatus(status)
        except ValueError:
            return {"error": f"Invalid status: {status}"}

    github_user_id = None
    if settings.oauth_enabled and ctx.user is not None and not ctx.is_service_account:
        github_user_id = ctx.user.id

    tasks = task_repo.list_recent(
        status=task_status,
        github_user_id=github_user_id,
        limit=cap,
        offset=offset,
    )

    return {
        "items": [
            {
                "id": t.id,
                "uuid": str(t.uuid),
                "status": t.status.value,
                "current_step": t.current_step,
                "issue_url": t.issue_url,
                "created_at": t.created_at.isoformat(),
            }
            for t in tasks
        ],
        "limit": cap,
        "offset": offset,
        "count": len(tasks),
    }
