"""WYOLO Service 2 Manager CLI and service entrypoint."""

import argparse
import sys
from typing import Any, Dict
import yaml

from pipelines import manager_study_pipeline
from user_orchestrator import VERSION, manage_study


def parse_arguments() -> argparse.Namespace:
    """Parse CLI input arguments for manager execution.

    Returns:
        argparse.Namespace: Parsed command-line arguments container.
    """
    parser = argparse.ArgumentParser(description="WYOLO Service 2 Manager")
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="Path to study YAML configuration file to launch locally",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"wyoloservice2_manager {VERSION}",
    )
    return parser.parse_args()


def run_local_study(config_file: str) -> Dict[str, Any]:
    """Execute study directly using manager study pipeline.

    Args:
        config_file (str): Filesystem path to study configuration YAML.

    Returns:
        Dict[str, Any]: Result mapping containing study output.
    """
    with open(config_file, "r", encoding="utf-8") as f:
        study_config = yaml.safe_load(f) or {}

    results = manager_study_pipeline.run(study_config)
    return results


def main() -> None:
    """Entrypoint function handling argument dispatch."""
    args = parse_arguments()
    if args.file:
        res = run_local_study(args.file)
        print(f"Study Completed: {res}")
    else:
        print(f"WYOLO Service 2 Manager ({VERSION}) Ready.")


if __name__ == "__main__":
    main()
