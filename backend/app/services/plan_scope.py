"""Issue scope, plan path hints, and architecture-aware path filtering."""

from __future__ import annotations

import re
from typing import Literal

Scope = Literal["frontend", "backend", "fullstack"]

_VALID_SCOPES: frozenset[str] = frozenset({"frontend", "backend", "fullstack"})

_PATH_IN_TEXT = re.compile(
    r"(?<![\w./-])((?:[\w.-]+/)+[\w.-]+\.(?:tsx?|jsx?|mjs|cjs|py|go|rs|java|vue|svelte))\b",
    re.IGNORECASE,
)

_FRONTEND_ONLY = re.compile(
    r"\b(?:no backend(?:\s+changes?)?|frontend[- ]only|ui[- ]only|client[- ]side only)\b",
    re.IGNORECASE,
)
_BACKEND_ONLY = re.compile(
    r"\b(?:no frontend(?:\s+changes?)?|backend[- ]only|api[- ]only|server[- ]only)\b",
    re.IGNORECASE,
)

_CONSTRAINT_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (_FRONTEND_ONLY, "No backend changes"),
    (_BACKEND_ONLY, "No frontend changes"),
    (re.compile(r"\bdo not (?:modify|change|touch) (?:the )?backend\b", re.I), "No backend changes"),
    (re.compile(r"\bdo not (?:modify|change|touch) (?:the )?frontend\b", re.I), "No frontend changes"),
)

_BACKEND_MARKERS = (
    "server/",
    "backend/",
    "/controllers/",
    "/controller/",
    "/routes/",
    "routes.js",
    "routes.ts",
    "repo.js",
    "repo.ts",
    "service.js",
    "service.ts",
    "/migrations/",
    "/models/",
)


def infer_scope_from_issue(title: str, body: str) -> Scope:
    text = f"{title or ''}\n{body or ''}"
    if _FRONTEND_ONLY.search(text):
        return "frontend"
    if _BACKEND_ONLY.search(text):
        return "backend"
    return "fullstack"


def extract_constraints_from_issue(title: str, body: str) -> list[str]:
    text = f"{title or ''}\n{body or ''}"
    found: list[str] = []
    seen: set[str] = set()
    for pattern, label in _CONSTRAINT_RULES:
        if pattern.search(text) and label not in seen:
            seen.add(label)
            found.append(label)
    return found


def resolve_scope(plan: dict, issue: dict) -> Scope:
    from_issue = infer_scope_from_issue(issue.get("title", ""), issue.get("body") or "")
    if from_issue != "fullstack":
        return from_issue
    raw = plan.get("scope")
    if isinstance(raw, str) and raw.lower() in _VALID_SCOPES:
        return raw.lower()  # type: ignore[return-value]
    return "fullstack"


def merge_plan_constraints(plan: dict, issue: dict) -> list[str]:
    from_plan = plan.get("constraints") if isinstance(plan.get("constraints"), list) else []
    from_issue = extract_constraints_from_issue(issue.get("title", ""), issue.get("body") or "")
    merged: list[str] = []
    seen: set[str] = set()
    for item in list(from_plan) + from_issue:
        if isinstance(item, str) and item.strip() and item not in seen:
            seen.add(item)
            merged.append(item.strip())
    scope = resolve_scope(plan, issue)
    if scope == "frontend" and "No backend changes" not in seen:
        merged.append("No backend changes")
    if scope == "backend" and "No frontend changes" not in seen:
        merged.append("No frontend changes")
    return merged


def extract_paths_from_plan(plan: dict) -> list[str]:
    """Pull explicit repo-relative paths mentioned in plan change descriptions."""
    paths: list[str] = []
    seen: set[str] = set()
    for change in plan.get("changes") or []:
        if not isinstance(change, str):
            continue
        for match in _PATH_IN_TEXT.finditer(change):
            raw = match.group(1).replace("\\", "/").strip("./")
            if raw.startswith("or ") or raw.startswith("similar"):
                continue
            key = raw.lower()
            if key in seen:
                continue
            seen.add(key)
            paths.append(raw)
    return paths


def is_backend_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    if normalized.startswith("frontend/"):
        return False
    if any(normalized.startswith(p) or f"/{p}" in normalized for p in ("server/", "backend/")):
        return True
    return any(marker in normalized for marker in _BACKEND_MARKERS)


def is_frontend_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    if normalized.startswith("frontend/"):
        return True
    if "/app/" in normalized and normalized.endswith(("page.tsx", "page.jsx", "layout.tsx", "layout.jsx")):
        return True
    if "/components/" in normalized or "/utils/apis/" in normalized:
        return True
    return normalized.endswith(("navbar.tsx", "navbar.jsx"))


def path_allowed_for_scope(path: str, scope: Scope) -> bool:
    if scope == "fullstack":
        return True
    if scope == "frontend":
        return is_frontend_path(path)
    if scope == "backend":
        return is_backend_path(path)
    return True


def filter_paths_by_scope(paths: list[str], scope: Scope) -> list[str]:
    return [p for p in paths if path_allowed_for_scope(p, scope)]


def find_reference_paths(new_path: str, repo_paths: list[str], *, limit: int = 2) -> list[str]:
    """Similar existing files to use as templates when creating a new path."""
    normalized = new_path.replace("\\", "/")
    lower = normalized.lower()
    refs: list[tuple[float, str]] = []

    for candidate in repo_paths:
        cl = candidate.replace("\\", "/").lower()
        score = 0.0
        if lower.endswith("page.tsx") and cl.endswith("page.tsx") and "/app/" in cl:
            score += 3.0 - cl.count("/") * 0.05
        if "ordersapi" in lower and "ordersapi" in cl:
            score += 4.0
        if lower.endswith("navbar.tsx") and cl.endswith("navbar.tsx"):
            score += 5.0
        parent = normalized.rsplit("/", 1)[0].lower()
        if parent and cl.startswith(parent + "/"):
            score += 1.5
        if score > 0:
            refs.append((score, candidate))

    refs.sort(key=lambda item: (-item[0], item[1]))
    out: list[str] = []
    seen: set[str] = set()
    for _, path in refs:
        if path in seen:
            continue
        seen.add(path)
        out.append(path)
        if len(out) >= limit:
            break
    return out
