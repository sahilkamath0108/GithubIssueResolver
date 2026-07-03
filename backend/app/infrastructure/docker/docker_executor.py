import base64
from typing import Tuple

import docker

from app.core.settings import settings

_client = docker.from_env()

_PYTHON_IMAGE = "python:3.11-slim"
_NODE_IMAGE = "node:22-alpine"
_TIMEOUT = 60
_CONTAINER_KWARGS = {
    "detach": True,
    "mem_limit": "256m",
    "network_disabled": True,
    "cap_drop": ["ALL"],
    "security_opt": ["no-new-privileges:true"],
    "user": "65534:65534",
    "remove": False,
    "tmpfs": {"/tmp": "size=64m"},
}


def _cleanup_container(container) -> None:
    if container is None:
        return
    try:
        container.remove(force=True)
    except Exception:
        pass


def _run_container(image: str, command: list[str]) -> Tuple[str, bool]:
    container = None
    try:
        container = _client.containers.run(image, command=command, **_CONTAINER_KWARGS)
        result = container.wait(timeout=_TIMEOUT)
        logs = container.logs(stdout=True, stderr=True).decode("utf-8", errors="ignore")
        return logs, result.get("StatusCode", 1) == 0
    except Exception as exc:
        return str(exc), False
    finally:
        _cleanup_container(container)


def _run_python_combined(generated_code: dict) -> Tuple[str, bool]:
    script_parts = []
    for file_path, content in generated_code.items():
        script_parts.append(f"# === {file_path} ===\n{content}")
    script = "\n\n".join(script_parts)
    return _run_container(_PYTHON_IMAGE, ["python", "-c", script])


def _run_node_syntax_check(generated_code: dict) -> Tuple[str, bool]:
    outputs = []
    all_ok = True
    for file_path, content in generated_code.items():
        if not file_path.endswith((".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs")):
            continue
        b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
        safe_name = file_path.replace("/", "_").replace("..", "")
        shell = f"echo {b64} | base64 -d > /tmp/{safe_name} && node --check /tmp/{safe_name}"
        logs, ok = _run_container(_NODE_IMAGE, ["sh", "-c", shell])
        outputs.append(f"=== {file_path} ===\n{logs}")
        all_ok = all_ok and ok
    if not outputs:
        return "No JS/TS files to syntax-check.", False
    return "\n".join(outputs), all_ok


def run_tests(generated_code: dict) -> Tuple[str, bool]:
    if not generated_code:
        return "No code to execute.", False

    paths = list(generated_code.keys())
    py_only = all(p.endswith(".py") for p in paths)
    has_js = any(p.endswith((".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs")) for p in paths)

    if py_only:
        return _run_python_combined(generated_code)
    if has_js and not any(p.endswith(".py") for p in paths):
        return _run_node_syntax_check(generated_code)

    return (
        "Mixed or unsupported file types for automated validation. "
        "Use Python-only or JS/TS-only changes, or set WORKFLOW_SKIP_TESTS for dev.",
        False,
    )


def run_code(container_image: str, command: str) -> str:
    logs, passed = _run_container(container_image, ["sh", "-c", command])
    return logs if passed else f"FAILED: {logs}"
