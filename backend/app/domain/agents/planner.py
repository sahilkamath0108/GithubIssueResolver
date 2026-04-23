from app.domain.state.workflow_state import WorkflowStateSchema
from app.services.llm_service import call_llm_json

_PLAN_PROMPT = """
You are a senior software engineer. Analyze the GitHub issue and produce a precise execution plan.

Issue Title: {title}
Issue Body: {body}

Respond ONLY with valid JSON in this exact format:
{{
  "files_to_modify": ["path/to/file.py"],
  "changes": ["description of change 1", "description of change 2"],
  "test_cases": ["test case description 1", "test case description 2"],
  "search_query": "short query to find relevant code via vector search"
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
        state.plan = plan
        return state
