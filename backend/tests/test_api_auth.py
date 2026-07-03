import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("GITHUB_TOKEN", "test-token")
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("API_KEY", "test-api-key")


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr("app.core.settings.settings.API_KEY", "test-api-key")
    monkeypatch.setattr("app.core.settings.settings.RATE_LIMIT_ENABLED", False)
    from app.main import app

    return TestClient(app)


def test_health_public(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_protected_route_without_key(client):
    res = client.post(
        "/api/v1/workflow/submit",
        json={
            "issue_url": "https://github.com/o/r/issues/1",
            "repo_url": "https://github.com/o/r",
        },
    )
    assert res.status_code == 401


def test_webhook_route_public_without_api_key(client, monkeypatch):
    monkeypatch.setattr("app.core.settings.settings.GITHUB_WEBHOOK_SECRET", "")
    monkeypatch.setattr("app.core.settings.settings.REQUIRE_WEBHOOK_SECRET", False)
    res = client.post(
        "/api/v1/webhooks/github/issues",
        json={"action": "opened", "issue": {}, "repository": {}},
    )
    # Missing payload fields → 400, not 401 (webhook auth is separate from API key)
    assert res.status_code != 401
