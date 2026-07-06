"""
Code Context Service — deterministic, no LLM.

Combines GitHub file contents with Qdrant vector hits (filtered by repo payload)
into a token-capped context for the code writer.
"""
import ast
import posixpath
from typing import List, Dict, Set

from app.core.settings import settings
from app.core.security import sanitize_repo_path
from app.services.plan_scope import (
    Scope,
    collect_plan_target_paths,
    filter_paths_by_scope,
    find_reference_paths,
    path_allowed_for_scope,
    resolve_scope,
)


_CHARS_PER_TOKEN = 4


def _estimate_tokens(text: str) -> int:
    return len(text) // _CHARS_PER_TOKEN


def cap_context(
    chunks: List[dict],
    max_tokens: int | None = None,
    *,
    priority_paths: Set[str] | None = None,
) -> List[dict]:
    """
    Trim context to token budget.
    Paths in priority_paths (files_to_modify) are always kept in full — never truncated.
    """
    limit = max_tokens or settings.MAX_CONTEXT_TOKENS
    priority_paths = priority_paths or set()

    priority = [c for c in chunks if c.get("path") in priority_paths]
    rest = [c for c in chunks if c.get("path") not in priority_paths]

    result: list[dict] = []
    used = 0

    for item in priority:
        result.append(item)
        used += _estimate_tokens(item.get("chunk", "") + item.get("content", ""))

    for item in rest:
        tokens = _estimate_tokens(item.get("chunk", "") + item.get("content", ""))
        if used + tokens > limit:
            break
        result.append(item)
        used += tokens

    return result


def _top_vector_paths(
    vector_chunks: List[dict],
    scope: Scope,
    *,
    limit: int | None = None,
) -> list[str]:
    """Unique top-scoring vector hit paths (scope-filtered), up to `limit`."""
    cap = limit if limit is not None else settings.CONTEXT_VECTOR_FETCH_TOP_FILES
    ordered = sorted(
        vector_chunks,
        key=lambda c: float(c.get("score") or 0),
        reverse=True,
    )
    paths: list[str] = []
    seen: set[str] = set()
    for vc in ordered:
        if len(paths) >= cap:
            break
        path = vc.get("path")
        if not isinstance(path, str) or not path:
            continue
        try:
            path = sanitize_repo_path(path)
        except ValueError:
            continue
        if not path_allowed_for_scope(path, scope) or path in seen:
            continue
        seen.add(path)
        paths.append(path)
    return paths


def assign_target_files(
    plan: dict,
    vector_chunks: List[dict],
    *,
    repo_paths: List[str] | None = None,
    issue: dict | None = None,
    max_files: int | None = None,
) -> dict:
    """
    Build files_to_modify from planner paths plus top vector-search hits, and
    files_to_fetch as the union (for GitHub load). Planner paths come first.
    Scope uses a backend denylist.
    """
    limit = max_files if max_files is not None else settings.CONTEXT_TARGET_MAX_FILES
    scope: Scope = resolve_scope(plan, issue or {})
    repo_set = set(repo_paths or [])

    planner_paths_raw = collect_plan_target_paths(plan)
    planner_paths = filter_paths_by_scope(planner_paths_raw, scope)
    # Trust explicit planner paths when scope heuristics over-filter (e.g. prometheus.yml + scope=backend).
    if not planner_paths and planner_paths_raw:
        planner_paths = planner_paths_raw
    vector_paths = _top_vector_paths(vector_chunks, scope)

    modify_targets: list[str] = []
    seen: set[str] = set()

    def add_modify(path: str) -> None:
        if path in seen or len(modify_targets) >= limit:
            return
        if not path_allowed_for_scope(path, scope):
            return
        seen.add(path)
        modify_targets.append(path)

    for path in planner_paths:
        try:
            add_modify(sanitize_repo_path(path))
        except ValueError:
            continue

    if not modify_targets:
        raise ValueError(
            "Planner listed file paths but none passed scope validation. "
            f"Listed paths: {planner_paths}. Scope: {scope}. "
            "For frontend-only issues, list client-side paths only; for backend-only, list server paths."
        )

    planner_modify_set = set(modify_targets)

    for path in vector_paths:
        try:
            add_modify(sanitize_repo_path(path))
        except ValueError:
            continue

    fetch_targets: list[str] = []
    fetch_seen: set[str] = set()

    def add_fetch(path: str) -> None:
        if path in fetch_seen:
            return
        if not path_allowed_for_scope(path, scope):
            return
        fetch_seen.add(path)
        fetch_targets.append(path)

    for path in modify_targets:
        add_fetch(path)
    for path in vector_paths:
        add_fetch(path)

    files_to_create = [p for p in modify_targets if p not in repo_set]
    plan["files_to_modify"] = modify_targets
    plan["files_to_fetch"] = fetch_targets
    plan["scope"] = scope
    plan["_targets_from_plan_hints"] = True
    plan["_vector_modify_paths"] = [p for p in modify_targets if p not in planner_modify_set]
    plan["_vector_context_paths"] = [p for p in vector_paths if p not in set(modify_targets)]
    if files_to_create:
        plan["_files_to_create"] = files_to_create
    if vector_paths:
        plan["_files_from_vector_search"] = True
    return plan


def prepare_repo_files_for_targets(
    planned_paths: List[str],
    files: List[dict],
    repo_paths: List[str],
) -> tuple[List[dict], List[str]]:
    """
    Allow new files from the plan (empty placeholder content) and attach reference paths.
    Returns (updated_files, reference_paths).
    """
    file_paths = {f["path"] for f in files}
    create_paths = [p for p in planned_paths if p not in file_paths]
    refs: list[str] = []
    for new_path in create_paths:
        files.append({"path": new_path, "content": ""})
        refs.extend(find_reference_paths(new_path, repo_paths))
    return files, refs


def expand_write_allowlist(
    plan: dict,
    repo_files: list[dict],
    extra_paths: list[str],
    *,
    repo_url: str,
    max_total_files: int | None = None,
) -> tuple[dict, list[dict], list[str]]:
    """
    Merge LLM-requested paths into files_to_modify, fetch missing bodies from GitHub,
    and return updated plan, repo_files, and the expanded target path list.
    """
    from app.services import github_service

    cap = max_total_files if max_total_files is not None else settings.CONTEXT_ALLOWLIST_MAX_FILES
    allowed = list(plan.get("files_to_modify") or [])
    seen = set(allowed)
    added: list[str] = []

    for raw in extra_paths:
        try:
            path = sanitize_repo_path(raw)
        except ValueError:
            continue
        if path in seen:
            continue
        if len(allowed) >= cap:
            break
        seen.add(path)
        allowed.append(path)
        added.append(path)

    if not added:
        raise ValueError("No valid extra paths to expand allowlist.")

    plan = dict(plan)
    plan["files_to_modify"] = allowed
    plan["_allowlist_expanded"] = True

    file_map = {f["path"]: f["content"] for f in repo_files}
    need_fetch = [p for p in added if p not in file_map]
    if need_fetch:
        fetched = github_service.get_file_contents(repo_url, need_fetch)
        repo_files = github_service.merge_repo_files(repo_files, fetched)

    return plan, repo_files, allowed


def _resolve_relative_import(current_file: str, level: int, module: str | None) -> List[str]:
    base = posixpath.dirname(current_file)
    for _ in range(level - 1):
        base = posixpath.dirname(base)

    if module:
        module_path = module.replace(".", "/")
        resolved_base = posixpath.join(base, module_path)
        return [
            f"{resolved_base}.py",
            f"{resolved_base}/__init__.py",
        ]
    return [posixpath.join(base, "__init__.py")]


def _parse_local_imports(
    file_content: str,
    current_file: str,
    all_paths: Set[str],
) -> List[str]:
    try:
        tree = ast.parse(file_content)
    except SyntaxError:
        return []

    candidates: List[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module_path = alias.name.replace(".", "/")
                candidates += [
                    f"{module_path}.py",
                    f"{module_path}/__init__.py",
                ]
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                candidates += _resolve_relative_import(
                    current_file, node.level, node.module
                )
            elif node.module:
                module_path = node.module.replace(".", "/")
                candidates += [
                    f"{module_path}.py",
                    f"{module_path}/__init__.py",
                ]

    resolved = []
    for candidate in candidates:
        if candidate in all_paths:
            resolved.append(candidate)
        else:
            matches = [p for p in all_paths if p.endswith(f"/{candidate}") or p == candidate]
            resolved.extend(matches)

    return list(set(resolved))


def resolve_dependencies(
    seed_paths: List[str],
    all_files: List[dict],
    max_depth: int = 3,
) -> List[dict]:
    file_map: Dict[str, str] = {f["path"]: f["content"] for f in all_files}
    all_paths: Set[str] = set(file_map.keys())

    visited: Set[str] = set()
    queue: List[str] = [p for p in seed_paths if p in file_map]
    depth = 0

    while queue and depth < max_depth:
        next_queue = []
        for path in queue:
            if path in visited or path not in file_map:
                continue
            visited.add(path)
            deps = _parse_local_imports(file_map[path], path, all_paths)
            for dep in deps:
                if dep not in visited:
                    next_queue.append(dep)
        queue = next_queue
        depth += 1

    return [
        {"path": p, "content": file_map[p]}
        for p in visited
        if p in file_map
    ]


def build_context(
    planned_paths: List[str],
    vector_chunks: List[dict],
    all_files: List[dict],
    *,
    reference_paths: List[str] | None = None,
    context_paths: List[str] | None = None,
    plan_hints_only: bool = False,
) -> List[dict]:
    """
    Build context for the code writer.

    - files_to_modify (planned_paths): always full GitHub file bodies
    - context_paths: supplementary full files (e.g. top vector hits), not edit targets
    - Other vector hits: snippets when full file unavailable, subject to token cap
    """
    file_map: Dict[str, str] = {f["path"]: f["content"] for f in all_files}
    target_set = set(planned_paths)
    seen: Set[str] = set()
    result: List[dict] = []

    def append(path: str, text: str, source: str) -> None:
        if path in seen:
            return
        if not text.strip() and source not in ("target_new", "target_full"):
            return
        seen.add(path)
        result.append({"path": path, "chunk": text, "source": source})

    # 1. Target files — full GitHub content (or placeholder for new files)
    for path in planned_paths:
        if path not in file_map:
            append(path, "", "target_new")
            continue
        append(path, file_map[path], "target_full")

    # 2. Python import deps for targets (supplementary)
    for f in resolve_dependencies(planned_paths, all_files):
        if f["path"] not in target_set:
            append(f["path"], f["content"], "target_dep")

    # 2b. Reference templates for new files (similar existing pages/API modules)
    for path in reference_paths or []:
        if path in file_map and path not in target_set:
            append(path, file_map[path], "reference_template")

    # 2c. Explicit context paths (planner fetch list + top vector hits)
    for path in context_paths or []:
        if path in target_set or path in seen:
            continue
        if path in file_map:
            append(path, file_map[path], "vector_context")

    # 3. Remaining Qdrant hits — snippets or full files when not already included
    related_added = 0
    related_limit = 2 if plan_hints_only else 12
    for vc in vector_chunks:
        if plan_hints_only and related_added >= related_limit:
            break
        path = vc.get("path")
        if not isinstance(path, str) or not path or path in target_set or path in seen:
            continue
        if path in file_map:
            append(path, file_map[path], "related_full")
            related_added += 1
        else:
            chunk_text = vc.get("chunk") or vc.get("text")
            if isinstance(chunk_text, str):
                append(path, chunk_text, "related_snippet")
                related_added += 1

    return cap_context(result, priority_paths=target_set)
