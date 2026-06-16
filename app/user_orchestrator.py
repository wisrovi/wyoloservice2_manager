"""Manager Orchestrator Module.

This module coordinates Optuna studies, suggesting hyperparameters and
dispatching training trials to workers through Celery. It ensures sequential
execution and supports dynamic search spaces.
"""

import copy
import os
import time
from collections.abc import Callable  # pylint: disable=import-error
from typing import Any, Optional

import optuna  # pylint: disable=import-error
from celery.result import AsyncResult  # pylint: disable=import-error
from optuna.storages import RDBStorage  # pylint: disable=import-error
from optuna.trial import Trial  # pylint: disable=import-error

# Import the Celery app configuration
from .celery_config import app as celery_app


def check_queue_active(app_instance: Any, queue_name: str) -> bool:
    """Checks if there is at least one active worker listening to the specified queue.

    Args:
        app_instance: The Celery app instance.
        queue_name (str): Name of the queue to check.

    Returns:
        bool: True if the queue is active, False otherwise.
    """
    try:
        inspector = app_instance.control.inspect()
        # This can be slow as it queries all workers via broadcast
        queues_data = inspector.active_queues()
        if not queues_data:
            return False

        for worker_queues in queues_data.values():
            for q in worker_queues:
                if q.get("name") == queue_name:
                    return True
        return False
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"Warning: Could not inspect queues: {e}")
        # If we can't inspect, we assume it might exist to avoid blocking
        return True


def wait_for_result(job: AsyncResult) -> Any:
    """Blocks until the Celery task is ready and returns the result safely.

    Avoids using job.get() to bypass Celery's safety check for synchronous subtasks.

    Args:
        job (AsyncResult): The Celery task to wait for.

    Returns:
        Any: The result of the Celery task or None if it failed.
    """
    try:
        # Manually poll for completion to avoid "Never call result.get() within a task"
        while not job.ready():
            time.sleep(1)

        if job.successful():
            return job.result
        # result attribute on AsyncResult contains the exception in case of FAILURE
        print(f"Task {job.id} failed with state: {job.state}. Error: {job.result}")
        return None
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"Error waiting for task {job.id}: {str(e)}")
        return None


# --- Global Defaults ---
BASE_DEFAULT_CONFIG = {
    "model": "yolov8n.pt",
    "type": "yolo",
    "train": {
        "batch": -1,
        "data": "/datasets/classification/colorball.v8i.multiclass/",
        "epochs": 2,
        "imgsz": 640,
    },
    "sweeper": {
        "study_name": "exp_deteccion_headless",
        "fitness": "metrics/mAP50-95(B)",
    },
    "metadata": {
        "author": "William Rodríguez - wisrovi",
        "content": "Experimento lanzado desde orquestador (fallback)",
    },
}


def deep_update(base: dict, update: dict) -> None:
    """Recursively updates a dictionary."""
    for k, v in update.items():
        if isinstance(v, dict) and k in base and isinstance(base[k], dict):
            deep_update(base[k], v)
        else:
            base[k] = v


def parse_space(trial: Trial, space: dict, prefix: str = "") -> dict:  # noqa: PLR0912  # pylint: disable=too-many-branches
    """Recursively parses the search space and suggests values using Optuna.

    Args:
        trial (Trial): The Optuna trial object.
        space (dict): The search space configuration.
        prefix (str): Prefix for the parameter names.

    Returns:
        dict: A dictionary of suggested values.
    """
    suggestions: dict[str, Any] = {}
    for key, value in space.items():
        name = f"{prefix}{key}"
        if isinstance(value, dict):
            suggestions[key] = parse_space(trial, value, f"{name}.")
        elif isinstance(value, (list, tuple)) and len(value) >= 2:
            dist_type = value[0]
            args = value[1:]
            try:
                if dist_type == "choice":
                    # Handle both ["choice", ["a", "b"]] and ["choice", "a", "b"]
                    choices = args[0] if isinstance(args[0], list) else list(args)
                    try:
                        suggestions[key] = trial.suggest_categorical(name, choices)
                    except Exception as e:  # pylint: disable=broad-exception-caught
                        print(f"Warning: Optuna categorical error for {name}: {e}. Using first choice as fallback.")
                        suggestions[key] = choices[0]
                elif dist_type == "uniform":
                    try:
                        suggestions[key] = trial.suggest_float(name, float(args[0]), float(args[1]))
                    except Exception as e:  # pylint: disable=broad-exception-caught
                        print(f"Warning: Optuna float error for {name}: {e}. Using lower bound as fallback.")
                        suggestions[key] = float(args[0])
                elif dist_type == "loguniform":
                    try:
                        suggestions[key] = trial.suggest_float(name, float(args[0]), float(args[1]), log=True)
                    except Exception as e:  # pylint: disable=broad-exception-caught
                        print(f"Warning: Optuna loguniform error for {name}: {e}. Using lower bound as fallback.")
                        suggestions[key] = float(args[0])
                elif dist_type == "int":
                    try:
                        suggestions[key] = trial.suggest_int(name, int(args[0]), int(args[1]))
                    except Exception as e:  # pylint: disable=broad-exception-caught
                        print(f"Warning: Optuna int error for {name}: {e}. Using lower bound as fallback.")
                        suggestions[key] = int(args[0])
                else:
                    # Unknown distribution type, just pass it through
                    suggestions[key] = value
            except Exception as e:  # pylint: disable=broad-exception-caught
                print(f"Critical error in parse_space for {name}: {e}. Using original value.")
                suggestions[key] = value
        else:
            # If it's a static value, just pass it through
            suggestions[key] = value
    return suggestions


def create_objective(full_config: dict[str, Any]) -> Callable[[Trial], float]:
    """Creates a closure for the Optuna objective function.

    Args:
        full_config (dict[str, Any]): The full YAML configuration for the study.
    """
    # Pre-calculate worker queue based on input config (independent of Optuna trials)
    sweeper_in = full_config.get("sweeper", {})
    priority = sweeper_in.get("priority", "low")
    debug_val = sweeper_in.get("debug", False)

    worker_queue = (debug_val if isinstance(debug_val, str) else "gpus_debug") if debug_val else f"gpus_{priority}"

    search_space: dict[str, Any] = sweeper_in.get("search_space", {})

    def objective(trial: Trial) -> float:
        import yaml as yaml_log  # type: ignore # pylint: disable=import-error,import-outside-toplevel

        # 1. Start with the HARDCODED defaults as ultimate safety net
        trial_config: dict[str, Any] = copy.deepcopy(BASE_DEFAULT_CONFIG)

        # 2. Merge with the USER'S full configuration (overwrites defaults)
        deep_update(trial_config, full_config)

        # 3. Generate and apply Optuna suggestions
        overrides: dict[str, Any] = parse_space(trial, search_space)
        print(f"Trial {trial.number}: Suggested overrides from Optuna: {overrides}")
        deep_update(trial_config, overrides)

        # 4. Final Cleanup & Mandatory Fields (The "Contract" with Invoker)
        # Ensure user_id exists
        if "user_id" not in trial_config:
            trial_config["user_id"] = trial_config.get("metadata", {}).get("author", "wisrovi")

        # Simplify sweeper for the Invoker (Invoker only needs these 2)
        trial_config["sweeper"] = {
            "study_name": sweeper_in.get("study_name", "optuna_study"),
            "fitness": sweeper_in.get("fitness", "metrics/accuracy_top1"),
        }

        # Log the exact payload for debugging
        print(f"\n--- [TRIAL {trial.number} PAYLOAD TO INVOKER] ---")
        print(yaml_log.dump(trial_config, default_flow_style=False))
        print(f"--- [TRIAL {trial.number} TARGET QUEUE: {worker_queue}] ---")
        print(f"--- [TRIAL {trial.number} PAYLOAD END] ---\n")

        # Validate queue before sending
        if not check_queue_active(celery_app, worker_queue):
            print(f"WARNING: No active workers for '{worker_queue}'. Task might hang.")

        # Dispatch the trial task to the worker with retries
        max_retries = 3
        retry_delay = 5
        attempt = 0
        result = None

        while attempt < max_retries:
            attempt += 1
            print(f"Trial {trial.number}: Dispatching task to queue '{worker_queue}' (Attempt {attempt}/{max_retries})")

            # Dispatch the trial task to the worker
            job: AsyncResult = celery_app.send_task(
                "tasks.train_on_gpu_simple", args=[trial_config], queue=worker_queue
            )

            # Wait for completion and extract the metric
            result = wait_for_result(job)

            # Check if result is valid and accuracy is non-negative
            if isinstance(result, dict) and "accuracy" in result:
                acc = float(result["accuracy"])
                if acc >= 0:
                    return acc
                print(f"Warning: Trial {trial.number} returned negative accuracy ({acc}). Possible training error.")

            print(f"[-] Trial {trial.number} attempt {attempt} failed or returned invalid result. Result: {result}")

            if attempt < max_retries:
                print(f"[*] Waiting {retry_delay}s before retrying...")
                time.sleep(retry_delay)

        print(f"[-] Critical: Trial {trial.number} failed after {max_retries} attempts.")
        # If we reach here, all retries failed. Mark as 0.0 or raise error to let Optuna handle it.
        return 0.0

    return objective


@celery_app.task(name="tasks.manage_study")
def manage_study(full_config: dict[str, Any]) -> dict[str, Any]:
    """Orchestrates an entire Optuna study.

    Args:
        full_config (dict[str, Any]): The complete study configuration.

    Returns:
        dict[str, Any]: The study results including the best parameters found.
    """
    sweeper_cfg: dict[str, Any] = full_config.get("sweeper", {})
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

    if direction_val == "maximize":
        direction = optuna.study.StudyDirection.MAXIMIZE
    elif direction_val == "minimize":
        direction = optuna.study.StudyDirection.MINIMIZE
    else:
        raise ValueError("Invalid direction")

    # PostgreSQL configuration for Optuna storage
    base_url = "postgresql://postgres:postgres@<IP>:23436/optuna_db"  # pragma: allowlist secret
    control_host = os.getenv("CONTROL_HOST", "192.168.10.252")
    storage_url = base_url.replace("<IP>", control_host)

    # Use RDBStorage directly with skip_compatibility_check=True to avoid the version mismatch error

    try:
        print(f"[*] Attempting to connect to Optuna storage: {storage_url}")
        storage = RDBStorage(storage_url, skip_compatibility_check=True)
        # Try to create a dummy study to test connection
        optuna.create_study(storage=storage, study_name="test_connection", load_if_exists=True)
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"Warning: Could not connect to PostgreSQL storage: {e}")
        storage_path = "sqlite:///src/optuna_study.db"
        print(f"[*] Falling back to local SQLite storage: {storage_path}")
        storage = RDBStorage(storage_path, skip_compatibility_check=True)

    study: optuna.Study = optuna.create_study(
        study_name=study_name,
        direction=direction,
        storage=storage,
        sampler=sampler,
        load_if_exists=True,
    )

    # Run the optimization loop
    try:
        study.optimize(create_objective(full_config), n_trials=n_trials)
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"[-] Critical error during Optuna optimization: {e}")
        return {"status": "failed", "error": str(e), "study_name": study_name}

    return {
        "status": "completed",
        "study_name": study_name,
        "best_params": study.best_params,
        "best_value": study.best_value,
    }
