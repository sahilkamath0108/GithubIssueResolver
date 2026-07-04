"""Static checks on LLM-generated code before validation or commit."""
from __future__ import annotations

import re

_EXECUTABLE_SUFFIXES = (
    ".py",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".mjs",
    ".cjs",
    ".sh",
    ".bash",
    ".ps1",
)

_DANGEROUS_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bos\.system\s*\("), "os.system"),
    (re.compile(r"\bsubprocess\b"), "subprocess"),
    (re.compile(r"\beval\s*\("), "eval()"),
    (re.compile(r"\bexec\s*\("), "exec()"),
    (re.compile(r"__import__\s*\("), "__import__()"),
    (re.compile(r"\bcompile\s*\("), "compile()"),
    (re.compile(r"\bsocket\b"), "socket"),
    (re.compile(r"\bctypes\b"), "ctypes"),
    (re.compile(r"\bpty\b"), "pty"),
    (re.compile(r"\bimportlib\b"), "importlib"),
    (re.compile(r"open\s*\([^)]*['\"]/?etc/"), "open(/etc/)"),
    (re.compile(r"open\s*\([^)]*['\"]/?proc/"), "open(/proc/)"),
)


class UnsafeGeneratedCodeError(ValueError):
    """Raised when generated code contains disallowed constructs."""


def _is_executable_path(path: str) -> bool:
    lower = path.lower()
    return any(lower.endswith(ext) for ext in _EXECUTABLE_SUFFIXES)


def scan_generated_code(generated: dict[str, str]) -> None:
    """
    Reject executable files containing patterns associated with sandbox escape / RCE.
    Config files (.yml, .json, etc.) are not scanned for these patterns.
    """
    for path, content in generated.items():
        if not _is_executable_path(path):
            continue
        for pattern, label in _DANGEROUS_PATTERNS:
            if pattern.search(content):
                raise UnsafeGeneratedCodeError(
                    f"Generated file '{path}' contains disallowed construct: {label}. "
                    "The agent must produce minimal, safe patches only."
                )
