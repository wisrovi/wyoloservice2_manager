"""Data Transfer Objects (DTO) for study orchestration and trial execution."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class StudySweeperDTO(BaseModel):
    """Configuration mapping for Optuna sweeper and hyperparameter search.

    Attributes:
        study_name: Unique study identifier.
        direction: Optimization direction ('maximize' or 'minimize').
        n_trials: Total number of trials to run.
        fitness: Objective fitness metric key.
        priority: Worker execution priority ('low', 'medium', 'high').
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)
    study_name: str = Field(default="optuna_study", description="Unique study identifier")
    direction: str = Field(default="maximize", description="Optimization direction")
    n_trials: int = Field(default=10, description="Total number of trials to run")
    fitness: str = Field(default="metrics/mAP50-95(B)", description="Target metric for optimization")
    priority: str = Field(default="medium", description="Worker execution priority")
    search_space: Dict[str, Any] = Field(default_factory=dict, description="Search space definition")


class StudyConfigDTO(BaseModel):
    """Full study configuration container defining model, train, and sweeper parameters.

    Attributes:
        model: Model architecture or initial weights file.
        type: Framework type (e.g. 'yolo').
        style: Computer vision task style ('detect', 'segment', 'classify', etc.).
        study_id: Unique task identifier.
        train: Dictionary of training parameters.
        sweeper: Hyperparameter sweeper configuration.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)
    model: str = Field(default="yolov8n.pt", description="Base model weights")
    type: str = Field(default="yolo", description="Model framework type")
    style: str = Field(default="detect", description="Vision task domain")
    task: Optional[str] = Field(default=None, description="Task alias")
    study_id: Optional[str] = Field(default=None, description="Study task ID")
    train: Dict[str, Any] = Field(default_factory=dict, description="Training parameters")
    sweeper: StudySweeperDTO = Field(default_factory=StudySweeperDTO, description="Sweeper configuration")
    extras: Dict[str, Any] = Field(default_factory=dict, description="Hardware extras")


class StudyResultDTO(BaseModel):
    """Final outcome container summarizing Optuna optimization results.

    Attributes:
        status: Execution status ('completed', 'failed').
        study_name: Target study name.
        best_params: Dictionary of best parameter combination discovered.
        best_value: Highest (or lowest) objective value achieved.
        error: Optional error diagnostic string.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)
    status: str = Field(..., description="Final execution status")
    study_name: str = Field(..., description="Name of the study")
    best_params: Dict[str, Any] = Field(default_factory=dict, description="Optimal parameters")
    best_value: Optional[float] = Field(default=None, description="Best fitness score achieved")
    error: Optional[str] = Field(default=None, description="Error diagnostics if failed")
