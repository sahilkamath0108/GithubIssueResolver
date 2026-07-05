from app.domain.state.workflow_state import WorkflowStateSchema
from app.domain.agents.prompt_guard import (
    PROMPT_INJECTION_SYSTEM_GUARDRAIL,
    validate_plan_output,
    wrap_repo_tree_for_planner,
    wrap_untrusted_issue,
)
from app.services.plan_scope import merge_plan_constraints, resolve_scope
from app.services.llm_service import call_llm_json_messages

_PLAN_SYSTEM = (
    PROMPT_INJECTION_SYSTEM_GUARDRAIL
    + """

You are a senior software engineer. Analyze the GitHub issue and repository layout, then produce a high-level execution plan.

You receive a **repository file tree** (trusted) listing paths on the default branch. Use it to understand project structure, likely entrypoints, and where related code may live when writing `changes` descriptions and `search_query` keywords.

Use the tree to infer architecture (e.g. Next.js `frontend/app/**/page.tsx` for UI pages vs Express `server/**` for APIs). When the issue says **no backend changes**, set `"scope": "frontend"` and include `"constraints": ["No backend changes"]`.

In each change description, name the **exact repo-relative path** from the tree when editing an existing file, or the path to create for new files (e.g. `frontend/app/my-registrations/page.tsx`).

Do NOT guess paths that are not in the tree unless the issue explicitly requires creating a new file at that location. Do NOT put file paths or extensions in `search_query` (validation will reject them).

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
  "changes": ["description with exact path from tree, e.g. Update frontend/components/navbar.tsx to add link"],
  "test_cases": ["test case description 1", "test case description 2"],
  "search_query": "dense code-like keywords for embedding search",
  "scope": "frontend | backend | fullstack",
  "constraints": ["No backend changes"]
}
"""
)


class PlannerAgent:
    """
    LLM agent — used ONLY for reasoning about what to change.
    Caches result by issue content to avoid repeat LLM calls.
    """

    def run(
        self,
        state: WorkflowStateSchema,
        issue: dict,
        *,
        repo_tree: str = "",
    ) -> WorkflowStateSchema:
        user_parts: list[str] = []
        tree_block = wrap_repo_tree_for_planner(repo_tree)
        if tree_block:
            user_parts.append(tree_block)
        user_parts.append(wrap_untrusted_issue(issue["title"], issue.get("body") or ""))
        messages = [
            {"role": "system", "content": _PLAN_SYSTEM},
            {"role": "user", "content": "\n\n".join(user_parts)},
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
        plan["scope"] = resolve_scope(plan, issue)
        plan["constraints"] = merge_plan_constraints(plan, issue)
        plan.pop("files_to_modify", None)
        state.plan = plan
        return state
