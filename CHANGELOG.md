# Changelog - Orchestrator Manager

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
