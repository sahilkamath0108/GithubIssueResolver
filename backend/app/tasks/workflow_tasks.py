from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.repositories.task_repo import TaskRepository
from app.repositories.log_repo import LogRepository
from app.repositories.dlq_repo import DLQRepository
from app.models.task import TaskStatus
from app.domain.graph.workflow_graph import run_workflow


@celery_app.task(name="app.tasks.workflow_tasks.run_workflow_task", bind=True)
def run_workflow_task(self, task_id: int, issue_url: str, repo_url: str):
    """
    Main Celery task — orchestrates the full agent workflow.
    Handles DB state updates and DLQ on failure.
    """
    db = SessionLocal()
    task_repo = TaskRepository(db)
    log_repo = LogRepository(db)
    dlq_repo = DLQRepository(db)

    try:
        task_repo.update_status(task_id, TaskStatus.running, current_step="planning")
        log_repo.info(task_id, "Workflow started", {"issue_url": issue_url})
        db.commit()

        final_state = run_workflow(task_id, issue_url, repo_url)

        if final_state.get("failed"):
            reason = final_state.get("failure_reason", "Unknown failure")
            task_repo.update_status(task_id, TaskStatus.failed, error=reason)
            log_repo.error(task_id, "Workflow failed — sent to DLQ", {"reason": reason})
            dlq_repo.create(
                original_task_id=str(task_id),
                payload={"issue_url": issue_url, "repo_url": repo_url},
                failed_step=final_state.get("error_type", "unknown"),
                error=reason,
                retry_count=final_state.get("retry_count", 0),
            )
        else:
            pr_url = final_state.get("pr_url")
            task_repo.set_pr_url(task_id, pr_url)
            task_repo.update_status(task_id, TaskStatus.success, current_step="completed")
            log_repo.info(task_id, "Workflow completed", {"pr_url": pr_url})

        db.commit()

    except Exception as exc:
        db.rollback()
        task_repo.update_status(task_id, TaskStatus.failed, error=str(exc))
        log_repo.error(task_id, f"Unexpected error: {exc}")
        db.commit()
        raise self.retry(exc=exc, countdown=30, max_retries=1)
    finally:
        db.close()
