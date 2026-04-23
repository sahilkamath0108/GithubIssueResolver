"""
Code Context Service — deterministic, no LLM.

Responsibilities:
1. Parse import dependencies from Python files using AST
2. Resolve relative AND absolute imports using file path context
3. Resolve transitive dependencies up to max_depth levels
4. Combine planned files + their deps + vector search results
   into a deduplicated, token-capped context for the code writer agent.
"""
import ast
import posixpath
from typing import List, Dict, Set

from app.core.settings import settings


# ~4 characters per token is a reliable approximation for code
_CHARS_PER_TOKEN = 4


def _estimate_tokens(text: str) -> int:
    """Estimate token count from character count"""
    return len(text) // _CHARS_PER_TOKEN


def cap_context(chunks: List[dict], max_tokens: int = None) -> List[dict]:
    """
    Trim context chunks to fit within the token budget.
    Planned files (earlier in list) are always prioritized — they are added first
    and later chunks are dropped if the budget is exceeded.

    Args:
        chunks: list of {path, chunk} dicts, priority order (planned files first)
        max_tokens: token cap, defaults to settings.MAX_CONTEXT_TOKENS

    Returns:
        Trimmed list that fits within the token budget.
    """
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


def _resolve_relative_import(current_file: str, level: int, module: str | None) -> List[str]:
    """
    Resolve a relative import to candidate file paths.
    """
    # Start from the directory of the current file
    base = posixpath.dirname(current_file)

    # Each extra level goes one directory up
    for _ in range(level - 1):
        base = posixpath.dirname(base)

    if module:
        module_path = module.replace(".", "/")
        resolved_base = posixpath.join(base, module_path)
        return [
            f"{resolved_base}.py",
            f"{resolved_base}/__init__.py",
        ]
    else:
        # `from . import something` — the package __init__ is the anchor
        return [posixpath.join(base, "__init__.py")]


def _parse_local_imports(
    file_content: str,
    current_file: str,
    all_paths: Set[str],
) -> List[str]:
    """
    Parse all imports (absolute + relative) from a Python file.
    Returns only paths that actually exist in the repo.
    """
    try:
        tree = ast.parse(file_content)
    except SyntaxError:
        return []

    candidates: List[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            # e.g. import os.path  →  absolute only, check if local
            for alias in node.names:
                module_path = alias.name.replace(".", "/")
                candidates += [
                    f"{module_path}.py",
                    f"{module_path}/__init__.py",
                ]

        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                # Relative import — resolve using current file path
                candidates += _resolve_relative_import(
                    current_file, node.level, node.module
                )
            elif node.module:
                # Absolute import
                module_path = node.module.replace(".", "/")
                candidates += [
                    f"{module_path}.py",
                    f"{module_path}/__init__.py",
                ]

    # Filter to only paths that exist in the repo
    resolved = []
    for candidate in candidates:
        # Exact match
        if candidate in all_paths:
            resolved.append(candidate)
        else:
            # Suffix match — handles cases where repo root differs
            matches = [p for p in all_paths if p.endswith(f"/{candidate}") or p == candidate]
            resolved.extend(matches)

    return list(set(resolved))


def resolve_dependencies(
    seed_paths: List[str],
    all_files: List[dict],
    max_depth: int = 3,
) -> List[dict]:
    """
    Given seed file paths, recursively resolve all local import
    dependencies (absolute + relative) up to max_depth levels.

    Returns list of {path, content} dicts including seeds + all deps.
    """
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
            # Pass current file path so relative imports can be resolved
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
    Build complete, deduplicated context for the code writer:

    1. Start with files the planner explicitly identified
    2. Resolve all their import dependencies (absolute + relative, AST)
    3. Add files referenced in vector search results + their deps
    4. Deduplicate — planned files take priority

    Returns list of {path, chunk} dicts ready for the LLM prompt.
    """
    file_map: Dict[str, str] = {f["path"]: f["content"] for f in all_files}

    # Step 1+2: planned files + transitive deps
    dep_files = resolve_dependencies(planned_paths, all_files)
    dep_paths = {f["path"] for f in dep_files}

    # Step 3: vector search paths not already covered + their deps
    vector_paths = [
        c["path"] for c in vector_chunks
        if c["path"] not in dep_paths and c["path"] in file_map
    ]
    extra_files = resolve_dependencies(vector_paths, all_files)

    # Step 4: merge, deduplicate, planned files first
    seen: Set[str] = set()
    result: List[dict] = []

    for f in dep_files + extra_files:
        if f["path"] not in seen:
            seen.add(f["path"])
            result.append({"path": f["path"], "chunk": f["content"]})

    # Step 5: cap total context to token budget before returning to LLM
    return cap_context(result)
