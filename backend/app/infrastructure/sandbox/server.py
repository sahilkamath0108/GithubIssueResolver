"""Minimal HTTP service — sole component with Docker socket access."""
from __future__ import annotations

import hmac

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from app.core.settings import settings
from app.infrastructure.docker.docker_executor import run_tests

app = FastAPI(title="Sandbox Runner", docs_url=None, redoc_url=None)


class ValidateRequest(BaseModel):
    files: dict[str, str] = Field(default_factory=dict)


class ValidateResponse(BaseModel):
    output: str
    passed: bool


def _verify_secret(provided: str | None) -> None:
    expected = settings.SANDBOX_RUNNER_SECRET
    if not expected:
        if settings.is_production:
            raise HTTPException(status_code=503, detail="SANDBOX_RUNNER_SECRET is not configured.")
        return
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="Invalid sandbox secret.")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/validate", response_model=ValidateResponse)
def validate_code(
    payload: ValidateRequest,
    x_sandbox_secret: str | None = Header(default=None, alias="X-Sandbox-Secret"),
):
    _verify_secret(x_sandbox_secret)
    if not payload.files:
        raise HTTPException(status_code=400, detail="No files provided.")
    if len(payload.files) > 20:
        raise HTTPException(status_code=400, detail="Too many files (max 20).")
    output, passed = run_tests(payload.files)
    return ValidateResponse(output=output, passed=passed)
