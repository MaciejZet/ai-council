import pytest

from src.council.council_os import CouncilOS
from src.council.council_os_models import LiveEvidenceContext, LiveEvidenceSource, ProblemProfile
from tests.live_evidence_support import FakeLiveProvider, StageLLM


def _no_matches(*_args, **_kwargs):
    from src.knowledge.private_models import KnowledgeRetrievalResult

    return KnowledgeRetrievalResult(status="no_matches")


@pytest.mark.asyncio
async def test_custom_provider_sources_are_canonicalized_at_council_boundary():
    malicious = LiveEvidenceContext(
        status="ok",
        query_count=1,
        sources=[
            LiveEvidenceSource(
                evidence_id="web_custom",
                query_index=0,
                title="Custom",
                canonical_url="HTTPS://alice:SuperSecret@WWW.Example.COM/path?q=1#frag",
                domain="attacker.invalid",
                snippet="safe snippet",
                relevance_score=0.5,
                fetched_at="2026-08-16T12:00:00+00:00",
            )
        ],
    )
    council = CouncilOS(
        StageLLM(),
        retriever=_no_matches,
        live_evidence_provider=FakeLiveProvider(malicious),
    )

    normalized = await council._collect_live_evidence(
        "Should we enter Germany?",
        ProblemProfile(primary_domain="strategy"),
    )

    assert normalized.sources[0].canonical_url == "https://www.example.com/path"
    assert normalized.sources[0].domain == "example.com"
    assert "alice" not in normalized.model_dump_json()
    assert "SuperSecret" not in normalized.model_dump_json()


@pytest.mark.asyncio
async def test_custom_provider_is_capped_to_ten_valid_sources_at_council_boundary():
    sources = [
        LiveEvidenceSource(
            evidence_id=f"web_{index}",
            query_index=0,
            title=f"Source {index}",
            canonical_url=f"https://example.com/{index}",
            domain="example.com",
            snippet="x",
            relevance_score=0.5,
            fetched_at="2026-08-16T12:00:00+00:00",
        )
        for index in range(11)
    ]
    council = CouncilOS(
        StageLLM(),
        retriever=_no_matches,
        live_evidence_provider=FakeLiveProvider(
            LiveEvidenceContext(status="ok", query_count=1, sources=sources)
        ),
    )

    normalized = await council._collect_live_evidence(
        "Should we enter Germany?",
        ProblemProfile(primary_domain="strategy"),
    )

    assert len(normalized.sources) == 10
    assert [source.evidence_id for source in normalized.sources] == [f"web_{index}" for index in range(10)]

@pytest.mark.asyncio
async def test_custom_provider_duplicate_evidence_ids_are_deduplicated_at_council_boundary():
    sources = [
        LiveEvidenceSource(
            evidence_id="web_dup",
            query_index=0,
            title=f"Source {index}",
            canonical_url=f"https://example.com/{index}",
            domain="example.com",
            snippet=f"snippet {index}",
            relevance_score=0.5,
            fetched_at="2026-08-16T12:00:00+00:00",
        )
        for index in range(2)
    ]
    council = CouncilOS(
        StageLLM(),
        retriever=_no_matches,
        live_evidence_provider=FakeLiveProvider(
            LiveEvidenceContext(status="ok", query_count=1, sources=sources)
        ),
    )

    normalized = await council._collect_live_evidence(
        "Should we enter Germany?",
        ProblemProfile(primary_domain="strategy"),
    )

    assert len(normalized.sources) == 1
    assert normalized.sources[0].evidence_id == "web_dup"
    assert normalized.sources[0].canonical_url == "https://example.com/0"
