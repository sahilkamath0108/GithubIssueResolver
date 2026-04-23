import uuid
import enum
from sqlalchemy import Column, BigInteger, VARCHAR, Text, TIMESTAMP, Enum as SAEnum, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import text
from app.db.session import Base


class StepStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"


class TaskStep(Base):
    __tablename__ = "task_steps"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    uuid = Column(UUID(as_uuid=True), unique=True, nullable=True, default=uuid.uuid4)
    task_id = Column(BigInteger, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    step_name = Column(VARCHAR(255), nullable=False)
    status = Column(SAEnum(StepStatus), nullable=False, default=StepStatus.pending)
    input = Column(JSONB, nullable=True)
    output = Column(JSONB, nullable=True)
    error = Column(Text, nullable=True)
    started_at = Column(TIMESTAMP, nullable=True)
    completed_at = Column(TIMESTAMP, nullable=True)

    task = relationship("Task", back_populates="steps")

    __table_args__ = (
        Index("idx_steps_task_status", "task_id", "status"),
        Index("idx_steps_task_time", "task_id", text("started_at DESC")),
    )
