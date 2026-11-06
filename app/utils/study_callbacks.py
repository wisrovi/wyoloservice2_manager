"""Study lifecycle callbacks and progress tracking for Optuna optimizations."""

import json
import time
from typing import Any, Dict, Optional
import optuna
from optuna.trial import FrozenTrial

from .config_resolver import resolve_redis_ttl_seconds


class StudyCancelCallback:
    """Callback monitoring Redis cancellation flag between Optuna trials."""

    def __init__(self, broker_url: str, study_id: Optional[str]) -> None:
        """Initialize callback with Redis broker connection and study ID.

        Args:
            broker_url (str): Celery broker Redis URL.
            study_id (Optional[str]): Unique study task identifier.
        """
        self.broker_url = broker_url
        self.study_id = study_id

    def __call__(self, optuna_study: optuna.Study, trial: FrozenTrial) -> None:
        """Inspect Redis cancel key and halt study optimization if signaled.

        Args:
            optuna_study (optuna.Study): Active Optuna study object.
            trial (FrozenTrial): Completed trial metadata.
        """
        try:
            import redis

            r_client = redis.from_url(self.broker_url)
            if self.study_id and r_client.get(f"study:{self.study_id}:cancel"):
                optuna_study.stop()
        except Exception:
            pass


class StudyProgressRecorder:
    """Updates Redis with completed trial counts, ETA projections, and status."""

    def __init__(self, broker_url: str, full_config: Dict[str, Any]) -> None:
        """Initialize progress recorder with study metadata.

        Args:
            broker_url (str): Celery broker Redis URL.
            full_config (Dict[str, Any]): Full study configuration.
        """
        self.broker_url = broker_url
        self.full_config = full_config
        self.study_id = full_config.get("study_id")
        self.n_trials = int(full_config.get("sweeper", {}).get("n_trials", 10))

    def record_progress(self, trial_num: int) -> None:
        """Calculate ETA and write progress JSON to Redis.

        Args:
            trial_num (int): Zero-indexed completed trial index.
        """
        try:
            import redis

            r_client = redis.from_url(self.broker_url)
            completed = min(trial_num + 1, self.n_trials)

            start_time_bytes = r_client.get(f"study:{self.study_id}:start_time")
            if start_time_bytes:
                study_start = float(start_time_bytes)
                elapsed = time.time() - study_start
                avg_duration = elapsed / completed
                remaining = self.n_trials - completed
                eta = round(remaining * avg_duration, 1) if remaining > 0 else 0.0
            else:
                eta = 0.0

            progress_data = {
                "completed_trials": completed,
                "total_trials": self.n_trials,
                "eta": eta,
            }
            redis_ttl = resolve_redis_ttl_seconds(self.full_config)
            r_client.set(
                f"study:{self.study_id}:progress",
                json.dumps(progress_data),
                ex=redis_ttl,
            )
        except Exception:
            pass
