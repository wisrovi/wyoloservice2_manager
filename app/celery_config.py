"""Celery configuration for Wyolo Manager."""

import os

from celery import Celery  # pylint: disable=import-error
from celery.result import AsyncResult  # pylint: disable=import-error,unused-import

# Use redis instead of rabbitmq
CONTROL_HOST = os.getenv("CONTROL_HOST", "192.168.10.252")
REDIS_URL = f"redis://{CONTROL_HOST}:23437/0"

app = Celery(
    "wyolo",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    result_expires=604800,  # 7 days (168 hours) to support extended multi-day training studies
    broker_transport_options={
        "visibility_timeout": 604800,  # 7 days (168 hours) to prevent task redelivery on Redis during training
    },
)
