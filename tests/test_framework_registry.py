from src.council.framework_registry import FRAMEWORK_POLICY_VERSION, FRAMEWORK_REGISTRY


def test_registry_has_expected_unique_ids():
    assert FRAMEWORK_POLICY_VERSION == "framework-selector-v1"
    assert set(FRAMEWORK_REGISTRY) == {
        "strategic_choice",
        "competitive_advantage",
        "positioning_category",
        "value_equation",
        "customer_job_evidence",
        "growth_loop",
        "operating_constraint",
        "reversibility_experiment",
    }
    assert len(FRAMEWORK_REGISTRY) == len(set(FRAMEWORK_REGISTRY))


def test_registry_contains_only_short_public_framework_copy():
    forbidden = ("drive_file_id", "private-library", "chapter ", "page ")
    for framework in FRAMEWORK_REGISTRY.values():
        assert framework.description
        assert len(framework.description) <= 280
        assert 2 <= len(framework.diagnostic_questions) <= 3
        serialized = repr(framework).casefold()
        assert all(token not in serialized for token in forbidden)
