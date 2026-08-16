from src.council.council_os_models import (
    CouncilOSResult,
    CouncilVerdict,
    DecisionVote,
    FrameworkAssessment,
    FrameworkFactMisclassification,
    FrameworkMatch,
    FrameworkSelection,
    FrameworkSelectionSummary,
    ProblemProfile,
)


def test_framework_models_are_sanitized_and_serializable():
    selection = FrameworkSelection(
        policy_version="framework-selector-v1",
        matches=[
            FrameworkMatch(
                framework_id="value_equation",
                score=8,
                reason_labels=["primary_domain", "routed_expert"],
                assigned_expert_ids=["offer_pricing"],
            )
        ],
        by_expert={"offer_pricing": ["value_equation"]},
    )
    summary = FrameworkSelectionSummary(
        policy_version=selection.policy_version,
        selected_framework_ids=["value_equation"],
        by_expert=selection.by_expert,
        reason_labels_by_framework={"value_equation": ["primary_domain"]},
        retrieval_status_by_expert={"offer_pricing": "framework_match"},
        rejected_framework_ids=[],
        selector_error_labels=[],
    )

    payload = summary.model_dump(mode="json")
    assert "book_text" not in payload
    assert payload["selected_framework_ids"] == ["value_equation"]


def test_framework_fact_misclassification_uses_stable_claim_ref():
    item = FrameworkFactMisclassification(
        claim_ref="marketing:2",
        framework_id="positioning_category",
        reason="framework_rule_presented_as_fact",
    )
    assessment = FrameworkAssessment(misclassified_fact_claims=[item])

    assert assessment.misclassified_fact_claims[0].claim_ref == "marketing:2"


def test_council_result_keeps_framework_summary_backward_compatible():
    result = CouncilOSResult(
        profile=ProblemProfile(primary_domain="strategy"),
        routed_experts=["strategy"],
        verdict=CouncilVerdict(
            verdict=DecisionVote.DEFER,
            recommendation="Need evidence",
            confidence=0.2,
            consensus="low",
            key_disagreement="unknown",
            minority_report="",
        ),
    )

    assert result.framework_selection_summary is None
