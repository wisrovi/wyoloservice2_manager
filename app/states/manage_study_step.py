"""WPipe step for delegating and executing a manager Optuna study."""

from typing import Any, Dict
from wpipe import step, to_obj

from dto.study_dto import StudyConfigDTO


@step(name="manage_study_step", version="v1.0", tags=["manager", "study"])
@to_obj(StudyConfigDTO)
def manage_study_step(input_data: StudyConfigDTO) -> Dict[str, Any]:
    """Execute Optuna study optimization step within WPipe pipeline.

    Args:
        input_data (StudyConfigDTO): Validated study configuration container.

    Returns:
        Dict[str, Any]: Execution state dictionary confirming study dispatch.
    """
    from user_orchestrator import manage_study

    config_dict = input_data.model_dump()
    result = manage_study(config_dict)
    return {"study_result": result}
