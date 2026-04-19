# Celery application factory — broker and result backend on Redis, JSON-only serialization
from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_application = Celery(
    "smartspend",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_application.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# Autodiscover registers @celery_application.task decorators in the background_tasks module
celery_application.autodiscover_tasks(["app.tasks.background_tasks"])
