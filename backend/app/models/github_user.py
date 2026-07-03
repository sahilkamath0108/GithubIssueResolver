from sqlalchemy import Column, BigInteger, Text, VARCHAR, TIMESTAMP
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.session import Base


class GitHubUser(Base):
    __tablename__ = "github_users"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    github_id = Column(BigInteger, unique=True, nullable=False, index=True)
    login = Column(VARCHAR(255), nullable=False)
    avatar_url = Column(Text, nullable=True)
    access_token_encrypted = Column(Text, nullable=False)
    token_scope = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())

    tasks = relationship("Task", back_populates="github_user")
