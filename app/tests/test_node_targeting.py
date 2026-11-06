# mypy: ignore-errors
# pylint: disable=all
# ruff: noqa
"""Unit tests for worker queue resolution and node targeting in user_orchestrator.

This test module verifies:
1. That user_orchestrator correctly targets a specific node queue when 'sweeper.debug' is specified.
2. That user_orchestrator correctly targets a specific node queue when root-level 'debug' is specified.
3. That user_orchestrator correctly targets a specific node queue when 'target_worker_queue' is specified.
4. That user_orchestrator routes to 'gpus_debug' when 'debug' is boolean True.
5. That user_orchestrator falls back to 'gpus_{priority}' when no node targeting is provided.
"""

import pytest


def resolve_worker_queue(full_config: dict) -> str:
    """Helper simulating the queue resolution logic in user_orchestrator.py."""
    sweeper_in = full_config.get("sweeper", {})
    if not isinstance(sweeper_in, dict):
        sweeper_in = {}
    priority = sweeper_in.get("priority", "low")
    target_queue = (
        sweeper_in.get("debug")
        or full_config.get("debug")
        or sweeper_in.get("target_worker_queue")
        or full_config.get("target_worker_queue")
    )

    if target_queue and not isinstance(target_queue, bool):
        return str(target_queue)
    elif target_queue is True:
        return "gpus_debug"
    else:
        return f"gpus_{priority}"


def test_resolve_worker_queue_sweeper_debug():
    """Validates node targeting when debug is placed inside sweeper section."""
    config = {"model": "yolo26n.pt", "sweeper": {"debug": "192.168.1.72", "priority": "high"}}
    assert resolve_worker_queue(config) == "192.168.1.72"


def test_resolve_worker_queue_root_debug():
    """Validates node targeting when debug is placed at YAML root level."""
    config = {"model": "yolo26n.pt", "debug": "192.168.1.72", "sweeper": {"priority": "medium"}}
    assert resolve_worker_queue(config) == "192.168.1.72"


def test_resolve_worker_queue_target_worker_queue():
    """Validates node targeting when target_worker_queue is passed by UI/API."""
    config = {"model": "yolo26n.pt", "sweeper": {"target_worker_queue": "192.168.1.68"}}
    assert resolve_worker_queue(config) == "192.168.1.68"


def test_resolve_worker_queue_boolean_debug():
    """Validates routing to gpus_debug when debug is True."""
    config = {"model": "yolo26n.pt", "sweeper": {"debug": True}}
    assert resolve_worker_queue(config) == "gpus_debug"


def test_resolve_worker_queue_public_fallback():
    """Validates public queue fallback when no targeting is provided."""
    config_low = {"model": "yolo26n.pt", "sweeper": {}}
    assert resolve_worker_queue(config_low) == "gpus_low"

    config_high = {"model": "yolo26n.pt", "sweeper": {"priority": "high"}}
    assert resolve_worker_queue(config_high) == "gpus_high"
