from sqlalchemy import Column, BigInteger, VARCHAR, Text, TIMESTAMP, ForeignKey, Index, PrimaryKeyConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func, text
from app.db.session import Base


class TaskLog(Base):
    __tablename__ = "task_logs"

    id = Column(BigInteger, autoincrement=True, nullable=False)
    task_id = Column(BigInteger, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    level = Column(VARCHAR(20), nullable=False)  # INFO, ERROR, DEBUG
    message = Column(Text, nullable=False)
    log_metadata = Column("metadata", JSONB, nullable=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())

    task = relationship("Task", back_populates="logs")

    __table_args__ = (
        PrimaryKeyConstraint("id", "created_at"),
        Index("idx_logs_task_created", "task_id", text("created_at DESC")),
        {"postgresql_partition_by": "RANGE (created_at)"},
    )
