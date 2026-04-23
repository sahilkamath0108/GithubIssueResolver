from typing import Literal

from pydantic import BaseModel, Field


class RepoSyncRequest(BaseModel):
    repo: str = Field(..., description='GitHub repository in "owner/name" form')
    force_full: bool = Field(
        False,
        description="If true, clears all vectors for this repo in Qdrant and reindexes every file.",
    )


class RepoIndexResponse(BaseModel):
    repo: str
    mode: Literal["full", "incremental", "skipped"]
    commit_sha: str
    files_indexed: int = 0
    chunks_written: int = 0
    files_deleted: int = 0
    files_skipped_unchanged: int = 0
    message: str = ""
