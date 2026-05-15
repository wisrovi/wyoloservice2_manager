"""Manager Orchestrator Module.

This module coordinates Optuna studies, suggesting hyperparameters and
dispatching training trials to workers through Celery. It ensures sequential
execution and supports dynamic search spaces.
"""

import os
import time
from typing import Any, Callable, Optional
import copy
import optuna
from optuna.trial import Trial
from optuna.storages import RDBStorage
from celery.result import AsyncResult

# Import the Celery app configuration
from .celery_config import app


def check_queue_active(app, queue_name: str) -> bool:
    """Checks if there is at least one active worker listening to the specified queue.

    Args:
        app: The Celery app instance.
        queue_name (str): Name of the queue to check.

    Returns:
        bool: True if the queue is active, False otherwise.
    """
    try:
        inspector = app.control.inspect()
        # This can be slow as it queries all workers via broadcast
        queues_data = inspector.active_queues()
        if not queues_data:
            return False

        for worker_queues in queues_data.values():
            for q in worker_queues:
                if q.get("name") == queue_name:
                    return True
        return False
    except Exception as e:
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
        else:
            # result attribute on AsyncResult contains the exception in case of FAILURE
            print(f"Task {job.id} failed with state: {job.state}. Error: {job.result}")
            return None
    except Exception as e:
        print(f"Error waiting for task {job.id}: {str(e)}")
        return None


def create_objective(full_config: dict[str, Any]) -> Callable[[Trial], float]:
    """Creates a closure for the Optuna objective function.

    Args:
        full_config (dict[str, Any]): The full YAML configuration for the study.

    Returns:
        Callable[[Trial], float]: The objective function for Optuna optimize.
    """
    sweeper_cfg: dict[str, Any] = full_config.get("sweeper", {})

    # 1. Determine priority (low, medium, high)
    priority = sweeper_cfg.get("priority", "low")

    # 2. Check for debug mode (defines a private or specific queue)
    debug_val = sweeper_cfg.get("debug", False)

    if debug_val:
        # If debug is a string, use it as the queue name, else use 'gpus_debug'
        worker_queue = debug_val if isinstance(debug_val, str) else "gpus_debug"
    else:
        # Construct queue name based on priority: gpus_low, gpus_medium, gpus_high
        worker_queue = f"gpus_{priority}"

    search_space: dict[str, Any] = sweeper_cfg.get("search_space", {})

    def objective(trial: Trial) -> float:
        """The actual objective function called by Optuna.

        Args:
            trial (Trial): The Optuna trial object.

        Returns:
            float: The accuracy (or metric) achieved in the trial.
        """

        def parse_space(space: dict[str, Any], prefix: str = "") -> dict[str, Any]:
            """Recursively parses the search space into Optuna suggestions.

            Args:
                space (dict[str, Any]): The search space definition.
                prefix (str, optional): Prefix for nested keys. Defaults to "".

            Returns:
                dict[str, Any]: The suggested hyperparameters for this trial.
            """
            params: dict[str, Any] = {}
            for key, value in space.items():
                if isinstance(value, dict):
                    params[key] = parse_space(value, f"{prefix}{key}_")
                elif isinstance(value, list) and len(value) >= 2:
                    dist_type: str = value[0]
                    args: list[Any] = value[1:]
                    # Ensure numeric arguments are properly typed
                    processed_args: list[Any] = []
                    for arg in args:
                        if isinstance(arg, str):
                            try:
                                processed_args.append(float(arg))
                            except ValueError:
                                processed_args.append(arg)
                        else:
                            processed_args.append(arg)

                    if dist_type == "choice":
                        params[key] = trial.suggest_categorical(f"{prefix}{key}", args)
                    elif dist_type == "uniform":
                        params[key] = trial.suggest_float(
                            f"{prefix}{key}", processed_args[0], processed_args[1]
                        )
                    elif dist_type == "loguniform":
                        params[key] = trial.suggest_float(
                            f"{prefix}{key}",
                            processed_args[0],
                            processed_args[1],
                            log=True,
                        )
                    elif dist_type == "range":
                        step: int = (
                            int(processed_args[2]) if len(processed_args) > 2 else 1
                        )
                        params[key] = trial.suggest_int(
                            f"{prefix}{key}",
                            int(processed_args[0]),
                            int(processed_args[1]),
                            step=step,
                        )
                    else:
                        params[key] = args[0]
                else:
                    params[key] = value
            return params

        # Generate overrides from the search space
        overrides: dict[str, Any] = parse_space(search_space)
        print(f"Trial {trial.number}: Suggested overrides: {overrides}")

        def deep_update(base: dict, update: dict):
            for k, v in update.items():
                if isinstance(v, dict) and k in base and isinstance(base[k], dict):
                    deep_update(base[k], v)
                else:
                    base[k] = v

        # Create a clean copy for this trial
        import copy
        import yaml as yaml_log

        trial_config = copy.deepcopy(full_config)
        deep_update(trial_config, overrides)

        # 1. Add user_id (root field)
        metadata = trial_config.get("metadata", {})
        if "user_id" not in trial_config:
            trial_config["user_id"] = metadata.get("author", "Optuna Manager")

        # 2. Ensure 'type' is present (mandatory field)
        if "type" not in trial_config:
            trial_config["type"] = "yolo"

        # 3. Simplify 'sweeper' section (only study_name and fitness)
        if "sweeper" in trial_config:
            original_sweeper = trial_config["sweeper"]
            trial_config["sweeper"] = {
                "study_name": original_sweeper.get("study_name", "optuna_study"),
                "fitness": original_sweeper.get("fitness", "metrics/accuracy_top1"),
            }

        # Log the exact payload for debugging
        print(f"\n--- [TRIAL {trial.number} PAYLOAD START] ---")
        print(yaml_log.dump(trial_config, default_flow_style=False))
        print(f"--- [TRIAL {trial.number} PAYLOAD END] ---\n")

        # Validate that the queue exists and has active workers before sending
        if not check_queue_active(app, worker_queue):
            print(
                f"WARNING: No active workers detected for queue '{worker_queue}'. Sending anyway, but task might stay pending."
            )

        # Log target queue and task dispatch
        print(f"Trial {trial.number}: Sending task to queue '{worker_queue}'")

        # Dispatch the trial task to the worker
        job: AsyncResult = app.send_task(
            "tasks.train_on_gpu_simple", args=[trial_config], queue=worker_queue
        )

        # Wait for completion and extract the metric
        result: Any = wait_for_result(job)
        if isinstance(result, dict) and "accuracy" in result:
            return float(result["accuracy"])

        print(
            f"Warning: Trial {trial.number} did not return accuracy. Result: {result}"
        )
        return 0.0

    return objective


@app.task(name="tasks.manage_study")
def manage_study(full_config: dict[str, Any]) -> dict[str, Any]:
    """Orchestrates an entire Optuna study.

    Args:
        full_config (dict[str, Any]): The complete study configuration.

    Returns:
        dict[str, Any]: The study results including the best parameters found.
    """
    sweeper_cfg: dict[str, Any] = full_config.get("sweeper", {})
    study_name: str = sweeper_cfg.get("study_name", "default_study")
    DIRECTION: str = sweeper_cfg.get("direction", "maximize")
    n_trials: int = int(sweeper_cfg.get("n_trials", 10))

    SAMPLER = sweeper_cfg.get("sampler", "TPESampler")

    if SAMPLER == "TPESampler":
        sampler = optuna.samplers.TPESampler()
    elif SAMPLER == "RandomSampler":
        sampler = optuna.samplers.RandomSampler()
    elif SAMPLER == "CmaEsSampler":
        sampler = optuna.samplers.CmaEsSampler()
    else:
        raise ValueError("Invalid sampler")

    if DIRECTION == "maximize":
        direction = optuna.study.StudyDirection.MAXIMIZE
    elif DIRECTION == "minimize":
        direction = optuna.study.StudyDirection.MINIMIZE
    else:
        raise ValueError("Invalid direction")

    # PostgreSQL configuration for Optuna storage
    base_url = "postgresql://postgres:postgres@<IP>:23436/wyoloservice"
    control_host = os.getenv("CONTROL_HOST", "192.168.10.252")
    storage_url = base_url.replace("<IP>", control_host)

    # Use RDBStorage directly with skip_compatibility_check=True to avoid the version mismatch error
    from optuna.storages import RDBStorage

    storage = RDBStorage(storage_url, skip_compatibility_check=True)

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
    except Exception as e:
        print(f"[-] Critical error during Optuna optimization: {e}")
        return {
            "status": "failed",
            "error": str(e),
            "study_name": study_name
        }

    return {
        "status": "completed",
        "study_name": study_name,
        "best_params": study.best_params,
        "best_value": study.best_value,
    }
