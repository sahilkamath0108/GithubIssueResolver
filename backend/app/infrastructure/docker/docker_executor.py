"""Syntax-only validation in hardened ephemeral containers — never executes agent code."""
from __future__ import annotations

import base64
import re
from typing import Tuple

import docker

from app.core.code_safety import scan_generated_code
from app.core.settings import settings

_client: docker.DockerClient | None = None

_PYTHON_IMAGE = "python:3.11-slim"
_NODE_IMAGE = "node:22-alpine"
_TIMEOUT = 60
_MAX_FILE_BYTES = 512_000
_SAFE_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")

_CONTAINER_KWARGS = {
    "detach": True,
    "mem_limit": "256m",
    "network_disabled": True,
    "cap_drop": ["ALL"],
    "security_opt": ["no-new-privileges:true"],
    "user": "65534:65534",
    "read_only": True,
    "pids_limit": 64,
    "privileged": False,
    "remove": False,
    "tmpfs": {"/tmp": "size=64m,noexec"},
}


def _get_client() -> docker.DockerClient:
    global _client
    if _client is None:
        _client = docker.from_env()
    return _client


def _cleanup_container(container) -> None:
    if container is None:
        return
    try:
        container.remove(force=True)
    except Exception:
        pass


def _safe_basename(file_path: str) -> str:
    name = file_path.replace("\\", "/").split("/")[-1].replace("..", "")
    if not name or not _SAFE_NAME.match(name):
        raise ValueError(f"Unsafe sandbox filename derived from: {file_path}")
    return name


def _run_container(image: str, command: list[str]) -> Tuple[str, bool]:
    container = None
    try:
        container = _get_client().containers.run(image, command=command, **_CONTAINER_KWARGS)
        result = container.wait(timeout=_TIMEOUT)
        logs = container.logs(stdout=True, stderr=True).decode("utf-8", errors="ignore")
        return logs, result.get("StatusCode", 1) == 0
    except Exception as exc:
        return str(exc), False
    finally:
        _cleanup_container(container)


def _write_file_command(image: str, safe_name: str, b64: str) -> list[str]:
    if "node" in image:
        return [
            "node",
            "-e",
            f"require('fs').writeFileSync('/tmp/{safe_name}', Buffer.from('{b64}', 'base64'))",
        ]
    return [
        "python",
        "-c",
        "import base64, pathlib; "
        f"pathlib.Path('/tmp/{safe_name}').write_bytes(base64.b64decode('{b64}'))",
    ]


def _write_and_check(image: str, check_cmd: list[str], file_path: str, content: str) -> Tuple[str, bool]:
    if len(content.encode("utf-8")) > _MAX_FILE_BYTES:
        return f"File too large for sandbox validation: {file_path}", False
    safe_name = _safe_basename(file_path)
    b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
    write_logs, write_ok = _run_container(image, _write_file_command(image, safe_name, b64))
    if not write_ok:
        return f"=== {file_path} (write failed) ===\n{write_logs}", False
    logs, ok = _run_container(image, check_cmd)
    return f"=== {file_path} ===\n{logs}", ok


def _run_python_syntax_check(generated_code: dict) -> Tuple[str, bool]:
    outputs: list[str] = []
    all_ok = True
    for file_path, content in generated_code.items():
        if not file_path.endswith(".py"):
            continue
        safe_name = _safe_basename(file_path)
        logs, ok = _write_and_check(
            _PYTHON_IMAGE,
            ["python", "-m", "py_compile", f"/tmp/{safe_name}"],
            file_path,
            content,
        )
        outputs.append(logs)
        all_ok = all_ok and ok
    if not outputs:
        return "No Python files to syntax-check.", False
    return "\n".join(outputs), all_ok


def _run_node_syntax_check(generated_code: dict) -> Tuple[str, bool]:
    outputs: list[str] = []
    all_ok = True
    for file_path, content in generated_code.items():
        if not file_path.endswith((".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs")):
            continue
        safe_name = _safe_basename(file_path)
        logs, ok = _write_and_check(
            _NODE_IMAGE,
            ["node", "--check", f"/tmp/{safe_name}"],
            file_path,
            content,
        )
        outputs.append(logs)
        all_ok = all_ok and ok
    if not outputs:
        return "No JS/TS files to syntax-check.", False
    return "\n".join(outputs), all_ok


def run_tests(generated_code: dict) -> Tuple[str, bool]:
    """
    Validate generated code via syntax checks only (py_compile / node --check).
    Does NOT execute agent-produced code.
    """
    if not generated_code:
        return "No code to validate.", False

    if settings.is_production and settings.WORKFLOW_SKIP_TESTS:
        return "WORKFLOW_SKIP_TESTS is forbidden in production.", False

    try:
        scan_generated_code(generated_code)
    except Exception as exc:
        return f"Code safety scan failed: {exc}", False

    paths = list(generated_code.keys())
    py_only = all(p.endswith(".py") for p in paths)
    has_js = any(p.endswith((".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs")) for p in paths)

    if py_only:
        return _run_python_syntax_check(generated_code)
    if has_js and not any(p.endswith(".py") for p in paths):
        return _run_node_syntax_check(generated_code)

    return (
        "Mixed or unsupported file types for automated validation. "
        "Use Python-only or JS/TS-only changes.",
        False,
    )
