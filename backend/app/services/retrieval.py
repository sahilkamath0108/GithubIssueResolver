"""
Multi-query vector retrieval helpers: query expansion, hit merging, entrypoint boost.
"""

from __future__ import annotations

import posixpath

from app.core.settings import settings
from app.services.plan_scope import Scope, extract_paths_from_plan, filter_paths_by_scope, path_allowed_for_scope

_ENTRYPOINT_BASENAMES = frozenset(
    {
        "main.py",
        "app.py",
        "wsgi.py",
        "asgi.py",
        "manage.py",
        "__init__.py",
        "index.js",
        "index.ts",
        "index.tsx",
        "index.jsx",
        "index.mjs",
        "main.ts",
        "main.js",
        "main.go",
        "main.rs",
        "server.js",
        "server.ts",
        "app.js",
        "app.ts",
        "App.tsx",
        "App.jsx",
        "App.vue",
    }
)


def build_search_queries(plan: dict) -> list[str]:
    """
    Primary planner search_query plus distinct change descriptions (multi-query retrieval).
    """
    queries: list[str] = []
    seen: set[str] = set()

    def add(raw: str) -> None:
        q = raw.strip()
        if not q:
            return
        key = q.lower()
        if key in seen:
            return
        if len(queries) >= settings.CONTEXT_SEARCH_MAX_QUERIES:
            return
        seen.add(key)
        queries.append(q[: settings.SEARCH_QUERY_MAX])

    primary = plan.get("search_query")
    if isinstance(primary, str):
        add(primary)

    for change in plan.get("changes") or []:
        if isinstance(change, str):
            add(change)

    if not queries:
        fallback = " ".join(str(c) for c in (plan.get("changes") or []) if c)
        add(fallback or "implementation bug fix handler component")

    return queries


def merge_search_hits(hit_lists: list[list[dict]]) -> list[dict]:
    """Merge per-query hits; keep the best score for each (path, chunk) pair."""
    merged: dict[tuple[str, str], dict] = {}
    for hits in hit_lists:
        for rank, chunk in enumerate(hits):
            path = chunk.get("path")
            text = chunk.get("chunk") or chunk.get("text") or ""
            if not isinstance(path, str) or not path:
                continue
            score = chunk.get("score")
            if score is None:
                score = max(0.0, 1.0 - rank * 0.02)
            key = (path, text)
            existing = merged.get(key)
            if existing is None or float(score) > float(existing.get("score") or 0):
                merged[key] = {**chunk, "path": path, "chunk": text, "score": float(score)}
            elif existing is not None:
                existing["score"] = max(float(existing.get("score") or 0), float(score))
    return list(merged.values())


def entrypoint_priority(path: str, *, scope: Scope = "fullstack") -> float:
    if scope == "frontend":
        return _frontend_entrypoint_priority(path)
    base = posixpath.basename(path)
    if base not in _ENTRYPOINT_BASENAMES:
        return 0.0
    depth = path.count("/")
    if base == "__init__.py" and depth > 2:
        return 0.0

    score = 1.0
    if depth <= 1:
        score += 0.25
    elif depth <= 2:
        score += 0.1

    parent = posixpath.basename(posixpath.dirname(path)).lower()
    if parent in {"server", "src", "app", "backend", "api"}:
        score += 0.1
    if base.lower() in {"server.js", "app.js", "main.py", "app.py"}:
        score += 0.05
    return score


def _frontend_entrypoint_priority(path: str) -> float:
    normalized = path.replace("\\", "/").lower()
    if normalized.endswith("navbar.tsx") or normalized.endswith("navbar.jsx"):
        return 3.0
    if "/utils/apis/" in normalized and normalized.endswith((".ts", ".tsx", ".js", ".jsx")):
        return 2.5
    if "/app/" in normalized and normalized.endswith(("page.tsx", "page.jsx")):
        return max(0.5, 2.0 - normalized.count("/") * 0.05)
    if normalized.endswith(("layout.tsx", "layout.jsx")):
        return 1.5
    return 0.0


def detect_entrypoint_paths(
    repo_paths: list[str],
    *,
    max_paths: int | None = None,
    scope: Scope = "fullstack",
) -> list[str]:
    limit = max_paths or settings.ENTRYPOINT_MAX_INJECT
    scored = [(p, entrypoint_priority(p, scope=scope)) for p in repo_paths]
    scored = [(p, s) for p, s in scored if s > 0]
    if scope == "frontend":
        scored = [(p, s) for p, s in scored if path_allowed_for_scope(p, scope)]
    scored.sort(key=lambda item: (-item[1], item[0]))
    return [p for p, _ in scored[:limit]]


def apply_entrypoint_boost(hits: list[dict], *, scope: Scope = "fullstack") -> list[dict]:
    boost = settings.ENTRYPOINT_SCORE_BOOST
    out: list[dict] = []
    for hit in hits:
        score = float(hit.get("score") or 0)
        path = hit.get("path") or ""
        if entrypoint_priority(path, scope=scope) > 0:
            score += boost
        out.append({**hit, "score": score})
    return out


def inject_missing_entrypoints(
    hits: list[dict],
    repo_paths: list[str],
    *,
    scope: Scope = "fullstack",
) -> list[dict]:
    """Ensure top entrypoint paths appear even if vector search missed them."""
    present = {h.get("path") for h in hits if h.get("path")}
    injected: list[dict] = []
    for path in detect_entrypoint_paths(repo_paths, scope=scope):
        if path in present:
            continue
        injected.append(
            {
                "path": path,
                "chunk": "",
                "score": 1.0 + settings.ENTRYPOINT_SCORE_BOOST,
                "source": "entrypoint",
            }
        )
        present.add(path)
    return injected + hits


def rank_retrieval_hits(
    hits: list[dict],
    repo_paths: list[str] | None = None,
    *,
    scope: Scope = "fullstack",
) -> list[dict]:
    """Boost entrypoints, inject missing ones, sort by score descending."""
    if scope != "fullstack":
        hits = [h for h in hits if path_allowed_for_scope(h.get("path") or "", scope)]
    if repo_paths:
        hits = inject_missing_entrypoints(hits, repo_paths, scope=scope)
    hits = apply_entrypoint_boost(hits, scope=scope)
    return sorted(hits, key=lambda h: float(h.get("score") or 0), reverse=True)


def truncate_retrieval_hits(hits: list[dict], top_k: int | None = None) -> list[dict]:
    limit = top_k or settings.CONTEXT_SEARCH_TOP_K
    return hits[:limit]
