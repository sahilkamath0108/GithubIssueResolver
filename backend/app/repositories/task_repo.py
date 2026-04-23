from typing import Optional, List
from sqlalchemy.orm import Session
from app.models.task import Task, TaskStatus


class TaskRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, issue_url: str, repo_url: str) -> Task:
        task = Task(issue_url=issue_url, repo_url=repo_url)
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def get_by_id(self, task_id: int) -> Optional[Task]:
        return self.db.query(Task).filter(Task.id == task_id).first()

    def get_by_uuid(self, uuid: str) -> Optional[Task]:
        return self.db.query(Task).filter(Task.uuid == uuid).first()

    def update_status(self, task_id: int, status: TaskStatus, current_step: str = None, error: str = None) -> Optional[Task]:
        task = self.get_by_id(task_id)
        if not task:
            return None
        task.status = status
        if current_step is not None:
            task.current_step = current_step
        if error is not None:
            task.error = error
        self.db.commit()
        self.db.refresh(task)
        return task

    def increment_retry(self, task_id: int) -> Optional[Task]:
        task = self.get_by_id(task_id)
        if not task:
            return None
        task.retry_count += 1
        self.db.commit()
        self.db.refresh(task)
        return task

    def set_pr_url(self, task_id: int, pr_url: str) -> Optional[Task]:
        task = self.get_by_id(task_id)
        if not task:
            return None
        task.result_pr_url = pr_url
        self.db.commit()
        self.db.refresh(task)
        return task

    def list_by_status(self, status: TaskStatus) -> List[Task]:
        return self.db.query(Task).filter(Task.status == status).all()
