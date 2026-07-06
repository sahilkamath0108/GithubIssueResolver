"""Issue scope, plan path hints, and architecture-aware path filtering."""

from __future__ import annotations

import posixpath
import re
from typing import Literal

Scope = Literal["frontend", "backend", "fullstack"]

_VALID_SCOPES: frozenset[str] = frozenset({"frontend", "backend", "fullstack"})

_PATH_IN_TEXT = re.compile(
    r"(?<![\w./-])((?:[\w.-]+/)+[\w.-]+\.(?:tsx?|jsx?|mjs|cjs|py|go|rs|java|vue|svelte|ya?ml|json|toml))\b",
    re.IGNORECASE,
)
# Root-level config files often mentioned in DevOps issues (no directory prefix).
_ROOT_CONFIG_IN_TEXT = re.compile(
    r"(?<![\w./-])(docker-compose[\w.-]*\.ya?ml|prometheus[\w.-]*\.ya?ml|\.env\.example)\b",
    re.IGNORECASE,
)

_FRONTEND_ONLY = re.compile(
    r"\b(?:no backend(?:\s+changes?)?|frontend[- ]only|ui[- ]only|client[- ]side only)\b",
    re.IGNORECASE,
)
_BACKEND_ONLY = re.compile(
    r"\b(?:no frontend(?:\s+changes?)?|frontend[- ]only|ui[- ]only|client[- ]side only)\b",
    re.IGNORECASE,
)
_DEVOPS_INFRA = re.compile(
    r"\b(?:prometheus|grafana|docker[- ]compose|host\.docker\.internal|scrape config|"
    r"monitoring stack|kubernetes|helm chart)\b",
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
    # Prometheus / Compose / scrape targets span services — not UI-only backend API work.
    if _DEVOPS_INFRA.search(text):
        return "fullstack"
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
        for match in _ROOT_CONFIG_IN_TEXT.finditer(change):
            raw = match.group(1).replace("\\", "/").strip("./")
            key = raw.lower()
            if key in seen:
                continue
            seen.add(key)
            paths.append(raw)
    return paths


def collect_plan_target_paths(plan: dict) -> list[str]:
    """Planner files_to_modify plus any paths mentioned in change descriptions."""
    paths: list[str] = []
    seen: set[str] = set()

    def add(raw: str) -> None:
        p = raw.replace("\\", "/").strip().strip("./")
        if not p:
            return
        key = p.lower()
        if key in seen:
            return
        seen.add(key)
        paths.append(p)

    for raw in plan.get("files_to_modify") or []:
        if isinstance(raw, str):
            add(raw)
    for path in extract_paths_from_plan(plan):
        add(path)
    return paths


_INFRA_PREFIXES = (
    "monitoring/",
    "deploy/",
    "deployment/",
    "ops/",
    "infra/",
    "k8s/",
    "kubernetes/",
    "helm/",
    ".github/",
    "prometheus/",
    "grafana/",
)


def is_infra_path(path: str) -> bool:
    """Docker, Prometheus, CI, and other ops/config paths (not UI)."""
    normalized = path.replace("\\", "/").lower()
    base = posixpath.basename(normalized)
    if base.startswith("docker-compose") and base.endswith((".yml", ".yaml")):
        return True
    if base in ("docker-compose.yml", "docker-compose.yaml", "prometheus.yml", "prometheus.yaml"):
        return True
    if "prometheus" in normalized or "grafana" in normalized:
        return True
    if normalized.endswith((".yml", ".yaml")) and any(
        seg in normalized for seg in ("monitoring", "deploy", "prometheus", "grafana", "docker")
    ):
        return True
    return any(normalized.startswith(p) or f"/{p}" in normalized for p in _INFRA_PREFIXES)


def is_backend_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    if normalized.startswith("frontend/"):
        return False
    if is_infra_path(path):
        return True
    if any(normalized.startswith(p) or f"/{p}" in normalized for p in ("server/", "backend/")):
        return True
    return any(marker in normalized for marker in _BACKEND_MARKERS)


def is_frontend_path(path: str) -> bool:
    """Client-side scope: any path that is not clearly server/backend."""
    return not is_backend_path(path)


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


def is_extra_path_related_to_targets(
    extra_path: str,
    target_paths: list[str],
    repo_files: list[dict] | None = None,
) -> bool:
    """
    True when an LLM-requested extra file is plausibly required alongside plan targets
    (same directory, shared API utils folder, or referenced from a target file).
    """
    if not target_paths:
        return False
    extra = extra_path.replace("\\", "/")
    extra_dir = posixpath.dirname(extra)
    extra_base = posixpath.basename(extra)

    for target in target_paths:
        t = target.replace("\\", "/")
        t_dir = posixpath.dirname(t)
        if extra_dir == t_dir:
            return True
        if "/utils/apis/" in extra and "/utils/apis/" in t:
            return True
        if "/utils/providers/" in extra and "/utils/providers/" in t:
            return True
        if "/components/" in extra and "/components/" in t:
            return True

    if repo_files:
        file_map = {f["path"]: f.get("content") or "" for f in repo_files}
        import_name = extra_base.rsplit(".", 1)[0]
        for target in target_paths:
            content = file_map.get(target, "")
            if not content:
                continue
            if extra in content or import_name in content or extra_base in content:
                return True
            if f"from './{import_name}'" in content or f'from "./{import_name}"' in content:
                return True
            if f"from '@/utils/apis/{import_name}'" in content:
                return True

    return False


def filter_related_extra_paths(
    extra_paths: list[str],
    target_paths: list[str],
    repo_files: list[dict] | None = None,
    *,
    max_extra: int,
) -> tuple[list[str], list[str]]:
    """Split extras into (related, unrelated), capping related count."""
    related: list[str] = []
    unrelated: list[str] = []
    seen: set[str] = set()
    for raw in extra_paths:
        if raw in seen:
            continue
        seen.add(raw)
        if is_extra_path_related_to_targets(raw, target_paths, repo_files):
            if len(related) < max_extra:
                related.append(raw)
        else:
            unrelated.append(raw)
    return related, unrelated
