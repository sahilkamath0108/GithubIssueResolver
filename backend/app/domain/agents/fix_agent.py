import json
from app.domain.state.workflow_state import WorkflowStateSchema
from app.domain.agents.patch_parse import parse_changes_to_files
from app.services.llm_service import call_llm_json

_SYSTEM_BLOCK = """
You are an AI coding assistant fixing a failing test or runtime error.

Rules:
- Fix ONLY what is needed for the error; keep unrelated code unchanged.
- Output FULL file content for each file you change (not a diff).
- Match the project's language and style.

Output: ONE JSON object only, no markdown, no commentary:
{{"changes":[{{"path":"relative/path.ext","content":"<full file text>"}}]}}
Escape newlines as \\n inside JSON strings. Valid JSON only.
"""

_FIX_PROMPT = (
    _SYSTEM_BLOCK
    + """

Error Type: {error_type}
Test Output:
{test_output}

Current Code:
{code}
"""
)


def classify_error(test_output: str) -> str:
    """
    Deterministic error classification — NO LLM needed.
    Parse error type from test output string.
    """
    if "ImportError" in test_output or "ModuleNotFoundError" in test_output:
        return "ImportError"
    if "AssertionError" in test_output:
        return "AssertionError"
    if "TypeError" in test_output:
        return "TypeError"
    if "AttributeError" in test_output:
        return "AttributeError"
    if "SyntaxError" in test_output:
        return "SyntaxError"
    return "UnknownError"


class FixAgent:
    """
    LLM agent — called ONLY on failure, max MAX_RETRIES times.
    Receives precise error context, not vague "fix code" prompt.
    """

    def run(self, state: WorkflowStateSchema) -> WorkflowStateSchema:
        error_type = classify_error(state.test_output or "")
        state.error_type = error_type

        prompt = _FIX_PROMPT.format(
            error_type=error_type,
            test_output=(state.test_output or "")[:2000],
            code=json.dumps(state.generated_code, indent=2),
        )
        result = call_llm_json(prompt, use_cache=False)
        changes = result.get("changes") if isinstance(result, dict) else None
        normalized = parse_changes_to_files(changes)

        if normalized is None or not normalized:
            repair = (
                prompt
                + "\n\nInvalid output. Return ONLY: "
                '{"changes":[{"path":"...","content":"..."}]} with valid JSON strings.'
            )
            result = call_llm_json(repair, use_cache=False)
            changes = result.get("changes") if isinstance(result, dict) else None
            normalized = parse_changes_to_files(changes)

        if normalized is None or not normalized:
            raise ValueError("LLM returned invalid fix JSON (expected {changes: [{path, content}]}).")

        allowed = set((state.generated_code or {}).keys()) or set(
            (state.plan or {}).get("files_to_modify", []) or []
        )
        if allowed:
            extra = [p for p in normalized.keys() if p not in allowed]
            if extra:
                raise ValueError(
                    f"LLM attempted to modify files outside allowed set: {extra}. "
                    f"Allowed: {sorted(allowed)}"
                )

        state.generated_code = normalized
        state.retry_count += 1
        return state
