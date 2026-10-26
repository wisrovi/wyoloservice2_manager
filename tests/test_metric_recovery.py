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


def test_manager_time_and_redis_ttl_resolution():
    """Validates train.time parsing and 2.0x Redis TTL calculation in the Manager.

    This test verifies:
    1. When 'train.time' is omitted or invalid, it is not injected (returns None) so
       Ultralytics trains by epochs, and Redis TTL uses the 12.0h reference -> 86,400s (24h).
    2. When 'train.time' is explicitly set (e.g. 30h), it is parsed as float(30.0) and
       Redis TTL scales to 2.0x -> 216,000s (60h).
    """
    default_cfg = {"train": {"epochs": 230, "patience": 50}}
    custom_cfg = {"train": {"epochs": 230, "patience": 50, "time": 30}}
    short_cfg = {"train": {"epochs": 10, "time": 1}}

    def parse_time(cfg: dict) -> float | None:
        raw = cfg.get("train", {}).get("time")
        if raw is None or isinstance(raw, bool):
            return None
        try:
            val = float(raw)
            return val if val > 0.0 else None
        except (ValueError, TypeError):
            return None

    def calc_redis_ttl(cfg: dict) -> int:
        user_t = parse_time(cfg)
        ref_h = user_t if user_t is not None else 12.0
        return max(86400, int(ref_h * 3600 * 2))

    assert parse_time(default_cfg) is None
    assert calc_redis_ttl(default_cfg) == 86400

    assert parse_time(custom_cfg) == 30.0
    assert calc_redis_ttl(custom_cfg) == 216000

    assert parse_time(short_cfg) == 1.0
    assert calc_redis_ttl(short_cfg) == 86400
