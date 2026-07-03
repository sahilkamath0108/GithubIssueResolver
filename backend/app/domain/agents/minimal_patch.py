"""Drop whitespace-only or identical file outputs before opening a PR."""
from __future__ import annotations


def _meaningful_lines(text: str) -> list[str]:
    """Non-empty lines with trailing whitespace stripped (blank-line edits ignored)."""
    return [line.rstrip() for line in text.splitlines() if line.strip()]


def has_substantive_change(original: str | None, updated: str) -> bool:
    """
    True when updated content differs from original in non-whitespace ways.
    Ignores: identical files, EOF newline-only, added/removed blank lines, line trailing spaces.
    """
    if original is None:
        return bool(updated.strip())
    if original == updated:
        return False
    if _meaningful_lines(original) == _meaningful_lines(updated):
        return False
    return True


def filter_substantive_file_changes(
    generated: dict[str, str],
    originals: dict[str, str],
) -> dict[str, str]:
    """Keep only paths whose content changed in a meaningful way."""
    kept: dict[str, str] = {}
    for path, content in generated.items():
        if has_substantive_change(originals.get(path), content):
            kept[path] = content
    return kept
