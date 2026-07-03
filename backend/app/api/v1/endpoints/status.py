from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.settings import settings
from app.repositories.task_repo import TaskRepository
from app.models.task import TaskStatus

router = APIRouter()


@router.get("/tasks")
def list_tasks_by_status(
    status: str | None = None,
    limit: int = Query(default=None, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """List tasks with pagination, optionally filtered by status."""
    task_repo = TaskRepository(db)
    cap = min(limit or settings.TASK_LIST_DEFAULT_LIMIT, settings.TASK_LIST_MAX_LIMIT)

    task_status = None
    if status:
        try:
            task_status = TaskStatus(status)
        except ValueError:
            return {"error": f"Invalid status: {status}"}

    tasks = task_repo.list_recent(status=task_status, limit=cap, offset=offset)

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
