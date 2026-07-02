from app.domain.state.workflow_state import WorkflowStateSchema
from app.services.llm_service import call_llm_json

_PLAN_PROMPT = """
You are a senior software engineer. Analyze the GitHub issue and produce a high-level execution plan.

You do NOT have access to the repository file tree. Do NOT guess file paths or extensions.

Issue Title: {title}
Issue Body: {body}

Respond ONLY with valid JSON in this exact format:
{{
  "changes": ["description of change 1", "description of change 2"],
  "test_cases": ["test case description 1", "test case description 2"],
  "search_query": "short query to find relevant code via semantic search (components, handlers, routes, etc.)"
}}
"""


class PlannerAgent:
    """
    LLM agent — used ONLY for reasoning about what to change.
    Caches result by issue content to avoid repeat LLM calls.
    """

    def run(self, state: WorkflowStateSchema, issue: dict) -> WorkflowStateSchema:
        prompt = _PLAN_PROMPT.format(
            title=issue["title"],
            body=issue["body"],
        )
        plan = call_llm_json(prompt, use_cache=True)
        if not isinstance(plan, dict):
            repair = prompt + "\n\nYour previous response was invalid. Return ONLY valid JSON in the exact schema. Do not include explanations."
            plan = call_llm_json(repair, use_cache=False)
        if (
            not isinstance(plan, dict)
            or not isinstance(plan.get("changes"), list)
            or not isinstance(plan.get("search_query"), str)
            or not plan.get("search_query", "").strip()
        ):
            raise ValueError("LLM returned invalid plan JSON (need changes[] and search_query).")
        # Target files are assigned later from Qdrant + GitHub in read_code.
        plan.pop("files_to_modify", None)
        state.plan = plan
        return state
