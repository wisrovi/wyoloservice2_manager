


"""Celery configuration module for the Manager component.

This module initializes the Celery application with settings optimized for
long-running orchestration tasks, including trial sequencing and result persistence.
"""

import os
from typing import Any
import celery.result
from celery import Celery

# Get Redis URL from environment
REDIS_URL = os.getenv("REDIS_URL")

if not REDIS_URL:
    # Fallback to CONTROL_HOST or localhost if REDIS_URL is not set
    REDIS_HOST = os.getenv("CONTROL_HOST", "localhost")
    REDIS_URL = f"redis://{REDIS_HOST}:23437/0"

app: Celery = Celery("gradio_launcher", broker=REDIS_URL, backend=REDIS_URL)

# Configuration for task routing
app.conf.task_routes = {
    "tasks.manage_study": {"queue": "managers"},
    "tasks.train_on_gpu": {"queue": "gpus"},
}

# Essential settings for long-running studies and nested task waiting
celery_settings: dict[str, Any] = {
    "task_acks_late": True,
    "worker_prefetch_multiplier": 1,
    "result_expires": 86400,  # 24 hours
    "task_always_eager": False,
    "result_persistent": True,
    "task_track_started": True,
}

app.conf.update(celery_settings)

# Allow .get() inside tasks, required for Optuna trial orchestration
# This is a critical setting for the Manager to wait for Invoker results
import celery.result

celery.result.allow_join_result()
