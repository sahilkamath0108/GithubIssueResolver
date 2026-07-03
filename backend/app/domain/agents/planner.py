from app.domain.state.workflow_state import WorkflowStateSchema
from app.domain.agents.prompt_guard import (
    PROMPT_INJECTION_SYSTEM_GUARDRAIL,
    validate_plan_output,
    wrap_untrusted_issue,
)
from app.services.llm_service import call_llm_json_messages

_PLAN_SYSTEM = (
    PROMPT_INJECTION_SYSTEM_GUARDRAIL
    + """

You are a senior software engineer. Analyze the GitHub issue data and produce a high-level execution plan.

You do NOT have access to the repository file tree. Do NOT guess file paths or extensions.

The search_query will be embedded and matched against **source code chunks** in a vector database (function bodies, JSX, imports, class names — not README prose).

search_query rules (critical for vector similarity):
- Write a **dense keyword string** (roughly 8–25 tokens), not a full sentence or task description.
- Prefer **words that literally appear in source code**: identifiers, hooks, props, handlers, routes, API paths, error strings, UI labels from the issue.
- Mix **domain terms from the issue** with **code vocabulary** (e.g. counter increment button click onClick useState setState handler render).
- Include likely **symbol-style tokens** when inferable (PascalCase/camelCase names, e.g. Counter, handleClick, TodoList).
- Do NOT use vague meta phrases like "components that render lists", "logic related to", "files that handle", or "implement the feature".
- Do NOT use file paths or extensions in search_query.

Respond ONLY with valid JSON in this exact format:
{
  "changes": ["description of change 1", "description of change 2"],
  "test_cases": ["test case description 1", "test case description 2"],
  "search_query": "dense code-like keywords for embedding search"
}
"""
)


class PlannerAgent:
    """
    LLM agent — used ONLY for reasoning about what to change.
    Caches result by issue content to avoid repeat LLM calls.
    """

    def run(self, state: WorkflowStateSchema, issue: dict) -> WorkflowStateSchema:
        messages = [
            {"role": "system", "content": _PLAN_SYSTEM},
            {
                "role": "user",
                "content": wrap_untrusted_issue(issue["title"], issue.get("body") or ""),
            },
        ]
        plan = call_llm_json_messages(messages, use_cache=True)
        if not isinstance(plan, dict):
            repair = messages + [
                {
                    "role": "user",
                    "content": "Your previous response was invalid. Return ONLY valid JSON in the exact schema. Do not include explanations.",
                }
            ]
            plan = call_llm_json_messages(repair, use_cache=False)
        validate_plan_output(plan)
        if not isinstance(plan.get("test_cases"), list):
            plan["test_cases"] = []
        plan.pop("files_to_modify", None)
        state.plan = plan
        return state
