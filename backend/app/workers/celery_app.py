"""Celery application configuration for LectureForge AI.

Configures asynchronous task execution using Redis broker, JSON message serialization,
task routing, late acks, and concurrency limits for background document processing
and study pack generation pipelines.
"""

from __future__ import annotations

import logging
import os

from celery import Celery

from app.core.config import settings

logger = logging.getLogger(__name__)

# Initialize Celery application
celery_app = Celery(
    "lectureforge",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.tasks"],
)

# Apply Celery configuration
celery_app.conf.update(
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Time and Localization
    timezone="UTC",
    enable_utc=True,
    # Worker and Reliability Settings
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    worker_concurrency=int(os.environ.get("CELERY_CONCURRENCY", 2)),
    # Task Routes
    task_routes={
        "app.workers.tasks.process_document": {"queue": "default"},
        "app.workers.tasks.generate_study_pack": {"queue": "default"},
        "app.workers.tasks.regenerate_section": {"queue": "default"},
    },
    # Results expiration (1 day)
    result_expires=86400,
)
