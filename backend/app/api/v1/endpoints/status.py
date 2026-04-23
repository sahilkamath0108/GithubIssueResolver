from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.repositories.task_repo import TaskRepository
from app.models.task import TaskStatus

router = APIRouter()


@router.get("/tasks")
def list_tasks_by_status(status: str = None, db: Session = Depends(get_db)):
    """List tasks, optionally filtered by status."""
    task_repo = TaskRepository(db)
    if status:
        try:
            task_status = TaskStatus(status)
        except ValueError:
            return {"error": f"Invalid status: {status}"}
        tasks = task_repo.list_by_status(task_status)
    else:
        tasks = db.query(__import__("app.models.task", fromlist=["Task"]).Task).all()

    return [
        {
            "id": t.id,
            "uuid": str(t.uuid),
            "status": t.status.value,
            "current_step": t.current_step,
            "issue_url": t.issue_url,
            "created_at": t.created_at.isoformat(),
        }
        for t in tasks
    ]
