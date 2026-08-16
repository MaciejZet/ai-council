import json

import pytest

from src.council.council_os import CouncilOS
from src.council.council_os_models import (
    FrameworkMatch,
    FrameworkSelection,
    FrameworkSelectionSummary,
    LiveEvidenceSummary,
    ProblemProfile,
)
from src.council.expert_registry import EXPERT_REGISTRY
from src.council.framework_registry import FRAMEWORK_POLICY_VERSION
from src.knowledge.private_models import KnowledgeRetrievalResult
from src.llm_providers import LLMResponse
from src.storage.decision_memory import DecisionMemoryStore
from src.council.council_os_models import CouncilOSResult, CouncilVerdict


class BlindLLM:
    async def generate(self, system_prompt, user_prompt, temperature=0.7, max_tokens=None):
        expert_id = system_prompt.split("[EXPERT_ID:", 1)[1].split("]", 1)[0]
        payload = {
            "expert_id": expert_id,
            "vote": "TEST",
            "recommendation": "test",
            "confidence": 0.5,
            "claims": [],
            "assumptions": [],
            "risks": [],
            "what_changes_my_mind": [],
        }
        return LLMResponse(content=json.dumps(payload), model="fake")


@pytest.mark.asyncio
async def test_framework_retrieval_no_match_fallback_is_unchanged():
    calls = []

    def retriever(_query, **kwargs):
        calls.append(kwargs)
        if kwargs.get("framework_tags"):
            return KnowledgeRetrievalResult(status="no_matches")
        return KnowledgeRetrievalResult(status="ok", chunks=[])

    expert = EXPERT_REGISTRY["marketing"]
    selection = FrameworkSelection(
        policy_version=FRAMEWORK_POLICY_VERSION,
        matches=[
            FrameworkMatch(
                framework_id="positioning_category",
                score=8,
                reason_labels=["primary_domain"],
                assigned_expert_ids=["marketing"],
            )
        ],
        by_expert={"marketing": ["positioning_category"]},
    )
    council = CouncilOS(BlindLLM(), retriever=retriever, live_evidence_provider=_DisabledLive())
    blind = await council._run_blind_memos("positioning decision", [expert], selection)

    assert len(calls) == 2
    assert calls[0]["framework_tags"]
    assert "framework_tags" not in calls[1]
    assert blind.framework_retrieval_status_by_expert["marketing"] == "framework_no_match_fallback_ok"
    assert blind.knowledge_status_by_expert["marketing"] == "ok"


def test_framework_card_and_fmw_discipline_remain_in_blind_prompt():
    expert = EXPERT_REGISTRY["marketing"]
    council = CouncilOS(BlindLLM(), live_evidence_provider=_DisabledLive())
    prompt = council._blind_user_prompt(
        "positioning decision",
        expert,
        KnowledgeRetrievalResult(status="no_matches"),
        ["positioning_category"],
    )
    assert "[FRAMEWORK:positioning_category]" in prompt
    assert "Use [FMW]" in prompt


class _DisabledLive:
    async def collect(self, question, profile, framework_ids):
        from src.council.council_os_models import LiveEvidenceContext
        return LiveEvidenceContext(status="disabled")


def test_decision_memory_keeps_framework_summary_when_live_summary_is_added(tmp_path):
    store = DecisionMemoryStore(tmp_path / "dm.db")
    result = CouncilOSResult(
        profile=ProblemProfile(primary_domain="strategy", decision_kind="strategy"),
        routed_experts=[],
        verdict=CouncilVerdict(
            verdict="TEST",
            recommendation="test",
            confidence=0.5,
            consensus="mixed",
            key_disagreement="x",
            minority_report="",
        ),
        framework_selection_summary=FrameworkSelectionSummary(
            policy_version=FRAMEWORK_POLICY_VERSION,
            selected_framework_ids=["strategic_choice"],
            by_expert={"strategy": ["strategic_choice"]},
        ),
        live_evidence_summary=LiveEvidenceSummary(status="disabled"),
    )
    decision_id = store.capture_decision("u1", "q", result)
    record = store.get_decision("u1", decision_id)
    assert record["framework_selection_summary"]["selected_framework_ids"] == ["strategic_choice"]
    assert record["live_evidence_summary"]["status"] == "disabled"
