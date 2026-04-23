from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.db.init_db import init
from app.api.v1.routes import api_router
from app.core.middleware import APIKeyMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    init()
    yield


app = FastAPI(title="Multi-Agent Orchestration System", lifespan=lifespan)

app.add_middleware(APIKeyMiddleware)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "ok"}
