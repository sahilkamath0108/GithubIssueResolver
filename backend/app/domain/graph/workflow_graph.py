from langgraph.graph import StateGraph, END
from app.domain.graph.nodes import (
    node_plan, node_read_code, node_write_code,
    node_execute, node_fix, node_create_pr, node_send_to_dlq,
    route_after_execute,
)
from app.domain.state.workflow_state import WorkflowStateSchema


def build_graph() -> StateGraph:
    graph = StateGraph(dict)

    # Register nodes
    graph.add_node("plan", node_plan)
    graph.add_node("read_code", node_read_code)
    graph.add_node("write_code", node_write_code)
    graph.add_node("execute", node_execute)
    graph.add_node("fix", node_fix)
    graph.add_node("create_pr", node_create_pr)
    graph.add_node("dlq", node_send_to_dlq)

    # Linear flow
    graph.set_entry_point("plan")
    graph.add_edge("plan", "read_code")
    graph.add_edge("read_code", "write_code")
    graph.add_edge("write_code", "execute")

    # Conditional routing after execution
    graph.add_conditional_edges(
        "execute",
        route_after_execute,
        {
            "create_pr": "create_pr",
            "fix": "fix",
            "dlq": "dlq",
        },
    )

    # Fix loops back to execute
    graph.add_edge("fix", "execute")

    # Terminal nodes
    graph.add_edge("create_pr", END)
    graph.add_edge("dlq", END)

    return graph.compile()


def run_workflow(task_id: int, issue_url: str, repo_url: str, max_retries: int = 2) -> dict:
    """
    Entry point for running the full agent workflow.
    Returns final state dict.
    """
    graph = build_graph()
    initial_state = WorkflowStateSchema(
        task_id=task_id,
        issue_url=issue_url,
        repo_url=repo_url,
        max_retries=max_retries,
    ).model_dump()

    return graph.invoke(initial_state)
