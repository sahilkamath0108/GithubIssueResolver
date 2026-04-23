from fastapi import APIRouter
from app.api.v1.endpoints import workflow, status, logs, indexing, webhooks

api_router = APIRouter()

api_router.include_router(workflow.router, prefix="/workflow", tags=["workflow"])
api_router.include_router(status.router, prefix="/status", tags=["status"])
api_router.include_router(logs.router, prefix="/logs", tags=["logs"])
api_router.include_router(indexing.router, prefix="/indexing", tags=["indexing"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
