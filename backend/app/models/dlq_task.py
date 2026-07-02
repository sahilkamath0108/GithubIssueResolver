import uuid
from sqlalchemy import Column, BigInteger, VARCHAR, Text, Integer, TIMESTAMP, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func, text
from app.db.session import Base


class DLQTask(Base):
    __tablename__ = "dlq_tasks"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    uuid = Column(UUID(as_uuid=True), unique=True, nullable=True, default=uuid.uuid4)
    # Store the originating Task.id (integer) as text to avoid UUID casting errors.
    original_task_id = Column(Text, nullable=True)
    payload = Column(JSONB, nullable=False)
    failed_step = Column(VARCHAR(255), nullable=True)
    error = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=True, default=0)
    failed_at = Column(TIMESTAMP, nullable=False, server_default=func.now())


    __table_args__ = (
        Index("idx_dlq_failed_at", text("failed_at DESC")),
    )
