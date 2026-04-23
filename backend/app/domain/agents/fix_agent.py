import json
from app.domain.state.workflow_state import WorkflowStateSchema
from app.services.llm_service import call_llm_json

_FIX_PROMPT = """
You are a senior software engineer. Fix the minimal bug based on the error.

Error Type: {error_type}
Test Output:
{test_output}

Current Code:
{code}

Rules:
- Fix ONLY the specific error
- Do NOT rewrite unrelated code
- Be minimal and precise

Respond ONLY with valid JSON:
{{
  "changes": {{
    "path/to/file.py": "complete new file content here"
  }}
}}
"""


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
            test_output=(state.test_output or "")[:2000],  # cap to avoid token explosion
            code=json.dumps(state.generated_code, indent=2),
        )
        result = call_llm_json(prompt, use_cache=False)
        state.generated_code = result.get("changes", state.generated_code)
        state.retry_count += 1
        return state
