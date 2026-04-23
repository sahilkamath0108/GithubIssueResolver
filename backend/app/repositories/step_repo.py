from typing import Optional, List
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.task_step import TaskStep, StepStatus


class StepRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, task_id: int, step_name: str, input_data: dict = None) -> TaskStep:
        step = TaskStep(
            task_id=task_id,
            step_name=step_name,
            status=StepStatus.pending,
            input=input_data,
        )
        self.db.add(step)
        self.db.commit()
        self.db.refresh(step)
        return step

    def start(self, step_id: int) -> Optional[TaskStep]:
        step = self.db.query(TaskStep).filter(TaskStep.id == step_id).first()
        if not step:
            return None
        step.status = StepStatus.running
        step.started_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(step)
        return step

    def complete(self, step_id: int, output: dict = None) -> Optional[TaskStep]:
        step = self.db.query(TaskStep).filter(TaskStep.id == step_id).first()
        if not step:
            return None
        step.status = StepStatus.success
        step.output = output
        step.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(step)
        return step

    def fail(self, step_id: int, error: str) -> Optional[TaskStep]:
        step = self.db.query(TaskStep).filter(TaskStep.id == step_id).first()
        if not step:
            return None
        step.status = StepStatus.failed
        step.error = error
        step.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(step)
        return step

    def get_by_task(self, task_id: int) -> List[TaskStep]:
        return self.db.query(TaskStep).filter(TaskStep.task_id == task_id).all()
