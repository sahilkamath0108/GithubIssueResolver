import hashlib
import hmac
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from uuid import UUID

from app.api.deps import get_db
from app.core.security import require_webhook_secret
from app.core.settings import settings
from app.repositories.task_repo import TaskRepository
from app.schemas.workflow import WorkflowSubmitResponse
from app.services import github_service
from app.tasks.workflow_tasks import run_workflow_task

logger = logging.getLogger(__name__)

router = APIRouter()


def _verify_github_signature(secret: str, body: bytes, signature_header: str | None) -> None:
    if not secret:
        if settings.REQUIRE_WEBHOOK_SECRET or settings.is_production:
            raise HTTPException(
                status_code=503,
                detail="GITHUB_WEBHOOK_SECRET is required but not configured.",
            )
        return
    if not signature_header or not signature_header.startswith("sha256="):
        raise HTTPException(status_code=401, detail="Missing X-Hub-Signature-256.")
    their_sig = signature_header.split("=", 1)[1].strip()
    mac = hmac.new(secret.encode("utf-8"), msg=body, digestmod=hashlib.sha256)
    our_sig = mac.hexdigest()
    if not hmac.compare_digest(our_sig, their_sig):
        raise HTTPException(status_code=401, detail="Invalid webhook signature.")


@router.post("/github/issues", response_model=WorkflowSubmitResponse)
async def github_issues_webhook(request: Request, db: Session = Depends(get_db)):
    """GitHub 'issues' webhook — signature + delivery dedup; queues workflow on open/reopen."""
    require_webhook_secret()

    event = request.headers.get("X-GitHub-Event", "")
    if event and event != "issues":
        raise HTTPException(status_code=400, detail=f"Unsupported event: {event}")

    delivery_id = request.headers.get("X-GitHub-Delivery", "")
    if delivery_id and not github_service.record_webhook_delivery(delivery_id):
        return WorkflowSubmitResponse(
            task_id=0,
            task_uuid=UUID("00000000-0000-0000-0000-000000000000"),
            status="ignored",
            message=f"Duplicate delivery {delivery_id} — skipped.",
        )

    body = await request.body()
    _verify_github_signature(
        settings.GITHUB_WEBHOOK_SECRET,
        body,
        request.headers.get("X-Hub-Signature-256"),
    )

    import json

    payload = json.loads(body)
    action = payload.get("action")
    allowed_actions = {"opened", "reopened"}
    if action not in allowed_actions:
        return WorkflowSubmitResponse(
            task_id=0,
            task_uuid=UUID("00000000-0000-0000-0000-000000000000"),
            status="ignored",
            message=f"Ignored issues webhook action: {action}",
        )

    issue = payload.get("issue") or {}
    repo = payload.get("repository") or {}

    issue_url = issue.get("html_url")
    repo_url = repo.get("html_url")

    if not isinstance(issue_url, str) or not isinstance(repo_url, str):
        raise HTTPException(status_code=400, detail="Missing issue.html_url or repository.html_url in payload.")

    try:
        github_service.assert_issue_matches_repo(issue_url, repo_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    task_repo = TaskRepository(db)
    task = task_repo.create(issue_url=issue_url, repo_url=repo_url)

    run_workflow_task.apply_async(args=[task.id, issue_url, repo_url], queue="main_queue")

    logger.info(
        "Webhook enqueued workflow task",
        extra={"task_id": task.id, "task_uuid": str(task.uuid), "issue_url": issue_url, "action": action},
    )

    return WorkflowSubmitResponse(
        task_id=task.id,
        task_uuid=task.uuid,
        status=task.status.value,
        message=f"Webhook accepted ({action}); task queued.",
    )
