from app.domain.state.workflow_state import WorkflowStateSchema
from app.domain.agents.prompt_guard import (
    PROMPT_INJECTION_SYSTEM_GUARDRAIL,
    validate_plan_output,
    wrap_repo_tree_for_planner,
    wrap_untrusted_issue,
)
from app.services.plan_scope import collect_plan_target_paths, merge_plan_constraints, resolve_scope
from app.services.llm_service import call_llm_json_messages

_PLAN_SYSTEM = (
    PROMPT_INJECTION_SYSTEM_GUARDRAIL
    + """

You are a senior software engineer. Analyze the GitHub issue and repository layout, then produce a high-level execution plan.

You receive a **repository file tree** (trusted) listing paths on the default branch. Use it to pick exact repo-relative paths.

Use the tree to infer architecture (e.g. UI under `frontend/`, `src/`, `client/` vs APIs under `server/` or `backend/` vs ops files like `docker-compose.yml`, `prometheus.yml`, `monitoring/**`). When the issue says **no backend changes**, set `"scope": "frontend"` and include `"constraints": ["No backend changes"]`. For Prometheus/Docker Compose/monitoring issues, use `"scope": "fullstack"` and list scrape configs, compose files, and service names from the tree.

**files_to_modify** (required): every file that must be created or edited to fix the issue — pages, components, API client modules, shared hooks, styles, etc. Paths must come from the tree (or be new paths you justify in `changes`). This list drives the code writer; be complete — if navbar + page + API client are involved, include all of them.

In `changes`, describe what to do in each file (you may repeat paths for clarity). Do NOT guess paths outside the tree unless the issue requires a new file. Do NOT put file paths in `search_query` (validation rejects them).

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
  "files_to_modify": ["frontend/components/navbar.tsx", "frontend/app/my-registrations/page.tsx"],
  "changes": ["Update frontend/components/navbar.tsx to add link", "Add frontend/app/my-registrations/page.tsx"],
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
        plan["files_to_modify"] = collect_plan_target_paths(plan)
        state.plan = plan
        return state
