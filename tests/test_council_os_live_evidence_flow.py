import pytest

from src.council.council_os import CouncilOS
from src.council.council_os_models import LiveEvidenceContext
from tests.live_evidence_support import FakeLiveProvider, StageLLM, source


def _no_matches(*_args, **_kwargs):
    from src.knowledge.private_models import KnowledgeRetrievalResult

    return KnowledgeRetrievalResult(status="no_matches")


@pytest.mark.asyncio
async def test_live_provider_is_called_after_rebuttals_and_before_red_team():
    events = []
    context = LiveEvidenceContext(
        status="ok",
        query_count=1,
        sources=[source("web_accept", "ACCEPTED_LIVE_SENTINEL", "https://example.com/a")],
    )
    council = CouncilOS(
        StageLLM(events=events),
        retriever=_no_matches,
        live_evidence_provider=FakeLiveProvider(context, events=events),
    )

    await council.deliberate("marketing positioning decision")

    assert events.index("rebuttal") < events.index("live_collect") < events.index("red_team")


@pytest.mark.asyncio
async def test_live_evidence_firewalls_and_chairman_acceptance_gate():
    context = LiveEvidenceContext(
        status="ok",
        query_count=1,
        sources=[
            source("web_accept", "ACCEPTED_LIVE_SENTINEL", "https://example.com/a"),
            source("web_reject", "REJECTED_LIVE_SENTINEL", "https://example.com/b"),
        ],
    )
    llm = StageLLM()
    council = CouncilOS(llm, retriever=_no_matches, live_evidence_provider=FakeLiveProvider(context))

    result = await council.deliberate("marketing positioning decision")

    prompts = {stage: user for stage, _system, user in llm.calls}
    assert "ACCEPTED_LIVE_SENTINEL" not in prompts["BLIND"]
    assert "ACCEPTED_LIVE_SENTINEL" not in prompts["REBUTTAL"]
    assert "ACCEPTED_LIVE_SENTINEL" in prompts["RED_TEAM"]
    assert "ACCEPTED_LIVE_SENTINEL" in prompts["EVIDENCE_JUDGE"]
    assert "ACCEPTED_LIVE_SENTINEL" in prompts["CHAIRMAN"]
    assert "REJECTED_LIVE_SENTINEL" not in prompts["CHAIRMAN"]
    assert "https://example.com/b" not in prompts["CHAIRMAN"]
    assert result.evidence.live_evidence.accepted_evidence_ids == ["web_accept"]
    assert [(item.evidence_id, item.reason) for item in result.evidence.live_evidence.rejected_evidence] == [
        ("web_reject", "other_evidence_issue")
    ]
    assert result.evidence.live_evidence.source_conflict_labels == ["other_source_conflict"]


@pytest.mark.asyncio
async def test_provider_exception_is_unavailable_and_nonfatal():
    council = CouncilOS(
        StageLLM(),
        retriever=_no_matches,
        live_evidence_provider=FakeLiveProvider(error=RuntimeError("PRIVATE_PROVIDER_EXCEPTION")),
    )

    result = await council.deliberate("marketing positioning decision")

    assert result.verdict.verdict.value == "TEST"
    assert result.live_evidence_summary.status == "unavailable"
    assert "live_evidence_unavailable" in result.errors
    assert "PRIVATE_PROVIDER_EXCEPTION" not in result.model_dump_json()
