from app.core.celery_app import celery_app
from app.core.settings import settings
from app.db.session import SessionLocal
from app.repositories.task_repo import TaskRepository
from app.repositories.log_repo import LogRepository
from app.repositories.dlq_repo import DLQRepository
from app.models.task import TaskStatus
from app.domain.graph.workflow_graph import run_workflow


def _write_dlq(
    db,
    dlq_repo: DLQRepository,
    task_id: int,
    issue_url: str,
    repo_url: str,
    failed_step: str,
    error: str,
    retry_count: int = 0,
) -> None:
    dlq_repo.create(
        original_task_id=str(task_id),
        payload={"issue_url": issue_url, "repo_url": repo_url},
        failed_step=failed_step,
        error=error,
        retry_count=retry_count,
    )


@celery_app.task(name="app.tasks.workflow_tasks.run_workflow_task", bind=True, max_retries=0)
def run_workflow_task(self, task_id: int, issue_url: str, repo_url: str):
    """
    Main Celery task — orchestrates the full agent workflow.
    All failure paths write to DLQ.
    """
    db = SessionLocal()
    task_repo = TaskRepository(db)
    log_repo = LogRepository(db)
    dlq_repo = DLQRepository(db)

    try:
        task_repo.update_status(task_id, TaskStatus.running, current_step="planning")
        log_repo.info(task_id, "Workflow started", {"issue_url": issue_url})
        db.commit()

        final_state = run_workflow(
            task_id,
            issue_url,
            repo_url,
            max_retries=settings.MAX_RETRIES,
        )

        if final_state.get("failed"):
            reason = final_state.get("failure_reason", "Unknown failure")
            step = final_state.get("error_type", final_state.get("failed_step", "unknown"))
            task_repo.update_status(task_id, TaskStatus.failed, error=reason)
            log_repo.error(task_id, "Workflow failed — sent to DLQ", {"reason": reason, "step": step})
            _write_dlq(db, dlq_repo, task_id, issue_url, repo_url, step, reason, final_state.get("retry_count", 0))
        else:
            pr_url = final_state.get("pr_url")
            task_repo.set_pr_url(task_id, pr_url)
            task_repo.update_status(task_id, TaskStatus.success, current_step="completed")
            log_repo.info(task_id, "Workflow completed", {"pr_url": pr_url})

        db.commit()

    except Exception as exc:
        db.rollback()
        reason = str(exc)
        task_repo.update_status(task_id, TaskStatus.failed, error=reason)
        log_repo.error(task_id, f"Unexpected workflow error: {exc}")
        _write_dlq(db, dlq_repo, task_id, issue_url, repo_url, "celery_exception", reason)
        db.commit()
        raise
    finally:
        db.close()
