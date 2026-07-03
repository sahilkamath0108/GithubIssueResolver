"""Normalize LLM patch JSON into {repo_path: file_content}."""
from __future__ import annotations

from typing import Any

from app.core.security import sanitize_repo_path


def _safe_paths(files: dict[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for path, content in files.items():
        try:
            out[sanitize_repo_path(path)] = content
        except ValueError:
            continue
    return out


def parse_changes_to_files(changes: Any) -> dict[str, str] | None:
    """
    Accepts:
    - {"changes": [...]} already unwrapped to the list or dict
    - list of {"path": "...", "content": "..."}  (content = full file text, UTF-8)
    - legacy dict { "path/to/file": "full content", ... }
    """
    if isinstance(changes, dict) and changes:
        if all(isinstance(k, str) and isinstance(v, str) for k, v in changes.items()):
            safe = _safe_paths(changes)
            return safe if safe else None
        return None
    if not isinstance(changes, list):
        return None
    out: dict[str, str] = {}
    for item in changes:
        if not isinstance(item, dict) or "path" not in item:
            continue
        path = str(item["path"]).strip()
        if not path:
            continue
        raw = item.get("content")
        if not isinstance(raw, str):
            continue
        try:
            out[sanitize_repo_path(path)] = raw
        except ValueError:
            continue
    return out if out else None
