from sqlalchemy import Column, BigInteger, Text, VARCHAR, TIMESTAMP, UniqueConstraint
from sqlalchemy.sql import func
from app.db.session import Base


class RepoIndexState(Base):
    """
    Tracks the last successfully indexed commit for a GitHub repo (owner/repo).
    Used to drive incremental indexing without cloning.
    """

    __tablename__ = "repo_index_state"
    __table_args__ = (UniqueConstraint("repo_full_name", name="uq_repo_index_state_repo"),)

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    repo_full_name = Column(VARCHAR(255), nullable=False, index=True)
    commit_sha = Column(VARCHAR(64), nullable=False)
    embedding_model = Column(VARCHAR(128), nullable=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())
