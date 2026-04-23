from sqlalchemy import Column, BigInteger, Text, TIMESTAMP, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base


class TaskResult(Base):
    __tablename__ = "task_results"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    task_id = Column(BigInteger, ForeignKey("tasks.id", ondelete="CASCADE"), unique=True, nullable=False)
    generated_code = Column(JSONB, nullable=True)
    test_cases = Column(JSONB, nullable=True)
    summary = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())

    task = relationship("Task", back_populates="result")

    __table_args__ = (
        Index("idx_results_task_id", "task_id", unique=True),
    )
