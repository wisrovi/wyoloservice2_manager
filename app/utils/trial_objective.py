"""Optuna trial objective class dispatching distributed worker training tasks."""

import copy
import time
from typing import Any, Dict
from optuna.trial import Trial

from .config_resolver import (
    BASE_DEFAULT_CONFIG,
    TASK_FITNESS_MAP,
    deep_update,
    parse_user_train_time_hours,
)
from .queue_checker import check_queue_active, wait_for_result
from .search_space_parser import parse_space
from .study_callbacks import StudyProgressRecorder


class OptunaTrialObjective:
    """Callable objective evaluated by Optuna for each trial configuration."""

    def __init__(self, celery_app: Any, full_config: Dict[str, Any]) -> None:
        """Initialize objective with Celery application and study configuration.

        Args:
            celery_app (Any): Configured Celery application instance.
            full_config (Dict[str, Any]): Full user and default study configuration.
        """
        self.celery_app = celery_app
        self.full_config = full_config

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
            self.worker_queue = str(target_queue)
        elif target_queue is True:
            self.worker_queue = "gpus_debug"
        else:
            self.worker_queue = f"gpus_{priority}"

        self.search_space: Dict[str, Any] = sweeper_in.get("search_space", {})
        self.progress_recorder = StudyProgressRecorder(
            broker_url=celery_app.conf.broker_url, full_config=full_config
        )

    def __call__(self, trial: Trial) -> float:
        """Evaluate hyperparameter configuration on distributed worker queue.

        Args:
            trial (Trial): Active Optuna trial instance.

        Returns:
            float: Evaluated fitness or accuracy metric.
        """
        trial_config: Dict[str, Any] = copy.deepcopy(BASE_DEFAULT_CONFIG)
        deep_update(trial_config, self.full_config)

        overrides: Dict[str, Any] = parse_space(trial, self.search_space)
        deep_update(trial_config, overrides)

        user_time_hours = parse_user_train_time_hours(trial_config)
        if user_time_hours is not None:
            trial_config.setdefault("train", {})["time"] = user_time_hours
        elif isinstance(trial_config.get("train"), dict):
            trial_config["train"].pop("time", None)

        if "user_id" not in trial_config:
            trial_config["user_id"] = trial_config.get("metadata", {}).get(
                "author", "wisrovi"
            )

        sweeper_in = self.full_config.get("sweeper", {})
        if not isinstance(sweeper_in, dict):
            sweeper_in = {}
        default_fit = TASK_FITNESS_MAP.get(
            trial_config.get("style", "detect"), "metrics/mAP50-95(B)"
        )
        trial_config["sweeper"] = {
            "study_name": sweeper_in.get("study_name", "optuna_study"),
            "fitness": sweeper_in.get("fitness", default_fit),
        }

        check_queue_active(self.celery_app, self.worker_queue)

        max_retries = 3
        retry_delay = 5
        attempt = 0

        while attempt < max_retries:
            attempt += 1
            job = self.celery_app.send_task(
                "tasks.train_on_gpu_simple",
                args=[trial_config],
                queue=self.worker_queue,
            )
            result = wait_for_result(job)

            if isinstance(result, dict):
                metric_key = None
                if "accuracy" in result and result["accuracy"] is not None:
                    metric_key = "accuracy"
                elif "fitness" in result and result["fitness"] is not None:
                    metric_key = "fitness"

                if metric_key is not None:
                    try:
                        acc = float(result[metric_key])
                        if acc >= 0:
                            self.progress_recorder.record_progress(trial.number)
                            return acc
                    except (ValueError, TypeError):
                        pass

            if attempt < max_retries:
                time.sleep(retry_delay)

        self.progress_recorder.record_progress(trial.number)
        return 0.0
