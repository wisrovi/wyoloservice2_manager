# Changelog

All notable changes to the **Wyolo Manager Orchestrator** will be documented in this file.

## [1.1.0] - 2026-05-15

### Added
- **Extreme Robustness Engine**: Introduced `BASE_DEFAULT_CONFIG` to automatically repair incomplete or malformed YAML requests.
- **Hierarchical Config Merging**: New logic to merge Defaults -> User YAML -> Optuna Suggestions, ensuring the Invoker always receives a valid payload.
- **Detailed Payload Logging**: Added transparent YAML logging of the exact data sent to Invokers for easier debugging.
- **Manual Robustness Tests**: Added `tests/send_broken_to_manager.py` and `tests/test_broken_config.yaml` to verify system stability.
- **Priority Routing**: Standardized queue routing (`gpus_low`, `gpus_medium`, `gpus_high`) with `gpus_low` as the fail-safe default.

### Changed
- **Redis Connection Logic**: Refactored `src/celery_config.py` to be environment-aware, supporting both `REDIS_URL` and `CONTROL_HOST` with local fallbacks.
- **Optuna Error Handling**: Wrapped study optimization in try-except blocks to prevent worker crashes on database or distribution conflicts.
- **UI Enhancements**: Updated Gradio interface with better status feedback, real-time log monitoring instructions, and updated YAML examples.
- **Infrastructure**: Fixed Docker container naming to `wyolo_manager` for consistent log monitoring.

### Fixed
- Fixed a critical bug where the Manager would crash if a study was reused with a different search space (CategoricalDistribution conflict).
- Fixed a bug where incomplete YAMLs would cause Invoker failures due to missing mandatory fields like `model` or `type`.
- Fixed Redis connection issues when running outside of the Docker network.

---
**William R.** - AI Leader & Solutions Architect
