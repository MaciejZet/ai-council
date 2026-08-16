from src.council.council_os_models import (
    LiveEvidenceAssessment,
    LiveEvidenceContext,
    LiveEvidenceRejection,
    LiveEvidenceSource,
    LiveEvidenceSummary,
)


def test_live_source_bounds_and_score():
    source = LiveEvidenceSource(
        evidence_id="web_abc123",
        query_index=0,
        title="x" * 300,
        canonical_url="https://example.com/a",
        domain="www.EXAMPLE.com",
        snippet="hello\x00" + "z" * 800,
        relevance_score=9,
        fetched_at="2026-08-16T12:00:00+00:00",
    )
    assert len(source.title) <= 180
    assert len(source.snippet) <= 600
    assert "\x00" not in source.snippet
    assert source.domain == "example.com"
    assert source.relevance_score == 1.0


def test_live_rejection_reason_is_allowlisted():
    rejection = LiveEvidenceRejection(evidence_id="web_a", reason="free text from model")
    assert rejection.reason == "other_evidence_issue"


def test_live_assessment_accepted_wins_and_conflicts_are_allowlisted():
    assessment = LiveEvidenceAssessment(
        accepted_evidence_ids=["web_a", "web_a"],
        rejected_evidence=[
            LiveEvidenceRejection(evidence_id="web_a", reason="weak_relevance"),
            LiveEvidenceRejection(evidence_id="web_b", reason="anything"),
            LiveEvidenceRejection(evidence_id="web_b", reason="contradicted"),
        ],
        source_conflict_labels=["sources_disagree", "free text"],
    )
    assert assessment.accepted_evidence_ids == ["web_a"]
    assert [(x.evidence_id, x.reason) for x in assessment.rejected_evidence] == [("web_b", "other_evidence_issue")]
    assert assessment.source_conflict_labels == ["sources_disagree", "other_source_conflict"]


def test_live_summary_contains_only_diagnostics():
    summary = LiveEvidenceSummary(
        status="ok",
        query_count=1,
        source_count=1,
        source_domains=["Example.COM", "example.com"],
        accepted_evidence_ids=["web_a", "web_a"],
        rejected_evidence_ids=["web_b"],
        error_labels=["partial_search_failure", "private_exception"],
    )
    dumped = summary.model_dump()
    assert summary.source_domains == ["example.com"]
    assert summary.accepted_evidence_ids == ["web_a"]
    assert summary.error_labels == ["partial_search_failure"]
    assert "snippet" not in dumped and "url" not in dumped
