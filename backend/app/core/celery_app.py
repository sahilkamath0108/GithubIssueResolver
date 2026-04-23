from celery import Celery

celery_app = Celery(
    "multiagent",
    broker="redis://redis:6379/0",
    backend="redis://redis:6379/1",
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