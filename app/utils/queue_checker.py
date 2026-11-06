"""Celery queue inspection and task waiting helpers for distributed training."""

import time
from typing import Any, Optional
from celery.result import AsyncResult


def check_queue_active(app_instance: Any, queue_name: str) -> bool:
    """Verify that at least one worker is actively subscribed to the target queue.

    Args:
        app_instance (Any): Celery application instance.
        queue_name (str): Name of the queue to inspect.

    Returns:
        bool: True if queue is registered, False otherwise.
    """
    try:
        inspector = app_instance.control.inspect()
        queues_data = inspector.active_queues()
        if not queues_data:
            return False

        for worker_queues in queues_data.values():
            for q in worker_queues:
                if q.get("name") == queue_name:
                    return True
        return False
    except Exception:
        return True


def wait_for_result(job: AsyncResult) -> Optional[Any]:
    """Poll safely until Celery task finishes and return outcome payload.

    Args:
        job (AsyncResult): Celery asynchronous result proxy.

    Returns:
        Optional[Any]: Result dictionary if successful, or None on failure.
    """
    try:
        while not job.ready():
            time.sleep(1)

        if job.successful():
            return job.result
        return None
    except Exception:
        return None
