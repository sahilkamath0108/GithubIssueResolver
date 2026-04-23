from typing import List
from sqlalchemy.orm import Session
from app.models.task_log import TaskLog


class LogRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, task_id: int, level: str, message: str, metadata: dict = None) -> TaskLog:
        log = TaskLog(
            task_id=task_id,
            level=level.upper(),
            message=message,
            log_metadata=metadata,
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def info(self, task_id: int, message: str, metadata: dict = None) -> TaskLog:
        return self.create(task_id, "INFO", message, metadata)

    def error(self, task_id: int, message: str, metadata: dict = None) -> TaskLog:
        return self.create(task_id, "ERROR", message, metadata)

    def debug(self, task_id: int, message: str, metadata: dict = None) -> TaskLog:
        return self.create(task_id, "DEBUG", message, metadata)

    def get_by_task(self, task_id: int) -> List[TaskLog]:
        return (
            self.db.query(TaskLog)
            .filter(TaskLog.task_id == task_id)
            .order_by(TaskLog.created_at.desc())
            .all()
        )
