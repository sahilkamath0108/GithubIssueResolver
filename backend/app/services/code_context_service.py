"""
Code Context Service — deterministic, no LLM.

Combines GitHub file contents with Qdrant vector hits (filtered by repo payload)
into a token-capped context for the code writer.
"""
import ast
import posixpath
from typing import List, Dict, Set

from app.core.settings import settings


_CHARS_PER_TOKEN = 4


def _estimate_tokens(text: str) -> int:
    return len(text) // _CHARS_PER_TOKEN


def cap_context(chunks: List[dict], max_tokens: int = None) -> List[dict]:
    limit = max_tokens or settings.MAX_CONTEXT_TOKENS
    result = []
    used = 0

    for item in chunks:
        tokens = _estimate_tokens(item.get("chunk", "") + item.get("content", ""))
        if used + tokens > limit:
            break
        result.append(item)
        used += tokens

    return result


def reconcile_plan_files(
    plan: dict,
    vector_chunks: List[dict],
    repo_paths: Set[str],
    *,
    max_files: int = 5,
) -> dict:
    """
    Ensure files_to_modify point at real repo paths.
    If the planner invented paths, replace them with top Qdrant vector hits.
    """
    planned = list(plan.get("files_to_modify") or [])
    valid = [p for p in planned if p in repo_paths]
    if valid:
        plan["files_to_modify"] = valid[:max_files]
        return plan

    from_vector: list[str] = []
    seen: set[str] = set()
    for vc in vector_chunks:
        path = vc.get("path")
        if isinstance(path, str) and path and path not in seen:
            seen.add(path)
            from_vector.append(path)

    if from_vector:
        plan["files_to_modify"] = from_vector[:max_files]
        plan["_plan_reconciled_from_vector"] = True
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
    Build context for the code writer:

    1. Planned repo files (+ Python import deps when applicable)
    2. Qdrant vector hits — full GitHub file when available, else indexed chunk text
    3. Python import deps discovered from vector-hit paths
    """
    file_map: Dict[str, str] = {f["path"]: f["content"] for f in all_files}
    seen: Set[str] = set()
    result: List[dict] = []

    def append(path: str, text: str, source: str) -> None:
        if path in seen or not text.strip():
            return
        seen.add(path)
        result.append({"path": path, "chunk": text, "source": source})

    # 1. Explicit planner paths (+ transitive Python deps)
    for f in resolve_dependencies(planned_paths, all_files):
        append(f["path"], f["content"], "planned")

    # 2. Qdrant hits — always inject chunk text; prefer full file from GitHub when we have it
    for vc in vector_chunks:
        path = vc.get("path")
        if not isinstance(path, str) or not path:
            continue
        if path in file_map:
            append(path, file_map[path], "vector_full")
        else:
            chunk_text = vc.get("chunk") or vc.get("text")
            if isinstance(chunk_text, str):
                append(path, chunk_text, "vector_chunk")

    # 3. Python deps for vector paths present in the repo (may add files not in top-k)
    vector_paths = [
        c["path"]
        for c in vector_chunks
        if isinstance(c.get("path"), str) and c["path"] in file_map
    ]
    for f in resolve_dependencies(vector_paths, all_files):
        append(f["path"], f["content"], "vector_dep")

    return cap_context(result)
