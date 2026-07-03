from app.domain.state.workflow_state import WorkflowStateSchema
from app.domain.agents.planner import PlannerAgent
from app.domain.agents.code_writer import CodeWriterAgent
from app.domain.agents.fix_agent import FixAgent
from app.services import github_service
from app.services import qdrant_search_service
from app.services.code_context_service import build_context, assign_target_files
from app.core.security import sanitize_repo_path
from app.indexing.indexer import RepoIndexer
from app.core.settings import settings
from app.db.session import SessionLocal
from app.repositories.task_repo import TaskRepository
from app.repositories.log_repo import LogRepository
from app.models.task import TaskStatus
import traceback
from app.services.llm_service import get_last_llm_raw

_planner = PlannerAgent()
_code_writer = CodeWriterAgent()
_fix_agent = FixAgent()


def _get_repos():
    """Create a fresh DB session + repos for each node call."""
    db = SessionLocal()
    return db, TaskRepository(db), LogRepository(db)

def _log_node_failure(log_repo: LogRepository, task_repo: TaskRepository, task_id: int, node: str, exc: Exception):
    tb = traceback.format_exc()
    # Keep log payload bounded so it fits comfortably in DB + UI.
    tb_tail = tb[-4000:] if tb else None
    last_llm = get_last_llm_raw()
    last_llm_tail = (last_llm[-2000:] if isinstance(last_llm, str) and last_llm else None)
    log_repo.error(
        task_id,
        f"Node failed: {node}",
        {
            "node": node,
            "exc_type": type(exc).__name__,
            "error": str(exc),
            "traceback_tail": tb_tail,
            "last_llm_raw_tail": last_llm_tail,
        },
    )
    task_repo.update_status(task_id, TaskStatus.running, current_step=f"{node}_failed")


def node_plan(state: dict) -> dict:
    """LLM node — plan what to change."""
    ws = WorkflowStateSchema(**state)
    db, task_repo, log_repo = _get_repos()
    try:
        task_repo.update_status(ws.task_id, TaskStatus.running, current_step="planning")
        log_repo.info(ws.task_id, "Node started: plan")
        db.commit()

        issue = github_service.get_issue(ws.issue_url)
        ws = _planner.run(ws, issue)

        last_llm = get_last_llm_raw()
        log_repo.info(
            ws.task_id,
            "Node succeeded: plan",
            {
                "plan": ws.plan,
                "llm_raw_tail": (last_llm[-2000:] if isinstance(last_llm, str) and last_llm else None),
            },
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        _log_node_failure(log_repo, task_repo, ws.task_id, "plan", exc)
        db.commit()
        raise
    finally:
        db.close()
    return ws.model_dump()


def node_read_code(state: dict) -> dict:
    """Deterministic node — ensure repo index, fetch repo files, resolve deps, retrieve context."""
    ws = WorkflowStateSchema(**state)
    db, task_repo, log_repo = _get_repos()
    try:
        task_repo.update_status(ws.task_id, TaskStatus.running, current_step="reading_code")
        log_repo.info(ws.task_id, "Node started: read_code")
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

        # Fetch repo source files (JS/TS/Python/etc. — same extensions as indexing)
        files = github_service.get_repo_files_cached(
            ws.repo_url, extensions=settings.index_file_extensions
        )

        # Vector search in Qdrant (payload.repo = owner/name) — paths only
        query = ws.plan.get("search_query", " ".join(ws.plan.get("changes", [])))
        vector_chunks = qdrant_search_service.search_relevant_chunks(repo_name, query)

        log_repo.info(
            ws.task_id,
            "Qdrant vector search",
            {
                "repo": repo_name,
                "query": query,
                "hits": len(vector_chunks),
                "paths": [c.get("path") for c in vector_chunks],
            },
        )

        ws.plan = assign_target_files(ws.plan, vector_chunks)
        planned_paths = ws.plan.get("files_to_modify", [])

        # Ensure targets have full GitHub bodies (bulk fetch may miss paths)
        file_paths = {f["path"] for f in files}
        missing_targets = [p for p in planned_paths if p not in file_paths]
        if missing_targets:
            extra = github_service.get_file_contents(ws.repo_url, missing_targets)
            files = github_service.merge_repo_files(files, extra)
            file_paths = {f["path"] for f in files}

        still_missing = [p for p in planned_paths if p not in file_paths]
        if still_missing:
            raise RuntimeError(
                f"Could not fetch full file content from GitHub for: {still_missing}"
            )

        ws.repo_files = files

        ws.relevant_chunks = build_context(planned_paths, vector_chunks, files)

        if not ws.relevant_chunks:
            raise RuntimeError(
                f"No code context for {repo_name}. "
                "Ensure the repo is indexed in Qdrant and Ollama embeddings are reachable, "
                f"or that GitHub returned files (got {len(files)} files)."
            )

        log_repo.info(
            ws.task_id,
            f"Context built: {len(ws.relevant_chunks)} files (planned + Qdrant + deps)",
            {
                "files": [c["path"] for c in ws.relevant_chunks],
                "sources": [c.get("source") for c in ws.relevant_chunks],
                "files_to_modify": planned_paths,
            },
        )
        log_repo.info(ws.task_id, "Node succeeded: read_code", {"context_files": len(ws.relevant_chunks)})
        db.commit()
    except Exception as exc:
        db.rollback()
        _log_node_failure(log_repo, task_repo, ws.task_id, "read_code", exc)
        db.commit()
        raise
    finally:
        db.close()
    return ws.model_dump()


def node_write_code(state: dict) -> dict:
    """LLM node — generate code using plan + relevant chunks only."""
    ws = WorkflowStateSchema(**state)
    db, task_repo, log_repo = _get_repos()
    try:
        task_repo.update_status(ws.task_id, TaskStatus.running, current_step="writing_code")
        log_repo.info(ws.task_id, "Node started: write_code")
        db.commit()

        ws = _code_writer.run(ws)

        last_llm = get_last_llm_raw()
        previews: dict[str, str] = {}
        for p, c in (ws.generated_code or {}).items():
            if isinstance(c, str):
                previews[p] = c[:400]
        log_repo.info(
            ws.task_id,
            "Node succeeded: write_code",
            {
                "files": list((ws.generated_code or {}).keys()),
                "llm_raw_tail": (last_llm[-2000:] if isinstance(last_llm, str) and last_llm else None),
                "decoded_preview": previews,
            },
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        _log_node_failure(log_repo, task_repo, ws.task_id, "write_code", exc)
        db.commit()
        raise
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
        log_repo.info(ws.task_id, "Node started: execute", {"skip_tests": settings.WORKFLOW_SKIP_TESTS})
        db.commit()

        if settings.WORKFLOW_SKIP_TESTS:
            output, passed = "SKIPPED (WORKFLOW_SKIP_TESTS=true)", True
        else:
            output, passed = run_tests(ws.generated_code)
        ws.test_output = output
        ws.test_passed = passed

        level = "INFO" if passed else "ERROR"
        log_repo.create(ws.task_id, level, f"Tests {'passed' if passed else 'failed'}", {"output": output[:500]})
        log_repo.info(ws.task_id, "Node succeeded: execute", {"passed": passed})
        db.commit()
    except Exception as exc:
        db.rollback()
        _log_node_failure(log_repo, task_repo, ws.task_id, "execute", exc)
        db.commit()
        raise
    finally:
        db.close()
    return ws.model_dump()


def node_fix(state: dict) -> dict:
    """LLM node — fix code based on precise error, limited retries."""
    ws = WorkflowStateSchema(**state)
    db, task_repo, log_repo = _get_repos()
    try:
        task_repo.update_status(ws.task_id, TaskStatus.running, current_step=f"fixing_retry_{ws.retry_count + 1}")
        log_repo.info(ws.task_id, "Node started: fix", {"retry": ws.retry_count + 1, "error_type": ws.error_type})
        db.commit()

        ws = _fix_agent.run(ws)

        last_llm = get_last_llm_raw()
        log_repo.info(
            ws.task_id,
            "Node succeeded: fix",
            {"llm_raw_tail": (last_llm[-2000:] if isinstance(last_llm, str) and last_llm else None)},
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        _log_node_failure(log_repo, task_repo, ws.task_id, "fix", exc)
        db.commit()
        raise
    finally:
        db.close()
    return ws.model_dump()


def node_create_pr(state: dict) -> dict:
    """Deterministic node — commit changes and open PR."""
    ws = WorkflowStateSchema(**state)
    db, task_repo, log_repo = _get_repos()
    try:
        task_repo.update_status(ws.task_id, TaskStatus.running, current_step="creating_pr")
        log_repo.info(ws.task_id, "Node started: create_pr")
        db.commit()

        branch = f"agent/fix-task-{ws.task_id}-r{ws.retry_count}-{int(__import__('time').time())}"
        for file_path, content in (ws.generated_code or {}).items():
            safe_path = sanitize_repo_path(file_path)
            github_service.create_branch_and_commit(
                ws.repo_url, branch, safe_path, content,
                commit_message=f"fix: agent patch for task {ws.task_id}",
            )
        pr_url = github_service.create_pull_request(
            ws.repo_url, branch,
            title=f"Agent Fix: Task {ws.task_id}",
            body=f"Automated fix generated by multi-agent system.\n\nTask: {ws.task_id}",
        )
        ws.pr_url = pr_url

        log_repo.info(ws.task_id, "Node succeeded: create_pr", {"pr_url": pr_url})
        db.commit()
    except Exception as exc:
        db.rollback()
        _log_node_failure(log_repo, task_repo, ws.task_id, "create_pr", exc)
        db.commit()
        raise
    finally:
        db.close()
    return ws.model_dump()


def node_send_to_dlq(state: dict) -> dict:
    """Terminal failure node — mark failed (DLQ row written by Celery task)."""
    ws = WorkflowStateSchema(**state)
    db, task_repo, log_repo = _get_repos()
    try:
        ws.failed = True
        ws.failure_reason = ws.failure_reason or f"Max retries exceeded. Last error: {ws.test_output}"

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
