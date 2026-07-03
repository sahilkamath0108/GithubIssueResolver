from langgraph.graph import StateGraph, END
import logging

from app.core.settings import settings
from app.domain.graph.nodes import (
    node_plan, node_read_code, node_write_code,
    node_execute, node_fix, node_create_pr, node_send_to_dlq,
    route_after_execute,
)
from app.domain.state.workflow_state import WorkflowStateSchema

logger = logging.getLogger(__name__)


def build_graph() -> StateGraph:
    graph = StateGraph(dict)

    graph.add_node("plan", node_plan)
    graph.add_node("read_code", node_read_code)
    graph.add_node("write_code", node_write_code)
    graph.add_node("execute", node_execute)
    graph.add_node("fix", node_fix)
    graph.add_node("create_pr", node_create_pr)
    graph.add_node("dlq", node_send_to_dlq)

    graph.set_entry_point("plan")
    graph.add_edge("plan", "read_code")
    graph.add_edge("read_code", "write_code")
    graph.add_edge("write_code", "execute")

    graph.add_conditional_edges(
        "execute",
        route_after_execute,
        {
            "create_pr": "create_pr",
            "fix": "fix",
            "dlq": "dlq",
        },
    )

    graph.add_edge("fix", "execute")
    graph.add_edge("create_pr", END)
    graph.add_edge("dlq", END)

    return graph.compile()


def run_workflow(task_id: int, issue_url: str, repo_url: str, max_retries: int | None = None) -> dict:
    """Run the agent workflow. Returns final state; sets failed=True on graph exceptions."""
    graph = build_graph()
    initial = WorkflowStateSchema(
        task_id=task_id,
        issue_url=issue_url,
        repo_url=repo_url,
        max_retries=max_retries if max_retries is not None else settings.MAX_RETRIES,
    ).model_dump()

    try:
        return graph.invoke(initial)
    except Exception as exc:
        logger.exception("Workflow graph failed for task %s", task_id)
        failed = dict(initial)
        failed["failed"] = True
        failed["failure_reason"] = str(exc)
        failed["error_type"] = type(exc).__name__
        failed["failed_step"] = failed.get("current_step", "graph_invoke")
        return failed
