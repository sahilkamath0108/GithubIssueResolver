from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.repositories.task_repo import TaskRepository
from app.repositories.log_repo import LogRepository
from app.models.task import TaskStatus
from app.tasks.workflow_tasks import run_workflow_task


@celery_app.task(name="app.tasks.retry_tasks.retry_failed_task")
def retry_failed_task(task_id: int):
    """
    Retry a failed task — resets status and re-queues workflow.
    """
    db = SessionLocal()
    task_repo = TaskRepository(db)
    log_repo = LogRepository(db)

    try:
        task = task_repo.get_by_id(task_id)
        if not task:
            return

        task_repo.update_status(task_id, TaskStatus.queued, current_step="retrying")
        task_repo.increment_retry(task_id)
        log_repo.info(task_id, f"Manual retry triggered (attempt {task.retry_count + 1})")

        run_workflow_task.apply_async(
            args=[task_id, task.issue_url, task.repo_url],
            queue="main_queue",
        )
    finally:
        db.close()
