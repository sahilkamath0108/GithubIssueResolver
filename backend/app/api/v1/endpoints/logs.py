from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.repositories.log_repo import LogRepository
from app.repositories.task_repo import TaskRepository

router = APIRouter()


@router.get("/{task_uuid}/logs")
def get_task_logs(task_uuid: str, db: Session = Depends(get_db)):
    """Fetch all logs for a task."""
    task_repo = TaskRepository(db)
    task = task_repo.get_by_uuid(task_uuid)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")

    log_repo = LogRepository(db)
    logs = log_repo.get_by_task(task.id)

    return [
        {
            "level": l.level,
            "message": l.message,
            "metadata": l.log_metadata,
            "created_at": l.created_at.isoformat(),
        }
        for l in logs
    ]
