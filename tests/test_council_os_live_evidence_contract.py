import inspect

import pytest

from src.council.council_os import CouncilOS
from src.council.council_os_models import LiveEvidenceContext
from tests.live_evidence_support import FakeLiveProvider, StageLLM


def test_live_evidence_stage_helpers_keep_old_call_compatibility():
    for method_name in ("_run_red_team", "_run_evidence_judge", "_run_chairman"):
        params = inspect.signature(getattr(CouncilOS, method_name)).parameters
        assert params["learning"].default is None
        assert params["live_evidence"].default is None


@pytest.mark.asyncio
async def test_external_search_boundary_never_receives_private_retrieval_or_history_text():
    private_rag = "PRIVATE_RAG_SENTINEL"
    private_history = "PRIVATE_HISTORY_SENTINEL"
    from src.knowledge.private_models import KnowledgeRetrievalResult

    def retriever(*_args, **_kwargs):
        return KnowledgeRetrievalResult(status="ok", chunks=[{"text": private_rag, "title": "private"}])

    def learning_provider(*_args, **_kwargs):
        return {"status": "disabled", "error_labels": []}

    live = FakeLiveProvider(LiveEvidenceContext(status="no_matches", query_count=1))
    council = CouncilOS(
        StageLLM(),
        retriever=retriever,
        learning_context_provider=learning_provider,
        live_evidence_provider=live,
    )

    await council.deliberate("Should we enter Germany?")

    assert live.calls
    question, _profile, framework_ids = live.calls[0]
    assert question == "Should we enter Germany?"
    assert private_rag not in question
    assert private_history not in question
    assert all(private_rag not in framework_id for framework_id in framework_ids)
