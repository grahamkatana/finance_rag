from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "rag_finance",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.tasks.audit",  # task modules to auto-discover
    ],
)

# Celery configuration
celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Timezone
    timezone="UTC",
    enable_utc=True,

    # Task behavior
    task_track_started=True,
    task_acks_late=True,          # only ack after task completes
    worker_prefetch_multiplier=1, # one task at a time per worker

    # Result expiry
    result_expires=86400,         # keep results 24 hours

    # Retry policy
    task_max_retries=3,
    task_default_retry_delay=60,  # retry after 60 seconds
)