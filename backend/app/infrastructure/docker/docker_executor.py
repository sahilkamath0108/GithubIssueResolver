import docker
from typing import Tuple

_client = docker.from_env()

_TEST_IMAGE = "python:3.11-slim"
_TIMEOUT = 60  # seconds


def run_tests(generated_code: dict) -> Tuple[str, bool]:
    """
    Run generated code in an isolated Docker container.
    Deterministic — no LLM involved.

    Args:
        generated_code: {file_path: content} dict from code writer

    Returns:
        (output_logs, passed) tuple
    """
    if not generated_code:
        return "No code to execute.", False

    # Build inline test script from generated files
    script_parts = []
    for file_path, content in generated_code.items():
        script_parts.append(f"# === {file_path} ===\n{content}")

    script = "\n\n".join(script_parts)
    command = ["python", "-c", script]

    try:
        container = _client.containers.run(
            _TEST_IMAGE,
            command=command,
            detach=True,
            mem_limit="256m",
            network_disabled=True,  # sandbox — no network access
            remove=False,
        )
        result = container.wait(timeout=_TIMEOUT)
        logs = container.logs(stdout=True, stderr=True).decode("utf-8", errors="ignore")
        container.remove()

        passed = result["StatusCode"] == 0
        return logs, passed

    except Exception as e:
        return str(e), False


def run_code(container_image: str, command: str) -> str:
    """
    Generic code runner — kept for backward compatibility.
    """
    container = _client.containers.run(container_image, command, detach=True)
    result = container.logs().decode("utf-8", errors="ignore")
    container.remove()
    return result
