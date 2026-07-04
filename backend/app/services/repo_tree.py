"""Build a compact repository path listing for planner context."""

from __future__ import annotations

# Directory prefixes to omit from planner tree (large or generated trees).
_SKIP_PREFIXES: tuple[str, ...] = (
    ".git/",
    "node_modules/",
    "dist/",
    "build/",
    "coverage/",
    "__pycache__/",
    ".venv/",
    "venv/",
    ".next/",
    ".nuxt/",
    "target/",
    "vendor/",
)


def should_skip_tree_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lstrip("./")
    lower = normalized.lower()
    if not lower:
        return True
    return any(
        lower == prefix.rstrip("/")
        or lower.startswith(prefix)
        or f"/{prefix}" in lower
        for prefix in _SKIP_PREFIXES
    )


def format_path_list_for_planner(
    paths: list[str],
    *,
    repo_full_name: str,
    branch: str,
    max_chars: int = 8000,
) -> str:
    """Sorted path list with header; truncate by character budget."""
    header = (
        f"Repository: {repo_full_name} (default branch: {branch})\n"
        f"File paths ({len(paths)} listed, directories implied by /):\n"
    )
    lines: list[str] = []
    used = len(header)
    for path in paths:
        line = path + "\n"
        if used + len(line) > max_chars:
            lines.append("...[tree truncated by size limit]")
            break
        lines.append(path)
        used += len(line)
    body = "\n".join(lines)
    return header + body
