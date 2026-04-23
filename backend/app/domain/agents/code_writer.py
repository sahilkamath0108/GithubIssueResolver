import json
from app.domain.state.workflow_state import WorkflowStateSchema
from app.services.llm_service import call_llm_json

_CODE_PROMPT = """
You are a senior software engineer. Write the minimal code changes needed.

Plan:
{plan}

Relevant existing code:
{context}

Rules:
- Modify ONLY the files listed in the plan
- Make minimal targeted changes
- Do NOT rewrite entire files

Respond ONLY with valid JSON:
{{
  "changes": {{
    "path/to/file.py": "complete new file content here"
  }}
}}
"""


class CodeWriterAgent:
    """
    LLM agent — receives plan + relevant chunks only
    """

    def run(self, state: WorkflowStateSchema) -> WorkflowStateSchema:
        context = self._format_chunks(state.relevant_chunks or [])
        prompt = _CODE_PROMPT.format(
            plan=json.dumps(state.plan, indent=2),
            context=context,
        )
        result = call_llm_json(prompt, use_cache=False)  # no cache — code gen must be fresh
        state.generated_code = result.get("changes", {})
        return state

    def _format_chunks(self, chunks: list[dict]) -> str:
        return "\n\n".join(
            f"# File: {c['path']}\n{c['chunk']}"
            for c in chunks
        )
