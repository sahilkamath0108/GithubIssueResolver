from sqlalchemy import Column, BigInteger, TIMESTAMP, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base


class WorkflowState(Base):
    __tablename__ = "workflow_states"

    task_id = Column(BigInteger, ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True)
    issue = Column(JSONB, nullable=True)
    plan = Column(JSONB, nullable=True)
    context = Column(JSONB, nullable=True)
    generated_code = Column(JSONB, nullable=True)
    test_results = Column(JSONB, nullable=True)
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())

    task = relationship("Task", back_populates="workflow_state")

    __table_args__ = (
        Index("idx_workflow_task_id", "task_id", unique=True),
    )
