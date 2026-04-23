import uuid
import enum
from sqlalchemy import Column, BigInteger, Text, Integer, VARCHAR, TIMESTAMP, Enum as SAEnum, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func, text
from app.db.session import Base


class TaskStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    success = "success"
    failed = "failed"


class Task(Base):
    __tablename__ = "tasks"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    uuid = Column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4)
    issue_url = Column(Text, nullable=False)
    repo_url = Column(Text, nullable=False)
    status = Column(SAEnum(TaskStatus), nullable=False, default=TaskStatus.queued)
    current_step = Column(VARCHAR(255), nullable=False, default="")
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    result_pr_url = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())

    steps = relationship("TaskStep", back_populates="task", cascade="all, delete-orphan")
    logs = relationship("TaskLog", back_populates="task", cascade="all, delete-orphan")
    result = relationship("TaskResult", back_populates="task", uselist=False, cascade="all, delete-orphan")
    workflow_state = relationship("WorkflowState", back_populates="task", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_tasks_status_created", "status", text("created_at DESC")),
    )
