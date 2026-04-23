from typing import Optional, List
from pydantic import BaseModel


class WorkflowStateSchema(BaseModel):
    """
    Shared state passed between all LangGraph nodes.
    Each agent reads from and writes to this state.
    """
    task_id: int
    issue_url: str
    repo_url: str

    # Populated by planner agent
    plan: Optional[dict] = None

    # Populated by code reader (deterministic)
    repo_files: Optional[List[dict]] = None
    relevant_chunks: Optional[List[dict]] = None

    # Populated by code writer agent
    generated_code: Optional[dict] = None  # {file_path: new_content}

    # Populated by docker executor
    test_output: Optional[str] = None
    test_passed: Optional[bool] = None

    # Error handling
    error_type: Optional[str] = None   # e.g. ImportError, AssertionError
    retry_count: int = 0
    max_retries: int = 2

    # Final output
    pr_url: Optional[str] = None
    failed: bool = False
    failure_reason: Optional[str] = None
