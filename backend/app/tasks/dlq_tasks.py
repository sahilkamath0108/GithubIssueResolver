from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.repositories.dlq_repo import DLQRepository
from app.repositories.log_repo import LogRepository


@celery_app.task(name="app.tasks.dlq_tasks.inspect_dlq")
def inspect_dlq():
    """
    Periodic task — logs DLQ entries for monitoring.
    Can be extended to alert or auto-retry based on rules.
    """
    db = SessionLocal()
    dlq_repo = DLQRepository(db)

    try:
        entries = dlq_repo.get_all()
        for entry in entries:
            print(f"[DLQ] id={entry.id} step={entry.failed_step} error={entry.error} retries={entry.retry_count}")
    finally:
        db.close()
