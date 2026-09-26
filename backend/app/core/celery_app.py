"""Celery application configuration for asynchronous analysis jobs."""
import os
from celery import Celery

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "analyst_tasks",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["backend.app.tasks.analysis_tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 min hard limit
)
