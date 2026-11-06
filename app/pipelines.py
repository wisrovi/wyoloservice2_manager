"""Declarative WPipe pipeline assembly for manager study orchestrations."""

from wpipe import Pipeline
from states.manage_study_step import manage_study_step


def build_manager_study_pipeline(
    tracking_db: str = "/tmp/manager_study.db",
) -> Pipeline:
    """Instantiate and configure manager study orchestration pipeline.

    Args:
        tracking_db (str): Path to SQLite tracking database file.

    Returns:
        Pipeline: Fully configured WPipe pipeline instance.
    """
    pipe = Pipeline(
        pipeline_name="manager_study_pipe",
        verbose=False,
        tracking_db=tracking_db,
    )
    pipe.set_steps([manage_study_step])
    return pipe


# Declarative pipeline singleton for WPipe architecture compliance and visualizer discovery
manager_study_pipeline: Pipeline = build_manager_study_pipeline()

__all__ = ["build_manager_study_pipeline", "manager_study_pipeline"]
