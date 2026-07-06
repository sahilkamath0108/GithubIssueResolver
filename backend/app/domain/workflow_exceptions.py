class WorkflowCancelledError(Exception):
    """Raised when a workflow task was cancelled by the user."""


class TaskNotCancellableError(ValueError):
    """Raised when cancel is requested for a task that is not queued or running."""
