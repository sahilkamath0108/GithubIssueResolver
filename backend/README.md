# Backend

Python FastAPI + Celery backend for the GitHub Issue Resolver multi-agent system.

**Full setup, architecture, API reference, and troubleshooting:** see the [project README](../README.md) at the repository root.

## Quick commands

From repo root:

```bash
docker compose up --build
curl http://localhost:8000/health
```

From `backend/` (CLI indexing):

```bash
pip install -r requirements.txt
python scripts/index_repo.py owner/name
```

API docs when running: [http://localhost:8000/docs](http://localhost:8000/docs)
