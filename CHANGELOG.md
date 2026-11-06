# Changelog - Orchestrator Manager

## [2.2.0] - 2026-11-06
### Added
- **WPipe Architecture & Quality Compliance:** Fully migrated manager service to standard WPipe microservice architecture:
  - Created declarative `app/pipelines.py` with `manager_study_pipeline` and `manage_study_step`.
  - Created typed Data Transfer Objects under `app/dto/` (`study_dto.py`).
  - Created standard service entrypoint `app/main.py`.
  - Modularized `user_orchestrator.py` into dedicated Single Responsibility Principle modules under `app/utils/` (`config_resolver.py`, `search_space_parser.py`, `queue_checker.py`, `study_callbacks.py`, `trial_objective.py`).
  - Extracted nested function closures (`objective`, `record_progress`, `check_cancel_callback`) into clean callable classes.
  - Strictly pinned external dependencies in `requirements.txt` (Rule 15).
  - Co-located unit test suite in `app/tests/` (Rule 16) and verified 100% dockerized test pass rate.

## [2.1.0] - 2026-11-03
### Added
- Implemented smart defaults engine in `user_orchestrator.py` (`resolve_study_configuration` and `resolve_style`), automatically resolving vision task styles (`detect`, `segment`, `classify`, `pose`, `obb`) and mapping them to their corresponding Optuna fitness objective metrics (`mAP50-95(B)`, `mAP50-95(M)`, `accuracy_top1`, `mAP50-95(P)`).
- Added automatic resolution for minimal YAML configurations: default `direction: "maximize"`, default `sampler: "TPESampler"`, default `algorithm: "optuna"`, default `train.batch: -1` (AutoBatch), and timestamped fallback study names.
- Added comprehensive unit tests in `tests/test_defaults_resolution.py` verifying smart defaults, task style resolution, and user override preservation.

## [2.0.1] - 2026-10-29
### Fixed
- Fixed trial counter overflow in `record_progress` within `user_orchestrator.py` by capping `completed` trials to `n_trials`, preventing distorted progress metrics (e.g. `20 / 7 trials`).

## [1.2.1] - 2026-10-28
### Fixed
- Enhanced worker queue resolution to inspect root-level `debug`, `sweeper.target_worker_queue`, and root `target_worker_queue` alongside `sweeper.debug`, preventing private worker tasks from unintentionally falling back to public queues.

## [1.2.0] - 2026-05-27
### Added
- Integrated **Optuna** persistence for relational databases.
- Multi-user registry support for task attribution.
- New marketing landing page.
