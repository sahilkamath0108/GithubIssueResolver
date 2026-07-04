"""Guardrails for LLM file edits during write/fix steps."""


class ExtraFilesRequestedError(ValueError):
    """Raised when the LLM returns paths outside the current allowlist."""

    def __init__(self, extra_paths: list[str], allowed: list[str]):
        self.extra_paths = extra_paths
        self.allowed = allowed
        super().__init__(
            f"LLM attempted to modify files not in allowlist: {extra_paths}. "
            f"Allowed: {sorted(allowed)}"
        )
