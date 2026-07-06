"""Cancel queued or running workflow Celery jobs."""

from __future__ import annotations

from app.core.celery_app import celery_app
from app.domain.workflow_exceptions import TaskNotCancellableError
from app.models.task import Task, TaskStatus
from app.repositories.log_repo import LogRepository
from app.repositories.task_repo import TaskRepository


def cancel_workflow_task(
    task: Task,
    *,
    task_repo: TaskRepository,
    log_repo: LogRepository,
) -> Task:
    if task.status not in (TaskStatus.queued, TaskStatus.running):
        raise TaskNotCancellableError(
            f"Task {task.uuid} cannot be cancelled (status={task.status.value})."
        )

    if task.celery_task_id:
        celery_app.control.revoke(task.celery_task_id, terminate=True, signal="SIGTERM")

    updated = task_repo.cancel(task.id)
    if not updated:
        raise TaskNotCancellableError(f"Task {task.uuid} not found.")

    log_repo.info(
        task.id,
        "Workflow cancelled by user",
        {"celery_task_id": task.celery_task_id},
    )
    return updated
