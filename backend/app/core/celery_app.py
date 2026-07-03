from urllib.parse import urlparse, urlunparse

from celery import Celery

from app.core.settings import settings


def _redis_backend_url(redis_url: str) -> str:
    """Use database 1 for Celery results when broker is database 0."""
    parsed = urlparse(redis_url)
    path = parsed.path or "/0"
    if path.endswith("/0"):
        path = path[:-2] + "/1"
    elif path in ("", "/"):
        path = "/1"
    return urlunparse(parsed._replace(path=path))


celery_app = Celery(
    "multiagent",
    broker=settings.REDIS_URL,
    backend=_redis_backend_url(settings.REDIS_URL),
    include=[
        "app.tasks.workflow_tasks",
        "app.tasks.retry_tasks",
        "app.tasks.dlq_tasks",
    ],
)

celery_app.conf.task_routes = {
    "app.tasks.workflow_tasks.*": {"queue": "main_queue"},
    "app.tasks.retry_tasks.*": {"queue": "retry_queue"},
    "app.tasks.dlq_tasks.*": {"queue": "dlq_queue"},
}


@celery_app.on_after_configure.connect
def _ensure_db_partitions(**_kwargs):
    from app.db.init_db import init

    init()
