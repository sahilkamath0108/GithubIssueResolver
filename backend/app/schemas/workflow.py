from pydantic import BaseModel, HttpUrl
from typing import Optional
from uuid import UUID


class WorkflowSubmitRequest(BaseModel):
    issue_url: str
    repo_url: str


class WorkflowSubmitResponse(BaseModel):
    task_id: int
    task_uuid: UUID
    status: str
    message: str


class TaskStatusResponse(BaseModel):
    task_id: int
    task_uuid: UUID
    status: str
    current_step: str
    retry_count: int
    result_pr_url: Optional[str] = None
    error: Optional[str] = None
