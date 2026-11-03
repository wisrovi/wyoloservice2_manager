# mypy: ignore-errors
# pylint: disable=all
# ruff: noqa
"""Unit tests for YAML smart defaults and vision style resolution in user_orchestrator.

This test module thoroughly verifies:
1. Vision task style resolution from explicit configuration keys ('style' or 'task').
2. Automatic style inference from model file naming patterns (e.g. -seg, -cls, -pose, -obb).
3. Fallback to 'detect' when model name does not indicate a specific sub-task.
4. Auto-mapping of Optuna fitness objective metrics according to vision task style.
5. Enrichment of minimal user YAML configurations with platform smart defaults:
   - algorithm defaulting to 'optuna'
   - direction defaulting to 'maximize'
   - sampler defaulting to 'TPESampler'
   - train batch defaulting to AutoBatch (-1)
   - hardware limits defaulting to 60% GPU allocation on device 0
6. Non-destructive behavior when user explicitly specifies custom values (overrides).
"""

import os
import sys
from unittest.mock import MagicMock

# Mock heavyweight infrastructure modules before importing orchestrator in lightweight test containers
for mod in [
    "optuna",
    "optuna.storages",
    "optuna.trial",
    "optuna.samplers",
    "optuna.pruners",
    "celery",
    "celery.result",
    "redis",
    "app.celery_config",
]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

# Add parent directory to sys.path to import user_orchestrator
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from app.user_orchestrator import (
    TASK_FITNESS_MAP,
    resolve_style,
    resolve_study_configuration,
)


def test_resolve_style_explicit_style_key():
    """Validates that explicit 'style' keys are respected and normalized.

    This test checks that passing style: 'segment' or style: 'classify'
    is preserved as lowercase string matching the supported task catalog.
    """
    assert resolve_style({"style": "segment"}) == "segment"
    assert resolve_style({"style": "CLASSIFY"}) == "classify"
    assert resolve_style({"style": "pose"}) == "pose"
    assert resolve_style({"style": "obb"}) == "obb"
    assert resolve_style({"style": "detect"}) == "detect"


def test_resolve_style_explicit_task_key():
    """Validates that explicit 'task' keys are respected when 'style' is omitted.

    This test checks interoperability with Ultralytics convention where the mode
    is defined under the 'task' parameter (e.g. task: 'segment').
    """
    assert resolve_style({"task": "segment"}) == "segment"
    assert resolve_style({"task": "classify"}) == "classify"
    assert resolve_style({"task": "detect"}) == "detect"


def test_resolve_style_inferred_from_model_name():
    """Validates that vision task style is correctly inferred from model weights filename.

    When neither 'style' nor 'task' is specified by the user, the orchestrator
    inspects the model name suffix:
    - -seg.pt -> 'segment'
    - -cls.pt -> 'classify'
    - -pose.pt -> 'pose'
    - -obb.pt -> 'obb'
    - standard .pt -> fallback to 'detect'
    """
    assert resolve_style({"model": "yolo11n-seg.pt"}) == "segment"
    assert resolve_style({"model": "yolov8m-cls.pt"}) == "classify"
    assert resolve_style({"model": "yolo11s-pose.pt"}) == "pose"
    assert resolve_style({"model": "yolo11n-obb.pt"}) == "obb"
    assert resolve_style({"model": "yolo11n.pt"}) == "detect"
    assert resolve_style({"model": "yolov8x.pt"}) == "detect"


def test_resolve_study_configuration_minimal_yaml():
    """Validates smart default resolution for a minimal 5-line user YAML.

    This test supplies only 'model', 'train.data', and 'train.epochs'.
    It verifies that:
    1. 'style' and 'task' are assigned as 'detect'.
    2. 'sweeper.fitness' is automatically set to 'metrics/mAP50-95(B)'.
    3. 'sweeper.direction' is automatically set to 'maximize'.
    4. 'sweeper.sampler' is automatically set to 'TPESampler'.
    5. 'sweeper.study_name' is dynamically generated with the task prefix.
    6. 'train.batch' is set to -1 (activating AutoBatch on the host GPU).
    7. 'extras.gpu' allocates default 60% memory limit on GPU 0.
    """
    minimal_config = {
        "model": "yolo11n.pt",
        "train": {
            "data": "/datasets/AREPO/protesis/data.yaml",
            "epochs": 5,
        },
    }

    resolved = resolve_study_configuration(minimal_config)

    assert resolved["style"] == "detect"
    assert resolved["task"] == "detect"
    assert resolved["type"] == "yolo"

    sweeper = resolved["sweeper"]
    assert sweeper["fitness"] == "metrics/mAP50-95(B)"
    assert sweeper["direction"] == "maximize"
    assert sweeper["sampler"] == "TPESampler"
    assert sweeper["algorithm"] == "optuna"
    assert sweeper["n_trials"] == 1
    assert "study_detect_" in sweeper["study_name"]

    assert resolved["train"]["batch"] == -1
    assert resolved["extras"]["gpu"]["id"] == 0
    assert resolved["extras"]["gpu"]["limit"] == 0.60


def test_resolve_study_configuration_segmentation_task():
    """Validates that style: 'segment' correctly resolves fitness to mask mAP.

    This test checks that when style is 'segment', the fitness metric
    auto-resolves to 'metrics/mAP50-95(M)' (mask metric) rather than box mAP.
    """
    config = {
        "model": "yolo11n-seg.pt",
        "style": "segment",
        "train": {
            "data": "/datasets/segmentation/data.yaml",
        },
    }

    resolved = resolve_study_configuration(config)
    assert resolved["style"] == "segment"
    assert resolved["sweeper"]["fitness"] == "metrics/mAP50-95(M)"


def test_resolve_study_configuration_classification_task():
    """Validates that style: 'classify' correctly resolves fitness to accuracy.

    This test checks that when style is 'classify', the fitness metric
    auto-resolves to 'metrics/accuracy_top1' rather than mAP.
    """
    config = {
        "model": "yolo11n-cls.pt",
        "train": {
            "data": "/datasets/classification/colorball/",
        },
    }

    resolved = resolve_study_configuration(config)
    assert resolved["style"] == "classify"
    assert resolved["sweeper"]["fitness"] == "metrics/accuracy_top1"


def test_resolve_study_configuration_preserves_explicit_user_overrides():
    """Validates that explicit user values override smart defaults without being overwritten.

    This test verifies that if the user explicitly specifies:
    - direction: 'minimize'
    - fitness: 'custom/loss'
    - batch: 32
    - sampler: 'RandomSampler'
    - extras.gpu.limit: 0.85
    these explicit user values are preserved and take precedence.
    """
    custom_config = {
        "model": "custom_yolo.pt",
        "style": "detect",
        "train": {
            "data": "/custom/path/data.yaml",
            "batch": 32,
        },
        "sweeper": {
            "fitness": "val/loss",
            "direction": "minimize",
            "sampler": "RandomSampler",
            "n_trials": 20,
            "study_name": "custom_optuna_run",
        },
        "extras": {
            "gpu": {
                "id": 1,
                "limit": 0.85,
            },
        },
    }

    resolved = resolve_study_configuration(custom_config)

    assert resolved["sweeper"]["fitness"] == "val/loss"
    assert resolved["sweeper"]["direction"] == "minimize"
    assert resolved["sweeper"]["sampler"] == "RandomSampler"
    assert resolved["sweeper"]["n_trials"] == 20
    assert resolved["sweeper"]["study_name"] == "custom_optuna_run"
    assert resolved["train"]["batch"] == 32
    assert resolved["extras"]["gpu"]["id"] == 1
    assert resolved["extras"]["gpu"]["limit"] == 0.85
