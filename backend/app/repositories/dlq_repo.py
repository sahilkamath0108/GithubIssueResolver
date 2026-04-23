from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.dlq_task import DLQTask


class DLQRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, original_task_id: str, payload: dict, failed_step: str, error: str, retry_count: int = 0) -> DLQTask:
        dlq = DLQTask(
            original_task_id=original_task_id,
            payload=payload,
            failed_step=failed_step,
            error=error,
            retry_count=retry_count,
        )
        self.db.add(dlq)
        self.db.commit()
        self.db.refresh(dlq)
        return dlq

    def get_all(self) -> List[DLQTask]:
        return self.db.query(DLQTask).order_by(DLQTask.failed_at.desc()).all()

    def get_by_uuid(self, uuid: str) -> Optional[DLQTask]:
        return self.db.query(DLQTask).filter(DLQTask.uuid == uuid).first()
