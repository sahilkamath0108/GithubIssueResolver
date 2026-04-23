from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.repositories.task_repo import TaskRepository
from app.schemas.workflow import WorkflowSubmitRequest, WorkflowSubmitResponse, TaskStatusResponse
from app.models.task import TaskStatus
from app.tasks.workflow_tasks import run_workflow_task

router = APIRouter()


@router.post("/submit", response_model=WorkflowSubmitResponse)
def submit_workflow(payload: WorkflowSubmitRequest, db: Session = Depends(get_db)):
    """Submit a GitHub issue for agent processing."""
    task_repo = TaskRepository(db)
    task = task_repo.create(issue_url=payload.issue_url, repo_url=payload.repo_url)

    run_workflow_task.apply_async(
        args=[task.id, payload.issue_url, payload.repo_url],
        queue="main_queue",
    )

    return WorkflowSubmitResponse(
        task_id=task.id,
        task_uuid=task.uuid,
        status=task.status.value,
        message="Task queued successfully.",
    )


@router.get("/{task_uuid}/status", response_model=TaskStatusResponse)
def get_task_status(task_uuid: str, db: Session = Depends(get_db)):
    """Poll task status by UUID."""
    task_repo = TaskRepository(db)
    task = task_repo.get_by_uuid(task_uuid)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")

    return TaskStatusResponse(
        task_id=task.id,
        task_uuid=task.uuid,
        status=task.status.value,
        current_step=task.current_step,
        retry_count=task.retry_count,
        result_pr_url=task.result_pr_url,
        error=task.error,
    )


@router.post("/{task_uuid}/retry")
def retry_task(task_uuid: str, db: Session = Depends(get_db)):
    """Manually retry a failed task."""
    from app.tasks.retry_tasks import retry_failed_task
    task_repo = TaskRepository(db)
    task = task_repo.get_by_uuid(task_uuid)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    if task.status != TaskStatus.failed:
        raise HTTPException(status_code=400, detail="Only failed tasks can be retried.")

    retry_failed_task.apply_async(args=[task.id], queue="retry_queue")
    return {"message": "Retry queued."}
