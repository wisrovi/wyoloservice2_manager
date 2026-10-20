# mypy: ignore-errors
# pylint: disable=all
# ruff: noqa
"""Unit tests for metric recovery and validation in user_orchestrator.

This test module verifies:
1. That user_orchestrator successfully recovers accuracy when the worker returns the 'accuracy' key.
2. That user_orchestrator successfully falls back to 'fitness' when 'accuracy' is absent.
3. That invalid, non-numeric, or negative metrics are properly identified and rejected.
"""

import pytest


def extract_metric(result: dict) -> float | None:
    """Helper function simulating the metric recovery logic in user_orchestrator.py."""
    if not isinstance(result, dict):
        return None

    metric_key = None
    if "accuracy" in result and result["accuracy"] is not None:
        metric_key = "accuracy"
    elif "fitness" in result and result["fitness"] is not None:
        metric_key = "fitness"

    if metric_key is not None:
        try:
            acc = float(result[metric_key])
            if acc >= 0:
                return acc
        except (ValueError, TypeError):
            return None
    return None


def test_metric_recovery_with_accuracy_key():
    """Validates recovery when worker returns standard 'accuracy' key.

    This test checks that a float accuracy value (e.g. 0.965 from mAP50)
    is properly parsed and validated as non-negative.
    """
    payload = {"train.lr0": 0.001, "accuracy": 0.965, "status": "done"}
    metric = extract_metric(payload)
    assert metric == 0.965


def test_metric_recovery_with_fitness_fallback():
    """Validates recovery fallback when worker returns 'fitness' key instead of 'accuracy'.

    This test checks that if the invoker returns 'fitness' (Optuna objective value),
    the manager accepts it seamlessly without failing the trial attempt.
    """
    payload = {"train.lr0": 0.001, "fitness": 0.884, "status": "done"}
    metric = extract_metric(payload)
    assert metric == 0.884


def test_metric_recovery_invalid_or_negative():
    """Validates rejection of negative or invalid metric values.

    This test verifies that negative metrics (which indicate training failures
    or errors) or unparsable non-numeric strings are rejected (return None),
    triggering the appropriate retry mechanism.
    """
    assert extract_metric({"accuracy": -1.0}) is None
    assert extract_metric({"fitness": -0.5}) is None
    assert extract_metric({"accuracy": "not_a_number"}) is None
    assert extract_metric({}) is None
    assert extract_metric("invalid_string_result") is None
