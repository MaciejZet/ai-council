from src.council.council_os_models import (
    AnalogDecision,
    CouncilOSResult,
    CouncilVerdict,
    DecisionVote,
    HistoricalAnalogyRejection,
    HistoricalContextAssessment,
    LearningContextSummary,
    ProblemProfile,
)


def _result() -> CouncilOSResult:
    return CouncilOSResult(
        profile=ProblemProfile(primary_domain="growth"),
        routed_experts=[],
        verdict=CouncilVerdict(
            verdict=DecisionVote.TEST,
            recommendation="x",
            confidence=0.5,
            consensus="x",
            key_disagreement="x",
            minority_report="",
        ),
    )


def test_new_learning_fields_default_without_breaking_existing_result():
    result = _result()

    assert result.learning_context_summary is None
    assert result.evidence is None


def test_learning_summary_is_metadata_only():
    summary = LearningContextSummary(
        status="ok",
        scored_history_count=15,
        analogy_count=2,
        active_sample_strengths={"growth": "normal"},
    )

    dumped = summary.model_dump()
    forbidden = {"query", "postmortem", "notes", "recommendation", "source_text"}
    assert forbidden.isdisjoint(dumped)


def test_historical_assessment_serializes_ids_and_reason_labels():
    assessment = HistoricalContextAssessment(
        accepted_analogy_ids=["a"],
        rejected_analogies=[
            HistoricalAnalogyRejection(
                decision_id="b",
                reason="current_evidence_conflict",
            )
        ],
    )

    assert assessment.model_dump()["rejected_analogies"][0] == {
        "decision_id": "b",
        "reason": "current_evidence_conflict",
    }


def test_analog_decision_has_no_free_text_history_fields():
    analog = AnalogDecision(
        decision_id="d",
        primary_domain="growth",
        decision_kind="general",
        reversibility="reversible",
        risk_level="medium",
        verdict="TEST",
        verdict_confidence=0.5,
        resolved_vote="GO",
        outcome_status="success",
        similarity_score=9,
        matching_dimensions=["primary_domain"],
    )

    assert "query" not in analog.model_dump()
    assert "postmortem" not in analog.model_dump()
