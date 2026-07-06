# GitHub Issue Resolver

Multi-agent system that reads a GitHub issue, plans a fix, searches your codebase with vector retrieval, writes patches, validates them, and opens a pull request — without cloning the repo locally.

**Live demo:** [githubissueresolver.me](https://githubissueresolver.me)

---

## How it works

```
plan → read_code → write_code → execute ↔ fix → create_pr | dlq
```

1. **Planner (Groq)** — issue → plan, search query, target files  
2. **Code reader** — sync index, Qdrant semantic search, fetch file content from GitHub  
3. **Writer (Groq)** — full-file patches for allowed paths  
4. **Executor** — isolated sandbox (Docker syntax validation)  
5. **PR creator** — commits to a branch and opens a PR  

Long-running workflows run asynchronously via **Celery + Redis** so the API stays responsive.

---

## Architecture

**Docker (local machine)** runs the app. **Postgres, Redis, and Qdrant** use managed cloud services (same URLs in `.env` for local dev and deploy).

```
Browser → nginx (frontend :3000) → FastAPI (backend)
                                        │
                                        ▼
                                  Celery worker
                                        │
        ┌───────────────────────────────┼───────────────────────────────┐
        ▼                               ▼                               ▼
  Supabase (Postgres)            Upstash (Redis)                 Qdrant Cloud
        │                               │                               │
        └───────────────────────────────┴───────────────────────────────┘
                                        │
                          Groq API · Jina API · GitHub API · sandbox
```

| Runs in Docker | Cloud (configured in `.env`) |
|----------------|------------------------------|
| `frontend`, `backend`, `worker`, `sandbox` | **Supabase** — Postgres |
| | **Upstash** — Redis (Celery broker + cache) |
| | **Qdrant Cloud** — code embeddings / search |

---

## Tech stack

| Layer | Technology |
|-------|------------|
| API | FastAPI, Uvicorn |
| Jobs | Celery, Redis (Upstash) |
| Workflow | LangGraph |
| Chat LLM | Groq (BYOK — add keys in UI after login) |
| Embeddings | Jina v5 (BYOK) |
| Vector DB | Qdrant Cloud |
| Database | PostgreSQL (Supabase) |
| Auth | GitHub OAuth |
| UI | React, Vite, nginx |

---

## Prerequisites

- Docker Desktop (recommended) or Docker Engine + Compose  
- [GitHub OAuth App](https://github.com/settings/developers) — callback `http://localhost:3000/api/v1/auth/github/callback`  
- [Groq](https://console.groq.com/keys) + [Jina](https://jina.ai/) API keys — entered in the UI after login  
- Free-tier cloud accounts:
  - [Supabase](https://supabase.com) — Postgres (`DATABASE_URL`, use **session pooler** URI + `?sslmode=require`)
  - [Upstash](https://upstash.com) — Redis (`REDIS_URL` as `rediss://...`)
  - [Qdrant Cloud](https://cloud.qdrant.io) — vectors (`QDRANT_URL` + `QDRANT_API_KEY`)

---

## Quick start

```bash
git clone <your-repo-url>
cd githubIssueClone
cp .env.example .env
```

Edit `.env` with your cloud connection strings and GitHub OAuth settings. Leave `GROQ_API_KEY` / `JINA_API_KEY` empty for BYOK in the UI.

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

`docker-compose.prod.yml` skips the local Postgres, Redis, and Qdrant containers — the app talks to your cloud services via `.env`.

Open [http://localhost:3000](http://localhost:3000)

1. Sign in with GitHub  
2. Add Groq + Jina API keys (popup or Settings)  
3. **Repositories** → sync a repo  
4. **Submit** an issue URL → track task → PR link when done  

Health check: `curl http://localhost:3000/health`

---

## Environment variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | Supabase session pooler URI (`postgresql://postgres.<ref>:...@....pooler.supabase.com:5432/postgres?sslmode=require`) |
| `REDIS_URL` | Upstash Redis URL (`rediss://default:...@....upstash.io:6379`) |
| `QDRANT_URL` / `QDRANT_API_KEY` | Qdrant Cloud HTTPS endpoint + API key |
| `QDRANT_EMBEDDING_DIM` | `1024` for Jina v5 |
| `GITHUB_OAUTH_*` | OAuth client ID, secret, callback (`http://localhost:3000/api/v1/auth/github/callback`) |
| `GROQ_API_KEY` / `JINA_API_KEY` | Optional; empty = per-user keys in Settings |

Full list: [`.env.example`](.env.example)

---

## Fully local stack (optional)

To run Postgres, Redis, and Qdrant in Docker instead of cloud services, use local URLs in `.env` and:

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build
```

See [`.env.example`](.env.example) for `postgres:5432`, `redis:6379`, and `http://qdrant:6333` values.

---

## API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/workflow/submit` | Queue issue workflow |
| GET | `/api/v1/workflow/{uuid}/status` | Task status + PR URL |
| POST | `/api/v1/workflow/{uuid}/cancel` | Cancel running task |
| POST | `/api/v1/indexing/sync` | Index/sync repository |
| GET | `/api/v1/logs/{uuid}/logs` | Task logs |

---

## Project structure

```
githubIssueClone/
├── docker-compose.yml          # App services (backend, worker, frontend, sandbox)
├── docker-compose.prod.yml     # Disable local DB containers — use cloud .env URLs
├── docker-compose.local.yml    # Optional: containerized Postgres/Redis/Qdrant
├── backend/
├── frontend/
└── .env.example
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Supabase `Network is unreachable` from Docker | Use **session pooler** host (IPv4), not direct `db.*` hostname |
| Celery / Upstash SSL error | Use `rediss://` URL; app sets `ssl_cert_reqs` for Celery automatically |
| OAuth redirect error | Callback URL must match GitHub OAuth app exactly |
| No vector hits | Sync repo first; set `QDRANT_EMBEDDING_DIM=1024` |
| Groq / Jina errors | Add keys in Settings after login |

---

## License

MIT — see repository license file if present.
