from app.domain.state.workflow_state import WorkflowStateSchema
from app.domain.agents.planner import PlannerAgent
from app.domain.agents.code_writer import CodeWriterAgent
from app.domain.agents.fix_agent import FixAgent
from app.services import github_service
from app.services import qdrant_search_service
from app.services.code_context_service import build_context
from app.indexing.indexer import RepoIndexer
from app.db.session import SessionLocal
from app.repositories.task_repo import TaskRepository
from app.repositories.log_repo import LogRepository
from app.models.task import TaskStatus

_planner = PlannerAgent()
_code_writer = CodeWriterAgent()
_fix_agent = FixAgent()


def _get_repos():
    """Create a fresh DB session + repos for each node call."""
    db = SessionLocal()
    return db, TaskRepository(db), LogRepository(db)


def node_plan(state: dict) -> dict:
    """LLM node — plan what to change."""
    ws = WorkflowStateSchema(**state)
    db, task_repo, log_repo = _get_repos()
    try:
        task_repo.update_status(ws.task_id, TaskStatus.running, current_step="planning")
        log_repo.info(ws.task_id, "Planner agent started")
        db.commit()

        issue = github_service.get_issue(ws.issue_url)
        ws = _planner.run(ws, issue)

        log_repo.info(ws.task_id, "Plan created", {"plan": ws.plan})
        db.commit()
    finally:
        db.close()
    return ws.model_dump()


def node_read_code(state: dict) -> dict:
    """Deterministic node — ensure repo index, fetch repo files, resolve deps, retrieve context."""
    ws = WorkflowStateSchema(**state)
    db, task_repo, log_repo = _get_repos()
    try:
        task_repo.update_status(ws.task_id, TaskStatus.running, current_step="reading_code")
        log_repo.info(ws.task_id, "Fetching and indexing repo files")
        db.commit()

        # Ensure Qdrant repo index is up-to-date (full / incremental / skip)
        repo_name = github_service.repo_full_name(ws.repo_url)
        indexer = RepoIndexer(db)
        try:
            sync_result = indexer.sync_repo(repo_name)
            log_repo.info(
                ws.task_id,
                "Repo index synced",
                {
                    "repo": repo_name,
                    "mode": sync_result.mode,
                    "commit_sha": sync_result.commit_sha,
                    "files_indexed": sync_result.files_indexed,
                    "files_deleted": sync_result.files_deleted,
                },
            )
            db.commit()
        finally:
            indexer.close()

        # Fetch all repo files — cached by repo URL + commit SHA
        files = github_service.get_repo_files_cached(ws.repo_url)
        ws.repo_files = files

        # Vector search — find semantically relevant chunks
        query = ws.plan.get("search_query", " ".join(ws.plan.get("changes", [])))
        vector_chunks = qdrant_search_service.search_relevant_chunks(repo_name, query)

        # Planned files from planner output
        planned_paths = ws.plan.get("files_to_modify", [])

        # Build full context: planned files + their deps + vector results
        ws.relevant_chunks = build_context(planned_paths, vector_chunks, files)

        log_repo.info(
            ws.task_id,
            f"Context built: {len(ws.relevant_chunks)} files (planned + deps + vector)",
            {"files": [c["path"] for c in ws.relevant_chunks]},
        )
        db.commit()
    finally:
        db.close()
    return ws.model_dump()


def node_write_code(state: dict) -> dict:
    """LLM node — generate code using plan + relevant chunks only."""
    ws = WorkflowStateSchema(**state)
    db, task_repo, log_repo = _get_repos()
    try:
        task_repo.update_status(ws.task_id, TaskStatus.running, current_step="writing_code")
        log_repo.info(ws.task_id, "Code writer agent started")
        db.commit()

        ws = _code_writer.run(ws)

        log_repo.info(ws.task_id, "Code generated", {"files": list((ws.generated_code or {}).keys())})
        db.commit()
    finally:
        db.close()
    return ws.model_dump()


def node_execute(state: dict) -> dict:
    """Deterministic node — run tests in Docker, no LLM."""
    from app.infrastructure.docker.docker_executor import run_tests
    ws = WorkflowStateSchema(**state)
    db, task_repo, log_repo = _get_repos()
    try:
        task_repo.update_status(ws.task_id, TaskStatus.running, current_step="executing_tests")
        log_repo.info(ws.task_id, "Running tests in Docker")
        db.commit()

        output, passed = run_tests(ws.generated_code)
        ws.test_output = output
        ws.test_passed = passed

        level = "INFO" if passed else "ERROR"
        log_repo.create(ws.task_id, level, f"Tests {'passed' if passed else 'failed'}", {"output": output[:500]})
        db.commit()
    finally:
        db.close()
    return ws.model_dump()


def node_fix(state: dict) -> dict:
    """LLM node — fix code based on precise error, limited retries."""
    ws = WorkflowStateSchema(**state)
    db, task_repo, log_repo = _get_repos()
    try:
        task_repo.update_status(ws.task_id, TaskStatus.running, current_step=f"fixing_retry_{ws.retry_count + 1}")
        log_repo.info(ws.task_id, f"Fix agent started (retry {ws.retry_count + 1})", {"error_type": ws.error_type})
        db.commit()

        ws = _fix_agent.run(ws)

        log_repo.info(ws.task_id, "Fix applied")
        db.commit()
    finally:
        db.close()
    return ws.model_dump()


def node_create_pr(state: dict) -> dict:
    """Deterministic node — commit changes and open PR."""
    ws = WorkflowStateSchema(**state)
    db, task_repo, log_repo = _get_repos()
    try:
        task_repo.update_status(ws.task_id, TaskStatus.running, current_step="creating_pr")
        log_repo.info(ws.task_id, "Creating PR on GitHub")
        db.commit()

        branch = f"agent/fix-task-{ws.task_id}-r{ws.retry_count}-{int(__import__('time').time())}"
        for file_path, content in (ws.generated_code or {}).items():
            github_service.create_branch_and_commit(
                ws.repo_url, branch, file_path, content,
                commit_message=f"fix: agent patch for task {ws.task_id}",
            )
        pr_url = github_service.create_pull_request(
            ws.repo_url, branch,
            title=f"Agent Fix: Task {ws.task_id}",
            body=f"Automated fix generated by multi-agent system.\n\nTask: {ws.task_id}",
        )
        ws.pr_url = pr_url

        log_repo.info(ws.task_id, "PR created", {"pr_url": pr_url})
        db.commit()
    finally:
        db.close()
    return ws.model_dump()


def node_send_to_dlq(state: dict) -> dict:
    """Terminal failure node — mark as failed for DLQ processing."""
    ws = WorkflowStateSchema(**state)
    db, task_repo, log_repo = _get_repos()
    try:
        ws.failed = True
        ws.failure_reason = f"Max retries exceeded. Last error: {ws.test_output}"

        task_repo.update_status(ws.task_id, TaskStatus.failed, error=ws.failure_reason)
        log_repo.error(ws.task_id, "Max retries exceeded — sent to DLQ")
        db.commit()
    finally:
        db.close()
    return ws.model_dump()


# --- Routing logic (pure functions, no LLM) ---

def route_after_execute(state: dict) -> str:
    ws = WorkflowStateSchema(**state)
    if ws.test_passed:
        return "create_pr"
    if ws.retry_count < ws.max_retries:
        return "fix"
    return "dlq"
