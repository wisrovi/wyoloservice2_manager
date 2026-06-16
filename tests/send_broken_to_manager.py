"""Test sending broken config to manager."""

import os
import sys

import yaml  # pylint: disable=import-error
from celery import Celery  # pylint: disable=import-error

# Ensure the parent directory is in the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

REDIS_HOST = os.getenv("CONTROL_HOST", "192.168.10.252")
REDIS_URL = f"redis://{REDIS_HOST}:23437/0"

app = Celery("tester", broker=REDIS_URL, backend=REDIS_URL)


def test_robustness():
    """Test the robustness of the manager with broken configs."""
    yaml_path = os.path.join(os.path.dirname(__file__), "test_broken_config.yaml")

    with open(yaml_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    print(f"[*] Sending BROKEN configuration (only study_name: {config['sweeper']['study_name']})")

    result = app.send_task("tasks.manage_study", args=[config], queue="managers")

    print(f"✅ Task Sent! ID: {result.id}")
    print("[*] Now check: docker logs wyolo_manager -f")


if __name__ == "__main__":
    test_robustness()
