import json
from app.domain.state.workflow_state import WorkflowStateSchema
from app.domain.agents.patch_parse import parse_changes_to_files
from app.services.llm_service import call_llm_json

# Tone aligned with a focused “coding assistant”: minimal, correct, repo-appropriate (any language).
_SYSTEM_BLOCK = """
You are an AI coding assistant implementing changes in a real repository.

Your job: produce complete updated file contents for each file that must change, matching the plan and the existing project (language, style, structure).

Rules:
- Modify ONLY files listed in files_to_modify (these were chosen from the repo via semantic search).
- Use the language and patterns shown in "Relevant existing code" (React/JS/TS/Python/etc.).
- Prefer minimal, targeted edits; still output the FULL file content for each changed path (not a diff).
- Do not invent new file names or switch languages unless the plan explicitly requires it.

Output contract:
- Respond with ONE JSON object only, no markdown fences, no commentary.
- Use this shape exactly:
  {{"changes":[{{"path":"relative/path.ext","content":"<full file text>"}}]}}
- Inside JSON strings: escape newlines as \\n, double-quotes as \\", backslashes as \\\\.
- Do not put triple-quotes or raw multiline blocks inside JSON; keep strings valid JSON.
"""

_CODE_PROMPT = (
    _SYSTEM_BLOCK
    + """

Plan:
{plan}

Relevant existing code:
{context}
"""
)


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
        result = call_llm_json(prompt, use_cache=False)

        changes = result.get("changes") if isinstance(result, dict) else None
        normalized = parse_changes_to_files(changes)

        if normalized is None or not normalized:
            repair = (
                prompt
                + "\n\nYour previous response was invalid. Return ONLY one JSON object: "
                '{"changes":[{"path":"...","content":"..."}]} with valid JSON strings (escaped newlines). '
                "No markdown, no explanation."
            )
            result = call_llm_json(repair, use_cache=False)
            changes = result.get("changes") if isinstance(result, dict) else None
            normalized = parse_changes_to_files(changes)

        if normalized is None or not normalized:
            raise ValueError(
                "LLM returned invalid code change JSON (expected {changes: [{path, content}]})."
            )

        allowed = set((state.plan or {}).get("files_to_modify", []) or [])
        if allowed:
            extra = [p for p in normalized.keys() if p not in allowed]
            if extra:
                raise ValueError(
                    f"LLM attempted to modify files not in plan.files_to_modify: {extra}. "
                    f"Allowed: {sorted(allowed)}"
                )

        state.generated_code = normalized
        return state

    def _format_chunks(self, chunks: list[dict]) -> str:
        parts: list[str] = []
        for c in chunks:
            header = f"# File: {c['path']}"
            if c.get("source") in ("related_snippet", "vector_chunk"):
                header += " (related snippet — not the file being edited)"
            parts.append(f"{header}\n{c['chunk']}")
        return "\n\n".join(parts)
