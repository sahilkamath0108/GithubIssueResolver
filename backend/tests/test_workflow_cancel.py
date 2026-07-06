from unittest.mock import MagicMock, patch

import pytest

from app.domain.workflow_exceptions import TaskNotCancellableError
from app.models.task import Task, TaskStatus
from app.services.workflow_cancel_service import cancel_workflow_task


def test_cancel_workflow_task_revokes_celery_and_marks_cancelled():
    task = Task(id=1, issue_url="https://github.com/o/r/issues/1", repo_url="https://github.com/o/r")
    task.status = TaskStatus.running
    task.celery_task_id = "celery-abc"

    task_repo = MagicMock()
    log_repo = MagicMock()
    task_repo.cancel.return_value = task

    with patch("app.services.workflow_cancel_service.celery_app.control.revoke") as revoke:
        result = cancel_workflow_task(task, task_repo=task_repo, log_repo=log_repo)

    revoke.assert_called_once_with("celery-abc", terminate=True, signal="SIGTERM")
    task_repo.cancel.assert_called_once_with(1)
    log_repo.info.assert_called_once()
    assert result is task


def test_cancel_rejects_completed_task():
    task = Task(id=2, issue_url="https://github.com/o/r/issues/2", repo_url="https://github.com/o/r")
    task.status = TaskStatus.success
    with pytest.raises(TaskNotCancellableError):
        cancel_workflow_task(task, task_repo=MagicMock(), log_repo=MagicMock())
