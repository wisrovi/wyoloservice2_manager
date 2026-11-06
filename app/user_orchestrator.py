"""Manager Orchestrator Module.

Coordinates Optuna studies, suggesting hyperparameters and dispatching training trials
to workers through Celery. Ensures sequential execution and supports dynamic search spaces.
"""

import os
import time
from typing import Any, Dict
from celery import current_task
import optuna
from optuna.storages import RDBStorage

from .celery_config import app as celery_app
from .utils.config_resolver import (
    BASE_DEFAULT_CONFIG,
    DEFAULT_REDIS_TTL_SECONDS,
    DEFAULT_REFERENCE_TIME_HOURS,
    TASK_FITNESS_MAP,
    deep_update,
    parse_user_train_time_hours,
    resolve_redis_ttl_seconds,
    resolve_study_configuration,
    resolve_style,
)
from .utils.queue_checker import check_queue_active, wait_for_result
from .utils.search_space_parser import parse_space
from .utils.study_callbacks import StudyCancelCallback, StudyProgressRecorder
from .utils.trial_objective import OptunaTrialObjective

VERSION: str = "v1.2.3"


def create_objective(full_config: Dict[str, Any]) -> OptunaTrialObjective:
    """Instantiate Optuna trial objective callable for study execution.

    Args:
        full_config (Dict[str, Any]): Complete study configuration.

    Returns:
        OptunaTrialObjective: Callable objective object for trial evaluations.
    """
    return OptunaTrialObjective(celery_app=celery_app, full_config=full_config)


def _init_optuna_storage() -> RDBStorage:
    """Connect to PostgreSQL or fall back to local SQLite Optuna storage.

    Returns:
        RDBStorage: Initialized relational database storage backend.
    """
    base_url = "postgresql://postgres:postgres@<IP>:23436/optuna_db"  # pragma: allowlist secret
    control_host = os.getenv("CONTROL_HOST", "192.168.10.252")
    storage_url = base_url.replace("<IP>", control_host)
    try:
        storage = RDBStorage(storage_url, skip_compatibility_check=True)
        optuna.create_study(
            storage=storage, study_name="test_connection", load_if_exists=True
        )
        return storage
    except Exception:
        storage_path = "sqlite:///src/optuna_study.db"
        return RDBStorage(storage_path, skip_compatibility_check=True)


@celery_app.task(name="tasks.manage_study")
def manage_study(full_config: Dict[str, Any]) -> Dict[str, Any]:
    """Orchestrate entire Optuna study dispatching trials to Celery worker queues.

    Args:
        full_config (Dict[str, Any]): Complete study configuration.

    Returns:
        Dict[str, Any]: Study results including best parameters and objective value.
    """
    try:
        full_config["study_id"] = current_task.request.id
    except Exception:
        full_config["study_id"] = "unknown"

    study_id = full_config.get("study_id", "unknown")
    resolve_study_configuration(full_config)

    try:
        import json
        import redis

        r_client = redis.from_url(celery_app.conf.broker_url)
        redis_ttl = resolve_redis_ttl_seconds(full_config)
        r_client.set(f"study:{study_id}:config", json.dumps(full_config), ex=redis_ttl)
        r_client.set(f"study:{study_id}:start_time", str(time.time()), ex=redis_ttl)
    except Exception:
        pass

    sweeper_cfg: Dict[str, Any] = full_config.get("sweeper", {})
    study_name: str = sweeper_cfg.get("study_name", "default_study")
    direction_val: str = sweeper_cfg.get("direction", "maximize")
    n_trials: int = int(sweeper_cfg.get("n_trials", 10))

    sampler_val = sweeper_cfg.get("sampler", "TPESampler")
    if sampler_val == "TPESampler":
        sampler = optuna.samplers.TPESampler()
    elif sampler_val == "RandomSampler":
        sampler = optuna.samplers.RandomSampler()
    elif sampler_val == "CmaEsSampler":
        sampler = optuna.samplers.CmaEsSampler()
    else:
        raise ValueError("Invalid sampler")

    direction = (
        optuna.study.StudyDirection.MAXIMIZE
        if direction_val == "maximize"
        else optuna.study.StudyDirection.MINIMIZE
    )
    storage = _init_optuna_storage()

    study: optuna.Study = optuna.create_study(
        study_name=study_name,
        direction=direction,
        storage=storage,
        sampler=sampler,
        load_if_exists=True,
    )

    cancel_callback = StudyCancelCallback(
        broker_url=celery_app.conf.broker_url, study_id=study_id
    )
    objective_func = OptunaTrialObjective(celery_app=celery_app, full_config=full_config)

    try:
        study.optimize(
            objective_func, n_trials=n_trials, callbacks=[cancel_callback]
        )
    except Exception as exc:
        return {"status": "failed", "error": str(exc), "study_name": study_name}

    return {
        "status": "completed",
        "study_name": study_name,
        "best_params": study.best_params,
        "best_value": study.best_value,
    }


__all__ = [
    "BASE_DEFAULT_CONFIG",
    "DEFAULT_REDIS_TTL_SECONDS",
    "DEFAULT_REFERENCE_TIME_HOURS",
    "TASK_FITNESS_MAP",
    "VERSION",
    "check_queue_active",
    "create_objective",
    "deep_update",
    "manage_study",
    "parse_space",
    "parse_user_train_time_hours",
    "resolve_redis_ttl_seconds",
    "resolve_study_configuration",
    "resolve_style",
    "wait_for_result",
]
