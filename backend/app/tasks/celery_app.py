"""
Celery application configuration.
"""
from celery import Celery
from app.core.config import settings

# Create Celery app
celery_app = Celery(
    "cloud_platform",
    broker=getattr(settings, "CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=getattr(settings, "CELERY_RESULT_BACKEND", "redis://localhost:6379/0"),
    include=[
        "app.tasks.iso_tasks",
        "app.tasks.vm_tasks",
        "app.tasks.sync_tasks",
    ]
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max per task
    task_soft_time_limit=3000,  # 50 minutes soft limit
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

# Celery Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    "sync-storage-pools-every-5-minutes": {
        "task": "app.tasks.sync_tasks.sync_all_storage_pools",
        "schedule": 300.0,  # 5 minutes
    },
}
