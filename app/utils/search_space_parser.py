"""Search space recursive parser suggesting hyperparameter values with Optuna."""

from typing import Any, Dict
from optuna.trial import Trial


def parse_space(trial: Trial, space: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
    """Recursively parse search space mapping and draw trial suggestions.

    Args:
        trial (Trial): Active Optuna trial instance.
        space (Dict[str, Any]): Search space definition structure.
        prefix (str): Namespace prefix for nested parameter names.

    Returns:
        Dict[str, Any]: Suggested parameter values dictionary.
    """
    suggestions: Dict[str, Any] = {}
    for key, value in space.items():
        name = f"{prefix}{key}"
        if isinstance(value, dict):
            suggestions[key] = parse_space(trial, value, f"{name}.")
        elif isinstance(value, (list, tuple)) and len(value) >= 2:
            dist_type = value[0]
            args = value[1:]
            try:
                if dist_type == "choice":
                    choices = args[0] if isinstance(args[0], list) else list(args)
                    try:
                        suggestions[key] = trial.suggest_categorical(name, choices)
                    except Exception:
                        suggestions[key] = choices[0]
                elif dist_type == "uniform":
                    try:
                        suggestions[key] = trial.suggest_float(name, float(args[0]), float(args[1]))
                    except Exception:
                        suggestions[key] = float(args[0])
                elif dist_type == "loguniform":
                    try:
                        suggestions[key] = trial.suggest_float(name, float(args[0]), float(args[1]), log=True)
                    except Exception:
                        suggestions[key] = float(args[0])
                elif dist_type == "int":
                    try:
                        suggestions[key] = trial.suggest_int(name, int(args[0]), int(args[1]))
                    except Exception:
                        suggestions[key] = int(args[0])
                else:
                    suggestions[key] = value
            except Exception:
                suggestions[key] = value
        else:
            suggestions[key] = value
    return suggestions
