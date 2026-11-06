"""Study configuration enrichment, style inference, and parameter normalization."""

import copy
import time
from typing import Any, Dict, Optional

DEFAULT_REFERENCE_TIME_HOURS: float = 12.0
DEFAULT_REDIS_TTL_SECONDS: int = 86400

TASK_FITNESS_MAP: Dict[str, str] = {
    "detect": "metrics/mAP50-95(B)",
    "segment": "metrics/mAP50-95(M)",
    "classify": "metrics/accuracy_top1",
    "pose": "metrics/mAP50-95(P)",
    "obb": "metrics/mAP50-95(B)",
}

BASE_DEFAULT_CONFIG: Dict[str, Any] = {
    "model": "yolov8n.pt",
    "type": "yolo",
    "style": "detect",
    "task": "detect",
    "train": {
        "batch": -1,
        "data": "/datasets/classification/colorball.v8i.multiclass/",
        "epochs": 2,
        "imgsz": 640,
    },
    "sweeper": {
        "study_name": "exp_detection_headless",
        "algorithm": "optuna",
        "direction": "maximize",
        "sampler": "TPESampler",
        "fitness": "metrics/mAP50-95(B)",
        "tune": False,
        "priority": "medium",
    },
    "extras": {
        "gpu": {
            "id": 0,
            "limit": 0.60,
        },
    },
    "metadata": {
        "author": "William Rodríguez - wisrovi",
        "content": "Experiment launched from orchestrator (fallback)",
    },
}


def resolve_style(config: Dict[str, Any]) -> str:
    """Resolve vision task style ('detect', 'segment', 'classify', 'pose', 'obb').

    Args:
        config (Dict[str, Any]): Dictionary containing model, style, or task parameters.

    Returns:
        str: Resolved vision style identifier string.
    """
    explicit = config.get("style") or config.get("task")
    if explicit and isinstance(explicit, str):
        cleaned = explicit.strip().lower()
        if cleaned in TASK_FITNESS_MAP:
            return cleaned

    model_str = str(config.get("model", "")).lower()
    if "-seg" in model_str or "segment" in model_str:
        return "segment"
    if "-cls" in model_str or "classify" in model_str or "classification" in model_str:
        return "classify"
    if "-pose" in model_str:
        return "pose"
    if "-obb" in model_str:
        return "obb"
    return "detect"


def resolve_study_configuration(full_config: Dict[str, Any]) -> Dict[str, Any]:
    """Enrich and normalize user training configuration with sensible smart defaults.

    Args:
        full_config (Dict[str, Any]): Configuration dictionary to mutate and enrich.

    Returns:
        Dict[str, Any]: Fully normalized study configuration dictionary.
    """
    style = resolve_style(full_config)
    full_config["style"] = style
    full_config["task"] = style

    if "type" not in full_config:
        full_config["type"] = "yolo"

    sweeper_cfg = full_config.setdefault("sweeper", {})
    if not isinstance(sweeper_cfg, dict):
        sweeper_cfg = {}
        full_config["sweeper"] = sweeper_cfg

    if not sweeper_cfg.get("fitness"):
        sweeper_cfg["fitness"] = TASK_FITNESS_MAP.get(style, "metrics/mAP50-95(B)")

    if not sweeper_cfg.get("study_name"):
        sweeper_cfg["study_name"] = f"study_{style}_{int(time.time())}"

    if not sweeper_cfg.get("direction"):
        sweeper_cfg["direction"] = "maximize"
    if not sweeper_cfg.get("sampler"):
        sweeper_cfg["sampler"] = "TPESampler"
    if not sweeper_cfg.get("algorithm"):
        sweeper_cfg["algorithm"] = "optuna"

    search_space = sweeper_cfg.get("search_space", {})
    is_tuning = bool(sweeper_cfg.get("tune", False)) or (
        isinstance(search_space, dict) and bool(search_space)
    )
    if "n_trials" not in sweeper_cfg:
        sweeper_cfg["n_trials"] = 10 if is_tuning else 1

    extras = full_config.setdefault("extras", {})
    if isinstance(extras, dict):
        gpu_extras = extras.setdefault("gpu", {})
        if isinstance(gpu_extras, dict):
            gpu_extras.setdefault("id", 0)
            gpu_extras.setdefault("limit", 0.60)

    train_cfg = full_config.setdefault("train", {})
    if isinstance(train_cfg, dict) and "batch" not in train_cfg:
        train_cfg["batch"] = -1

    return full_config


def parse_user_train_time_hours(config: Optional[Dict[str, Any]]) -> Optional[float]:
    """Extract valid user-defined training time limit in hours from configuration.

    Args:
        config (Optional[Dict[str, Any]]): Configuration dictionary holding train block.

    Returns:
        Optional[float]: Extracted training time in hours, or None if omitted or <= 0.
    """
    if not isinstance(config, dict):
        return None
    train_section = config.get("train")
    if not isinstance(train_section, dict):
        return None
    raw_time = train_section.get("time")
    if raw_time is None or isinstance(raw_time, bool):
        return None
    try:
        parsed = float(raw_time)
        return parsed if parsed > 0.0 else None
    except (ValueError, TypeError):
        return None


def resolve_redis_ttl_seconds(config: Optional[Dict[str, Any]]) -> int:
    """Calculate the Redis key time-to-live in seconds (2x reference hours, min 24h).

    Args:
        config (Optional[Dict[str, Any]]): Configuration dictionary.

    Returns:
        int: Total TTL duration in seconds.
    """
    user_time = parse_user_train_time_hours(config)
    ref_hours = user_time if user_time is not None else DEFAULT_REFERENCE_TIME_HOURS
    return max(DEFAULT_REDIS_TTL_SECONDS, int(ref_hours * 3600 * 2))


def deep_update(base: Dict[str, Any], update: Dict[str, Any]) -> None:
    """Recursively update nested dictionaries in-place.

    Args:
        base (Dict[str, Any]): Target base dictionary.
        update (Dict[str, Any]): New key-values to merge into base.
    """
    for k, v in update.items():
        if isinstance(v, dict) and k in base and isinstance(base[k], dict):
            deep_update(base[k], v)
        else:
            base[k] = v
