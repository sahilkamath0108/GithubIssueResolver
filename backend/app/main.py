from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.routes import api_router
from app.core.middleware import APIKeyMiddleware
from app.core.csrf import CSRFMiddleware
from app.core.security import validate_production_settings
from app.core.settings import settings
from app.db.init_db import init
from app.indexing.qdrant_store import QdrantVectorStore

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init()
    try:
        store = QdrantVectorStore()
        store.ensure_payload_indexes()
        store.close()
    except Exception as exc:
        logger.warning("Could not ensure Qdrant payload indexes at startup: %s", exc)
    provider_dim = settings.provider_embedding_dim
    if (
        provider_dim
        and settings.QDRANT_EMBEDDING_DIM
        and provider_dim != settings.QDRANT_EMBEDDING_DIM
    ):
        logger.warning(
            "QDRANT_EMBEDDING_DIM=%s conflicts with %s output dim %s; "
            "using provider dim. Update .env: QDRANT_EMBEDDING_DIM=%s",
            settings.QDRANT_EMBEDDING_DIM,
            settings.EMBEDDING_PROVIDER,
            provider_dim,
            provider_dim,
        )
    for msg in validate_production_settings():
        if settings.is_production:
            logger.error("Production configuration issue: %s", msg)
            raise RuntimeError(msg)
        logger.warning("Configuration warning: %s", msg)
    yield


app = FastAPI(
    title="Multi-Agent Orchestration System",
    lifespan=lifespan,
    docs_url="/docs" if settings.EXPOSE_DOCS else None,
    redoc_url="/redoc" if settings.EXPOSE_DOCS else None,
    openapi_url="/openapi.json" if settings.EXPOSE_DOCS else None,
)

_cors_origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]
if settings.FRONTEND_ORIGIN:
    _cors_origins.append(settings.FRONTEND_ORIGIN.rstrip("/"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(CSRFMiddleware)
app.add_middleware(APIKeyMiddleware)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "ok", "environment": settings.ENVIRONMENT}
