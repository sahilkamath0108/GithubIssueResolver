from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from celery import Celery

from app.core.settings import settings


def _celery_redis_url(redis_url: str) -> str:
    """Normalize Redis URL for Celery/kombu (TLS requires ssl_cert_reqs on rediss://)."""
    parsed = urlparse(redis_url)
    params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if parsed.scheme == "rediss" and "ssl_cert_reqs" not in params:
        params["ssl_cert_reqs"] = "CERT_NONE"
    return urlunparse(parsed._replace(query=urlencode(params)))


def _redis_backend_url(redis_url: str) -> str:
    """Use database 1 for Celery results when broker is database 0."""
    # Upstash and some hosted Redis providers only expose database 0.
    if "upstash.io" in redis_url:
        return redis_url
    parsed = urlparse(redis_url)
    path = parsed.path or "/0"
    if path.endswith("/0"):
        path = path[:-2] + "/1"
    elif path in ("", "/"):
        path = "/1"
    return urlunparse(parsed._replace(path=path))


_broker_url = _celery_redis_url(settings.REDIS_URL)

celery_app = Celery(
    "multiagent",
    broker=_broker_url,
    backend=_redis_backend_url(_broker_url),
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
    import logging

    from app.db.init_db import init
    from app.indexing.qdrant_store import QdrantVectorStore

    logger = logging.getLogger(__name__)
    init()
    try:
        store = QdrantVectorStore()
        store.ensure_payload_indexes()
        store.close()
    except Exception as exc:
        logger.warning("Could not ensure Qdrant payload indexes at worker startup: %s", exc)
