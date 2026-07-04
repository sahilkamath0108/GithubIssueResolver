"""Call the isolated sandbox runner from worker/backend (no Docker socket required)."""
from __future__ import annotations

import httpx

from app.core.settings import settings
from app.infrastructure.docker.docker_executor import run_tests


def validate_generated_code(generated_code: dict[str, str]) -> tuple[str, bool]:
    """
    Validate via sandbox HTTP service when configured; otherwise local Docker (dev only).
    Production requires SANDBOX_RUNNER_URL.
    """
    if settings.is_production and not settings.SANDBOX_RUNNER_URL:
        return "SANDBOX_RUNNER_URL must be set in production.", False

    url = (settings.SANDBOX_RUNNER_URL or "").rstrip("/")
    if not url:
        return run_tests(generated_code)

    headers = {"Content-Type": "application/json"}
    if settings.SANDBOX_RUNNER_SECRET:
        headers["X-Sandbox-Secret"] = settings.SANDBOX_RUNNER_SECRET

    try:
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(
                f"{url}/validate",
                json={"files": generated_code},
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("output", ""), bool(data.get("passed"))
    except httpx.HTTPError as exc:
        return f"Sandbox runner error: {exc}", False
