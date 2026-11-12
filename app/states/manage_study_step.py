"""WPipe step for delegating and executing a manager Optuna study."""

from typing import Any

from dto.study_dto import StudyConfigDTO
from user_orchestrator import manage_study
from wpipe.decorators.step import step
from wpipe.util.transform import to_obj


@step(name="manage_study_step", version="v1.0", tags=["manager", "study"])
@to_obj(StudyConfigDTO)
def manage_study_step(input_data: StudyConfigDTO) -> dict[str, Any]:
    """Execute Optuna study optimization step within WPipe pipeline.

    Args:
        input_data (StudyConfigDTO): Validated study configuration container.

    Returns:
        Dict[str, Any]: Execution state dictionary confirming study dispatch.
    """
    config_dict = input_data.model_dump()
    result = manage_study(config_dict)
    return {"study_result": result}
