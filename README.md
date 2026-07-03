# GitHub Issue Resolver — Multi-Agent Orchestration System

An autonomous backend that reads GitHub issues, searches your codebase with vector embeddings, generates fixes with an LLM, and opens a Pull Request — without cloning the repository locally.

**Typical flow:** submit an issue URL → agent plans the fix → indexes/searches code in Qdrant → writes patches → (optionally) runs tests → opens a PR.

---

## Table of contents

- [How it works](#how-it-works)
- [Architecture](#architecture)
- [Tech stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Quick start (Docker — recommended)](#quick-start-docker--recommended)
- [Environment variables](#environment-variables)
- [First-time setup checklist](#first-time-setup-checklist)
- [Usage](#usage)
- [Repository indexing](#repository-indexing)
- [GitHub webhooks](#github-webhooks)
- [Workflow details](#workflow-details)
- [API reference](#api-reference)
- [Project structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [Known limitations](#known-limitations)
- [Development](#development)

---

## How it works

1. **You provide** a GitHub issue URL and the repository URL (must be the **same repo**).
2. **Planner (Groq)** reads the issue and outputs a high-level plan + a **code-oriented search query** (keywords that match source text, not vague descriptions).
3. **Code reader (deterministic)**  
   - Ensures the repo is indexed in **Qdrant** (full / incremental / skip by commit SHA)  
   - Runs **semantic search** filtered by `payload.repo = owner/name`  
   - Picks **target files** from top vector hits  
   - Loads **full file content from GitHub** for those targets (Qdrant is used to choose paths, not as the sole file body)
4. **Code writer (Groq)** generates full-file patches from plan + context.
5. **Executor (Docker)** optionally runs generated code in a sandbox (see [Known limitations](#known-limitations)).
6. **PR creator (GitHub API)** commits to a branch and opens a pull request.

LLM calls happen in three places: **plan**, **write**, **fix** (on test failure). Indexing, search, GitHub I/O, and PR creation are deterministic.

---

## Architecture

```
                    ┌─────────────┐
  GitHub webhook ──►│   FastAPI   │──► PostgreSQL (tasks, logs, index state, DLQ)
  POST /submit  ──► │   :8000     │
                    └──────┬──────┘
                           │ enqueue
                    ┌──────▼──────┐
                    │    Redis    │
                    └──────┬──────┘
                           │
                    ┌──────▼──────────────────────────────────────────┐
                    │              Celery worker                       │
                    │  LangGraph: plan → read_code → write_code →     │
                    │             execute → fix? → create_pr / dlq     │
                    └──────┬───────────────┬──────────────┬────────────┘
                           │               │              │
                     Groq (chat)      Ollama (embed)   GitHub API
                           │               │              │
                           │          ┌────▼────┐         │
                           │          │ Qdrant  │         │
                           │          │ vectors │         │
                           │          └─────────┘         │
                           │                              │
                     Docker (tests) ◄─────────────────────┘
```

**Services in `docker-compose.yml`:**

| Service   | Port   | Role                                      |
|-----------|--------|-------------------------------------------|
| `backend` | 8000   | FastAPI HTTP API                          |
| `frontend`| 3000   | React web UI (nginx → proxies `/api`)     |
| `worker`  | —      | Celery + LangGraph workflow               |
| `postgres`| 5432   | Tasks, logs, repo index state, DLQ        |
| `redis`   | 6379   | Celery broker + LLM response cache        |
| `qdrant`  | 6333   | Code chunk embeddings (local dev)         |

**External (not in Compose by default):**

- **Ollama** on the host — embeddings only (`OLLAMA_EMBEDDING_MODEL`, e.g. `nomic-embed-text`)
- **Groq** — chat LLM for agents (`GROQ_API_KEY`)
- **GitHub** — issues, repo files, PRs (`GITHUB_TOKEN`)

---

## Tech stack

| Layer        | Technology                          |
|--------------|-------------------------------------|
| API          | FastAPI, Uvicorn                    |
| Jobs         | Celery 5, Redis                     |
| Workflow     | LangGraph                           |
| Chat LLM     | Groq API                            |
| Embeddings   | Ollama HTTP API                     |
| Vector DB    | Qdrant                              |
| Database     | PostgreSQL 15, SQLAlchemy 2         |
| GitHub       | PyGithub (no local git clone)       |
| Runtime      | Python 3.11, Docker Compose         |

---

## Prerequisites

- **Docker Desktop** (Windows/macOS) or Docker Engine + Compose (Linux)
- **Git**
- **GitHub Personal Access Token** with `repo` scope ([create one](https://github.com/settings/tokens))
- **Groq API key** ([console.groq.com](https://console.groq.com))
- **Ollama** installed on the host with an embedding model:
  ```bash
  ollama pull nomic-embed-text
  ```
- (Optional) **Qdrant Cloud** instead of the local Qdrant container — set `QDRANT_URL` + `QDRANT_API_KEY`

> **Windows note:** Celery workers are not supported natively on Windows; use Docker for the worker.

---

## Quick start (Docker — recommended)

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd githubIssueClone
```

### 2. Create environment file

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:

```env
GITHUB_TOKEN=ghp_...
GROQ_API_KEY=gsk_...

# Local Qdrant from docker-compose (inside containers):
QDRANT_URL=http://qdrant:6333

# Ollama on your host machine (Docker Desktop):
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
```

On **Linux**, if `host.docker.internal` is unavailable, use your host IP or add to `docker-compose.yml`:

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

### 3. Start the stack

```bash
docker compose up --build
```

Wait until you see the backend and worker running without import errors.

### 4. Verify health

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

Open interactive API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

**Web UI:** [http://localhost:3000](http://localhost:3000) — use the dashboard to index repos, submit issues, and track tasks (no Swagger required).

### 5. Index a repository (required before workflow search works well)

```bash
curl -X POST http://localhost:8000/api/v1/indexing/sync \
  -H "Content-Type: application/json" \
  -d "{\"repo\":\"YOUR_GITHUB_USER/YOUR_REPO\"}"
```

Response `mode` is `full`, `incremental`, or `skipped` depending on commit state.

### 6. Submit an issue to resolve

```bash
curl -X POST http://localhost:8000/api/v1/workflow/submit \
  -H "Content-Type: application/json" \
  -d "{
    \"issue_url\": \"https://github.com/YOUR_USER/YOUR_REPO/issues/1\",
    \"repo_url\": \"https://github.com/YOUR_USER/YOUR_REPO\"
  }"
```

Save the returned `task_uuid`, then poll:

```bash
curl http://localhost:8000/api/v1/workflow/<task_uuid>/status
curl http://localhost:8000/api/v1/logs/<task_uuid>/logs
```

When `status` is `success`, `result_pr_url` contains the opened PR link.

---

## Environment variables

Copy from [`.env.example`](.env.example). Key variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | Postgres connection string. Use `@postgres:5432` inside Docker. |
| `REDIS_URL` | Yes | Redis for Celery + LLM cache. Use `redis://redis:6379/0` in Docker. |
| `GITHUB_TOKEN` | Yes | PAT with `repo` scope. |
| `GITHUB_WEBHOOK_SECRET` | Recommended | HMAC secret for GitHub issue webhooks. |
| `GROQ_API_KEY` | Yes | Groq chat API key. |
| `GROQ_MODEL` | No | Default `llama-3.3-70b-versatile`. |
| `QDRANT_URL` | Yes | `http://qdrant:6333` (Compose) or Qdrant Cloud HTTPS URL. |
| `QDRANT_API_KEY` | Cloud | Required for Qdrant Cloud. |
| `QDRANT_COLLECTION` | No | Default `repo_code_chunks`. |
| `OLLAMA_BASE_URL` | Yes | Host Ollama URL reachable from containers. |
| `OLLAMA_EMBEDDING_MODEL` | Yes | e.g. `nomic-embed-text` (must support `/api/embeddings`). |
| `API_KEY` | No | If set, all routes except `/health` and `/docs` need header `X-API-Key`. |
| `WORKFLOW_SKIP_TESTS` | No | `true` skips Docker test step (dev only; PRs still open). |
| `MAX_CONTEXT_TOKENS` | No | Token budget for supplementary context (target files are never truncated). |
| `CONTEXT_SEARCH_TOP_K` | No | Max Qdrant hits for file selection (default 12). |

---

## First-time setup checklist

- [ ] Docker Compose stack is up (`backend`, `worker`, `postgres`, `redis`, `qdrant`)
- [ ] `curl localhost:8000/health` returns OK
- [ ] Ollama is running: `curl http://localhost:11434/api/tags`
- [ ] Embedding model pulled: `ollama pull nomic-embed-text`
- [ ] `.env` has valid `GITHUB_TOKEN`, `GROQ_API_KEY`, `QDRANT_URL`, `OLLAMA_BASE_URL`
- [ ] Target repo indexed via `/api/v1/indexing/sync`
- [ ] Issue and repo URLs refer to the **same** repository

---

## Usage

### Submit workflow manually

`issue_url` and `repo_url` **must match the same GitHub repository** (validated at API layer).

```json
POST /api/v1/workflow/submit
{
  "issue_url": "https://github.com/owner/repo/issues/42",
  "repo_url": "https://github.com/owner/repo"
}
```

### Monitor progress

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/workflow/{uuid}/status` | Task status, step, PR URL, errors |
| `GET /api/v1/logs/{uuid}/logs` | Step-by-step logs with metadata (plan, Qdrant hits, LLM tails) |
| `GET /api/v1/status/tasks` | List all tasks |
| `POST /api/v1/workflow/{uuid}/retry` | Re-queue a failed task |

### API key (optional)

If `API_KEY` is set in `.env`:

```bash
curl -H "X-API-Key: your-secret" ...
```

---

## Repository indexing

Indexing uses the **GitHub API only** (no clone): walk git tree → fetch blobs → chunk → Ollama embeddings → upsert to Qdrant.

**Single sync endpoint** decides full vs incremental vs skip:

```
POST /api/v1/indexing/sync
{ "repo": "owner/name", "force_full": false }
```

| Mode | When |
|------|------|
| `full` | First index, `force_full`, or Qdrant empty for repo |
| `incremental` | Stored commit ≠ GitHub tip; diff by blob SHA |
| `skipped` | Already indexed at latest commit |

**CLI (same logic):**

```bash
cd backend
pip install -r requirements.txt
python scripts/index_repo.py owner/name
python scripts/index_repo.py owner/name --force-full
```

Each workflow run also calls `sync_repo` in the `read_code` step to keep the index fresh.

**Qdrant payload fields:** `repo`, `path`, `text`, `commit_sha`, etc. Search filters on `repo = owner/name`.

---

## GitHub webhooks

Automate issue handling:

1. In GitHub → **Settings → Webhooks → Add webhook**
2. **Payload URL:** `https://YOUR_PUBLIC_URL/api/v1/webhooks/github/issues`
3. **Content type:** `application/json`
4. **Secret:** same as `GITHUB_WEBHOOK_SECRET` in `.env`
5. **Events:** Issues only

On `opened`, `edited`, `reopened`, or `labeled`, a task is created and the workflow is enqueued (same as `/workflow/submit`).

**Local testing:** use [ngrok](https://ngrok.com/) or Cloudflare Tunnel to expose port 8000, or test manually with `/workflow/submit`.

---

## Workflow details

LangGraph node sequence:

```
plan → read_code → write_code → execute → create_pr
                              ↘ fix → execute (loop, max retries)
                              ↘ dlq (max retries exceeded)
```

### `plan`
- Fetches issue from GitHub.
- Groq returns `changes`, `test_cases`, `search_query` (dense code keywords for embedding search).
- Does **not** choose file paths.

### `read_code`
- Syncs Qdrant index for `owner/name`.
- Fetches repo files from GitHub (filtered by extension).
- Embeds `search_query` → Qdrant `query_points` (top-K, repo filter).
- Sets `files_to_modify` from vector hit paths.
- Fetches **full GitHub content** for each target file (individual API call if missing from bulk fetch).
- Builds LLM context: targets always full files; related chunks may be trimmed by token cap.

### `write_code`
- Groq outputs JSON `{ "changes": [{ "path", "content" }] }`.
- Only paths in `files_to_modify` are allowed.

### `execute`
- Runs concatenated files via `python -c` in Docker (see limitations).
- Set `WORKFLOW_SKIP_TESTS=true` to bypass during development.

### `fix` / `create_pr` / `dlq`
- Fix agent retries on test failure (Groq).
- PR creator commits each file to `agent/fix-task-{id}-...` branch.
- DLQ records exhausted failures in Postgres.

---

## API reference

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/api/v1/workflow/submit` | Queue issue workflow |
| GET | `/api/v1/workflow/{uuid}/status` | Task status |
| POST | `/api/v1/workflow/{uuid}/retry` | Retry failed task |
| GET | `/api/v1/status/tasks` | List tasks |
| GET | `/api/v1/logs/{uuid}/logs` | Task logs |
| POST | `/api/v1/indexing/sync` | Index/sync repository |
| POST | `/api/v1/webhooks/github/issues` | GitHub Issues webhook |

Full OpenAPI spec: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Project structure

```
githubIssueClone/
├── docker-compose.yml          # Postgres, Redis, Qdrant, backend, worker
├── .env.example                # Copy to .env at repo root
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/   # REST + webhooks
│   │   ├── core/               # settings, celery, middleware
│   │   ├── db/                 # SQLAlchemy, init, partitions
│   │   ├── domain/
│   │   │   ├── agents/         # planner, code_writer, fix_agent
│   │   │   └── graph/          # LangGraph nodes + workflow_graph
│   │   ├── indexing/           # GitHub tree, chunk, Ollama, Qdrant
│   │   ├── services/           # GitHub, Groq LLM, Qdrant search, context
│   │   ├── tasks/              # Celery tasks
│   │   └── main.py
│   ├── scripts/index_repo.py   # CLI indexing
│   ├── Dockerfile
│   ├── Dockerfile.worker       # Mounts Docker socket for test runner
│   └── requirements.txt
└── frontend/                   # React + Vite web UI (port 3000 in Docker)
```

---

## Troubleshooting

### Worker crashes on startup
- Check logs: `docker compose logs worker`
- Common: missing `workflow_graph.py`, bad imports, Postgres not ready.

### `Network is unreachable` / Ollama errors
- Containers cannot reach `localhost:11434`. Use `OLLAMA_BASE_URL=http://host.docker.internal:11434` (Windows/macOS).
- Confirm Ollama is running on the host.

### Qdrant 403 / 400
- **403:** set `QDRANT_API_KEY` for Qdrant Cloud.
- **400 index required:** payload indexes on `repo` and `path` are created automatically on index; ensure worker/backend use latest code.

### `No target files found from Qdrant search`
- Run `/indexing/sync` for the repo first.
- Improve issue/search_query quality (planner uses code-like keywords).
- Verify points exist in Qdrant UI with `repo: "owner/name"`.

### `Issue repo does not match repo_url`
- `issue_url` and `repo_url` must point to the same GitHub repository.

### `no partition of relation "task_logs"`
- Restart stack so `init_db` creates monthly partitions (fixed in recent versions).

### Bad PRs / wrong language files
- Ensure index + search ran successfully (check logs for `target_full` sources).
- Do not use `WORKFLOW_SKIP_TESTS=true` in production.
- Test runner is Python-only; React/JS projects need custom test strategy.

### Groq empty response / JSON errors
- Use a valid chat model ID in `GROQ_MODEL`.
- Check worker logs for `llm_raw_tail` in task logs metadata.

---

## Known limitations

- **Test runner** concatenates all generated files into `python -c` — not suitable for React/Node projects as-is.
- **Python-only import graph** for dependency expansion; JS/TS imports are not resolved via AST.
- **Planner runs before repo context** — file selection depends on Qdrant search quality.
- **Webhook `edited`/`labeled`** enqueues a new workflow each time (no deduplication yet).
- **Celery broker URL** in code is hardcoded to `redis://redis:6379` (matches Compose; change if deploying elsewhere).

---

## Development

### Run API locally (without Docker worker)

Requires local Postgres, Redis, Qdrant, and `.env` with `127.0.0.1` hostnames instead of Docker service names.

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Run worker separately (Linux/macOS):

```bash
celery -A app.core.celery_app worker -Q main_queue,retry_queue,dlq_queue --loglevel=info
```

### Frontend (web UI)

**Docker (recommended):** included in `docker compose up --build` — open [http://localhost:3000](http://localhost:3000).

**Local dev** (requires Node.js 20.19+ or 22.12+):

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). Vite proxies `/api` and `/health` to `localhost:8000`.

**Pages:**

| Route | Purpose |
|-------|---------|
| `/` | Dashboard — stats, recent tasks, quick actions |
| `/submit` | Submit a GitHub issue workflow |
| `/tasks` | List and filter all tasks |
| `/tasks/:uuid` | Live status, logs, PR link, retry |
| `/repositories` | Sync repo index + manage connected repos |
| `/settings` | API key and optional base URL (stored in browser) |

If `API_KEY` is set on the backend, enter it in **Settings** so requests include the `X-API-Key` header.

### Useful log fields

In `GET /api/v1/logs/{uuid}/logs`, look for:

- `Node succeeded: plan` → `plan.search_query`
- `Qdrant vector search` → `hits`, `paths`
- `Context built` → `files_to_modify`, `sources` (`target_full`, `related_snippet`, …)
- `Node succeeded: write_code` → `decoded_preview`

---

## License

MIT — see repository license file if present.
