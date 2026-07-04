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


def assign_target_files(
    plan: dict,
    vector_chunks: List[dict],
    *,
    max_files: int = 5,
) -> dict:
    """
    Pick files_to_modify from Qdrant semantic search hits.
    Paths are chosen by vector rank only; full content is loaded from GitHub later.
    """
    targets: list[str] = []
    seen: set[str] = set()
    for vc in vector_chunks:
        path = vc.get("path")
        if not isinstance(path, str) or not path or path in seen:
            continue
        try:
            path = sanitize_repo_path(path)
        except ValueError:
            continue
        seen.add(path)
        targets.append(path)

    if not targets:
        raise ValueError(
            "No target files found from Qdrant search. "
            "Ensure the repo is indexed and search_query matches indexed code."
        )

    plan["files_to_modify"] = targets[:max_files]
    plan["_files_from_vector_search"] = True
    return plan


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
) -> List[dict]:
    """
    Build context for the code writer.

    - files_to_modify: always full GitHub file bodies (never Qdrant snippets alone)
    - Other vector hits: supplementary full files or snippets, subject to token cap
    """
    file_map: Dict[str, str] = {f["path"]: f["content"] for f in all_files}
    target_set = set(planned_paths)
    seen: Set[str] = set()
    result: List[dict] = []

    def append(path: str, text: str, source: str) -> None:
        if path in seen or not text.strip():
            return
        seen.add(path)
        result.append({"path": path, "chunk": text, "source": source})

    # 1. Target files — full GitHub content only
    for path in planned_paths:
        if path not in file_map:
            continue
        append(path, file_map[path], "target_full")

    # 2. Python import deps for targets (supplementary)
    for f in resolve_dependencies(planned_paths, all_files):
        if f["path"] not in target_set:
            append(f["path"], f["content"], "target_dep")

    # 3. Other Qdrant hits (not edit targets) — context only
    for vc in vector_chunks:
        path = vc.get("path")
        if not isinstance(path, str) or not path or path in target_set or path in seen:
            continue
        if path in file_map:
            append(path, file_map[path], "related_full")
        else:
            chunk_text = vc.get("chunk") or vc.get("text")
            if isinstance(chunk_text, str):
                append(path, chunk_text, "related_snippet")

    return cap_context(result, priority_paths=target_set)
