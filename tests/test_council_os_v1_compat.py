import inspect

from src.council.council_os import CouncilOS


def test_v1_stage_helpers_keep_learning_optional():
    for method_name in (
        "_run_rebuttals",
        "_run_red_team",
        "_run_evidence_judge",
        "_run_chairman",
    ):
        parameter = inspect.signature(getattr(CouncilOS, method_name)).parameters["learning"]
        assert parameter.default is None
