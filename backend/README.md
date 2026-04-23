# Multi-Agent Orchestration System — Backend

An AI-powered backend that autonomously resolves GitHub issues by planning, writing, testing, and submitting code fixes as Pull Requests — with minimal LLM usage through hybrid deterministic + AI execution.

---

## Overview

Submit a GitHub issue URL and the system handles the rest:

1. Analyzes the issue and creates an execution plan (LLM)
2. Fetches relevant source files using vector search + AST dependency resolution (deterministic)
3. Generates a targeted code fix (LLM)
4. Runs the fix in an isolated Docker container to verify it works (deterministic)
5. Opens a Pull Request with the fix (deterministic)

LLM is used in exactly 3 places — planning, code generation, and error fixing. Everything else is deterministic.

---

## Tech Stack

| Layer          | Technology                            |
|----------------|---------------------------------------|
| API            | FastAPI + Uvicorn                     |
| Task Queue     | Celery 5 + Redis                      |
| Workflow       | LangGraph                             |
| LLM            | Ollama                                |
| Embeddings     | Ollama (embeddings API)               |
| Vector DB      | Qdrant                                |
| Database       | PostgreSQL 15 + SQLAlchemy 2          |
| GitHub         | PyGithub                              |
| Containers     | Docker + Docker Compose               |
| Language       | Python 3.11                           |

---

## Getting Started

### Prerequisites
- Docker and Docker Compose
- GitHub personal access token (with `repo` scope)
- Qdrant (hosted/remote is fine; Docker service included for local dev)
- Ollama (or any HTTP server compatible with `/api/embeddings`) for embedding models such as `nomic-embed-text`

### Setup

1. Clone the repository and navigate to the project root.

2. Create a `.env` file at the project root:

```env
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/multiagent_db
REDIS_URL=redis://redis:6379/0

GITHUB_TOKEN=your_github_token

# Repo indexing (GitHub API → Ollama → Qdrant)
QDRANT_URL=https://your-qdrant-host:6333
QDRANT_COLLECTION=repo_code_chunks
# If using Qdrant Cloud, set the API key (recommended)
QDRANT_API_KEY=your_qdrant_api_key
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_CHAT_MODEL=gemma4:e4b
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
# Optional: set when you must match an existing collection dimension
# QDRANT_EMBEDDING_DIM=768
```

On Linux hosts, replace `OLLAMA_BASE_URL` with your reachable Ollama URL (for example `http://172.17.0.1:11434`). Many coding models (including some Gemma tags) do **not** expose embeddings; use a dedicated embedding model unless you have confirmed `/api/embeddings` works for your tag.

3. Start all services:

```bash
docker-compose up --build
```

4. Verify everything is running:

```bash
curl http://localhost:8000/health
```

### Starting the app (quick reference)

From the **repository root** (where `docker-compose.yml` lives):

```bash
docker compose up --build
```

This starts PostgreSQL, Redis, Qdrant, the FastAPI **backend** on [http://localhost:8000](http://localhost:8000), and the Celery **worker**. Ollama is expected on the host unless you add an `ollama` service; point `OLLAMA_BASE_URL` at it (see `.env` example above).

To run the API **without** Docker (you must supply Postgres, Redis, Qdrant, and env vars yourself):

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## API Reference

| Method | Endpoint                           | Description                  |
|--------|------------------------------------|------------------------------|
| POST   | /api/v1/workflow/submit            | Submit a GitHub issue        |
| GET    | /api/v1/workflow/{uuid}/status     | Poll task status             |
| POST   | /api/v1/workflow/{uuid}/retry      | Retry a failed task          |
| GET    | /api/v1/status/tasks               | List all tasks               |
| GET    | /api/v1/logs/{uuid}/logs           | Get logs for a task          |
| POST   | /api/v1/indexing/sync              | Sync repo index (auto full / incremental / skip) |
| POST   | /api/v1/webhooks/github/issues     | GitHub Issues webhook (auto queue workflow) |
| GET    | /health                            | Health check                 |

Interactive docs available at `http://localhost:8000/docs`

### Example

```bash
curl -X POST http://localhost:8000/api/v1/workflow/submit \
  -H "Content-Type: application/json" \
  -d '{
    "issue_url": "https://github.com/owner/repo/issues/1",
    "repo_url": "https://github.com/owner/repo"
  }'
```

### Repo indexing (single endpoint)

`POST /api/v1/indexing/sync` compares the **latest default-branch commit** on GitHub to the commit stored in Postgres (`repo_index_state`). It then runs a **full** index (first time, forced, or if Qdrant has no vectors for that repo), an **incremental** update (path + blob SHA diff vs the stored commit’s tree), or returns **skipped** if the stored commit already matches GitHub.

Body: `{"repo":"owner/name"}` optional `"force_full": true` to wipe that repo’s vectors in Qdrant and reindex everything.

**Bash (no API key configured):**

```bash
curl -s -X POST http://localhost:8000/api/v1/indexing/sync \
  -H "Content-Type: application/json" \
  -d "{\"repo\":\"octocat/Hello-World\"}" | jq .
```

**If `API_KEY` is set in `.env`:**

```bash
curl -s -X POST http://localhost:8000/api/v1/indexing/sync \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d "{\"repo\":\"octocat/Hello-World\"}" | jq .
```

**PowerShell:**

```powershell
$body = @{ repo = "octocat/Hello-World"; force_full = $false } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/v1/indexing/sync" `
  -ContentType "application/json" -Body $body
```

**Using Swagger UI:** open [http://localhost:8000/docs](http://localhost:8000/docs), expand **indexing** → `POST /api/v1/indexing/sync` → **Try it out**.

**CLI (same logic as the API):** from `backend/` with the same env vars:

```bash
python scripts/index_repo.py owner/repo
python scripts/index_repo.py owner/repo --force-full
```

When an **issue** arrives (webhook or `/workflow/submit`), call `RepoIndexer(db).sync_repo("owner/repo")` once; do not choose full vs incremental in the caller—the indexer compares commits and blob SHAs for you.

**Requirements to test indexing successfully:** valid `GITHUB_TOKEN`, running **Qdrant** (`QDRANT_URL`), running **Ollama** with an embedding-capable model (`OLLAMA_EMBEDDING_MODEL`), and reachable **Postgres** so `repo_index_state` can be read and updated.

### GitHub webhook (Issues)

Endpoint: `POST /api/v1/webhooks/github/issues`

- Configure a GitHub webhook on your repo:
  - **Payload URL**: your public URL + `/api/v1/webhooks/github/issues`
  - **Content type**: `application/json`
  - **Secret**: set this to the same value as `GITHUB_WEBHOOK_SECRET` in `.env`
  - **Events**: enable **Issues**
- The handler verifies `X-Hub-Signature-256` **if** `GITHUB_WEBHOOK_SECRET` is set.
- For issue actions `opened|edited|reopened|labeled`, it creates a DB Task and enqueues the workflow (same as `/workflow/submit`).

Local testing options:
- Use GitHub’s “Recent deliveries → Redeliver” once you have a public URL (ngrok/cloudflared).
- Or use the `gh` CLI to create a real issue and let the webhook fire.

---

## Architecture

```
FastAPI → Redis → Celery Worker → LangGraph
                                      ├── Planner (LLM)
                                      ├── Code Reader (deterministic)
                                      ├── Code Writer (LLM)
                                      ├── Docker Executor (deterministic)
                                      ├── Fix Agent (LLM, max 2 retries)
                                      └── PR Creator (deterministic)
                                              ↓
                                        PostgreSQL
```

---

## Project Structure

```
backend/
├── app/
│   ├── api/v1/endpoints/       # REST endpoints
│   ├── core/                   # settings, celery config
│   ├── db/                     # session, migrations
│   ├── domain/
│   │   ├── agents/             # planner, code_writer, fix_agent
│   │   ├── graph/              # LangGraph nodes and workflow
│   │   └── state/              # shared workflow state schema
│   ├── infrastructure/
│   │   ├── docker/             # sandboxed code executor
│   │   └── queue/              # redis client
│   ├── models/                 # SQLAlchemy ORM models
│   ├── repositories/           # database query layer
│   ├── schemas/                # Pydantic request/response models
│   ├── indexing/                 # GitHub tree + chunk + Ollama + Qdrant
│   ├── services/
│   │   ├── llm_service.py          # Gemini + Redis caching
│   │   ├── github_service.py       # GitHub API integration
│   │   ├── qdrant_search_service.py # Qdrant vector search (workflow context)
│   │   └── code_context_service.py # AST dependency resolver
│   ├── tasks/                  # Celery task definitions
│   └── main.py                 # application entry point
├── Dockerfile
├── Dockerfile.worker
└── requirements.txt
```

---

## Implementation Notes

See [`docs/v1-implementation.md`](https://github.com/anujchauhann09/multi-agent-orchestration-system/blob/main/docs/v1-implementation.md) for detailed notes on what was built in v1, known gaps, and planned improvements.

---

## Contributing

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Commit using conventional commits: `feat:`, `fix:`, `chore:`, `docs:`
3. Open a Pull Request

---

## License

Open source under the [MIT License](https://opensource.org/licenses/MIT).
