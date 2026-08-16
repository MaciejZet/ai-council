import json

import pytest

from src.council.council_os import CouncilOS
from src.council.council_os_models import (
    Claim,
    ClaimLabel,
    EvidenceAssessment,
    ExpertMemo,
    FrameworkAssessment,
    FrameworkFactMisclassification,
    FrameworkMatch,
    FrameworkSelection,
    ProblemProfile,
    RedTeamReport,
)
from src.council.expert_registry import EXPERT_REGISTRY
from src.knowledge.private_models import KnowledgeRetrievalResult
from src.llm_providers import LLMResponse


class FrameworkLLM:
    def __init__(self, events=None):
        self.calls = []
        self.events = events if events is not None else []

    @staticmethod
    def _stage(system_prompt):
        for stage in ("BLIND", "REBUTTAL", "RED_TEAM", "EVIDENCE_JUDGE", "CHAIRMAN"):
            if f"[STAGE:{stage}]" in system_prompt:
                return stage
        raise AssertionError("missing stage")

    @staticmethod
    def _expert(system_prompt):
        if "[EXPERT_ID:" not in system_prompt:
            return "unknown"
        return system_prompt.split("[EXPERT_ID:", 1)[1].split("]", 1)[0]

    async def generate(self, system_prompt, user_prompt, temperature=0.7, max_tokens=None):
        stage = self._stage(system_prompt)
        expert = self._expert(system_prompt)
        self.events.append(stage)
        self.calls.append({"stage": stage, "expert": expert, "system": system_prompt, "user": user_prompt})
        if stage == "BLIND":
            payload = {
                "expert_id": expert,
                "vote": "TEST",
                "recommendation": "test",
                "confidence": 0.6,
                "claims": [],
                "assumptions": [],
                "risks": [],
                "what_changes_my_mind": [],
            }
        elif stage == "REBUTTAL":
            payload = {
                "expert_id": expert,
                "strongest_agreement": "a",
                "strongest_disagreement": "d",
                "assumption_to_test": "x",
                "revised_vote": "TEST",
                "revised_confidence": 0.6,
            }
        elif stage == "RED_TEAM":
            payload = {
                "failure_modes": [],
                "challenged_assumptions": [],
                "double_crux_questions": [],
                "premature_consensus": False,
                "contrarian_case": "",
                "parse_error": False,
            }
        elif stage == "EVIDENCE_JUDGE":
            payload = {
                "supported_claims": [],
                "weak_or_unsupported_claims": [],
                "contradictions": [],
                "evidence_gaps": [],
                "knowledge_status_by_expert": {},
                "framework_fact_confusions": [],
                "historical_context": {
                    "accepted_analogy_ids": [],
                    "rejected_analogies": [],
                    "usable_calibration_expert_ids": [],
                    "too_weak_calibration_expert_ids": [],
                    "current_evidence_conflicts": [],
                },
                "parse_error": False,
            }
        else:
            payload = {
                "verdict": "TEST",
                "recommendation": "test",
                "confidence": 0.6,
                "consensus": "mixed",
                "key_disagreement": "x",
                "minority_report": "",
                "assumptions": [],
                "evidence_gaps": [],
                "what_would_change_decision": [],
                "next_experiment": None,
            }
        return LLMResponse(content=json.dumps(payload), model="fake")


def selection_for(expert_id="marketing", framework_id="positioning_category"):
    return FrameworkSelection(
        policy_version="framework-selector-v1",
        matches=[
            FrameworkMatch(
                framework_id=framework_id,
                score=9,
                reason_labels=["primary_domain"],
                assigned_expert_ids=[expert_id],
            )
        ],
        by_expert={expert_id: [framework_id]},
    )


@pytest.mark.asyncio
async def test_selector_runs_before_retrieval_and_before_blind_llm_calls():
    events = []
    llm = FrameworkLLM(events)

    def selector(query, profile, routed_ids):
        events.append("selector")
        assert routed_ids
        return FrameworkSelection(policy_version="framework-selector-v1", by_expert={eid: [] for eid in routed_ids})

    def retriever(query, **kwargs):
        events.append("retrieve")
        return KnowledgeRetrievalResult(status="no_matches")

    council = CouncilOS(llm, retriever=retriever, framework_selector=selector)
    await council.deliberate("Should we change our pricing strategy?")

    assert events[0] == "selector"
    assert events.index("selector") < events.index("retrieve") < events.index("BLIND")


@pytest.mark.asyncio
async def test_framework_no_match_retries_base_retrieval_once_and_records_status():
    calls = []

    def retriever(query, **kwargs):
        calls.append(kwargs)
        if kwargs.get("framework_tags"):
            return KnowledgeRetrievalResult(status="no_matches")
        return KnowledgeRetrievalResult(status="ok", chunks=[{"text": "base evidence"}])

    council = CouncilOS(FrameworkLLM(), retriever=retriever)
    blind = await council._run_blind_memos(
        "position the offer",
        [EXPERT_REGISTRY["marketing"]],
        selection_for(),
    )

    assert len(calls) == 2
    assert calls[0]["framework_tags"]
    assert calls[1].get("framework_tags") is None
    assert blind.framework_retrieval_status_by_expert["marketing"] == "framework_no_match_fallback_ok"


@pytest.mark.asyncio
async def test_framework_unavailable_does_not_retry():
    calls = []

    def retriever(query, **kwargs):
        calls.append(kwargs)
        return KnowledgeRetrievalResult(status="unavailable", error_code="backend_down")

    council = CouncilOS(FrameworkLLM(), retriever=retriever)
    blind = await council._run_blind_memos(
        "position the offer",
        [EXPERT_REGISTRY["marketing"]],
        selection_for(),
    )

    assert len(calls) == 1
    assert blind.framework_retrieval_status_by_expert["marketing"] == "framework_unavailable"


@pytest.mark.asyncio
async def test_expert_without_framework_uses_base_retrieval_once():
    calls = []

    def retriever(query, **kwargs):
        calls.append(kwargs)
        return KnowledgeRetrievalResult(status="no_matches")

    council = CouncilOS(FrameworkLLM(), retriever=retriever)
    blind = await council._run_blind_memos(
        "general question",
        [EXPERT_REGISTRY["marketing"]],
        FrameworkSelection(policy_version="framework-selector-v1", by_expert={"marketing": []}),
    )

    assert len(calls) == 1
    assert calls[0].get("framework_tags") is None
    assert blind.framework_retrieval_status_by_expert["marketing"] == "base_retrieval"


def test_blind_prompt_contains_only_assigned_framework_cards_and_doctrine():
    council = CouncilOS(FrameworkLLM(), retriever=lambda *_args, **_kwargs: KnowledgeRetrievalResult(status="no_matches"))
    prompt = council._blind_user_prompt(
        "position the offer",
        EXPERT_REGISTRY["marketing"],
        KnowledgeRetrievalResult(status="no_matches"),
        ["positioning_category"],
    )

    assert "Selected framework lenses" in prompt
    assert "positioning_category" in prompt
    assert "[FMW]" in prompt
    assert "value_equation" not in prompt
    assert "HIST_ACCEPTED_ID" not in prompt
    assert "peer memo" not in prompt.casefold()


@pytest.mark.asyncio
async def test_red_team_receives_sanitized_framework_selection_and_challenge_doctrine():
    llm = FrameworkLLM()
    council = CouncilOS(llm, retriever=lambda *_args, **_kwargs: KnowledgeRetrievalResult(status="no_matches"))
    selection = selection_for()

    await council._run_red_team(
        "position the offer",
        ProblemProfile(primary_domain="marketing", decision_kind="marketing"),
        [],
        [],
        framework_selection=selection,
    )

    red = next(call for call in llm.calls if call["stage"] == "RED_TEAM")
    assert "positioning_category" in red["user"]
    assert "applicable" in red["system"].casefold()
    assert "correlated" in red["system"].casefold()
    assert "empirical evidence" in red["system"].casefold()
    assert "PRIVATE_BOOK_SENTINEL" not in red["user"]


class FrameworkEvidenceLLM(FrameworkLLM):
    async def generate(self, system_prompt, user_prompt, temperature=0.7, max_tokens=None):
        stage = self._stage(system_prompt)
        if stage != "EVIDENCE_JUDGE":
            return await super().generate(system_prompt, user_prompt, temperature, max_tokens)
        self.calls.append({"stage": stage, "expert": "evidence_judge", "system": system_prompt, "user": user_prompt})
        payload = {
            "supported_claims": [],
            "weak_or_unsupported_claims": [],
            "contradictions": [],
            "evidence_gaps": [],
            "knowledge_status_by_expert": {},
            "framework_fact_confusions": [],
            "historical_context": {
                "accepted_analogy_ids": [],
                "rejected_analogies": [],
                "usable_calibration_expert_ids": [],
                "too_weak_calibration_expert_ids": [],
                "current_evidence_conflicts": [],
            },
            "framework_assessment": {
                "misclassified_fact_claims": [
                    {
                        "claim_ref": "marketing:1",
                        "framework_id": "positioning_category",
                        "reason": "framework_rule_presented_as_fact",
                    },
                    {
                        "claim_ref": "marketing:99",
                        "framework_id": "unknown_framework",
                        "reason": "INVALID_SENTINEL",
                    },
                ],
                "framework_overreach_labels": ["correlated_framework_reasoning"],
                "rejected_framework_ids": ["positioning_category", "unknown_framework"],
            },
            "parse_error": False,
        }
        return LLMResponse(content=json.dumps(payload), model="fake")


@pytest.mark.asyncio
async def test_evidence_judge_uses_stable_claim_refs_and_sanitizes_unknown_framework_output():
    llm = FrameworkEvidenceLLM()
    council = CouncilOS(llm, retriever=lambda *_args, **_kwargs: KnowledgeRetrievalResult(status="no_matches"))
    memo = ExpertMemo(
        expert_id="marketing",
        vote="TEST",
        recommendation="test",
        confidence=0.6,
        claims=[
            Claim(label=ClaimLabel.FRAMEWORK, text="lens claim"),
            Claim(label=ClaimLabel.FACT, text="misclassified claim"),
        ],
    )
    blind = type("Blind", (), {
        "knowledge_status_by_expert": {"marketing": "no_matches"},
        "source_inventory": {"marketing": []},
    })()

    evidence = await council._run_evidence_judge(
        "position the offer",
        ProblemProfile(primary_domain="marketing", decision_kind="marketing"),
        blind,
        [memo],
        [],
        RedTeamReport(),
        framework_selection=selection_for(),
    )

    assert [item.claim_ref for item in evidence.framework_assessment.misclassified_fact_claims] == ["marketing:1"]
    assert evidence.framework_assessment.rejected_framework_ids == ["positioning_category"]
    evidence_call = next(call for call in llm.calls if call["stage"] == "EVIDENCE_JUDGE")
    assert '"marketing:0":{"label":"FMW"}' in evidence_call["user"]
    assert '"marketing:1":{"label":"F"}' in evidence_call["user"]
    assert "lens claim" in evidence_call["user"]


def test_evidence_rejected_framework_is_removed_from_chairman_active_context():
    council = CouncilOS(FrameworkLLM(), retriever=lambda *_args, **_kwargs: KnowledgeRetrievalResult(status="no_matches"))
    selection = selection_for()
    evidence = EvidenceAssessment(
        framework_assessment=FrameworkAssessment(
            rejected_framework_ids=["positioning_category"],
        )
    )

    approved = council._approved_framework_payload(selection, evidence)

    assert approved["active_frameworks"] == []
    assert approved["rejected_framework_ids"] == ["positioning_category"]


@pytest.mark.asyncio
async def test_selector_failure_is_sanitized_and_council_continues_with_empty_selection():
    def broken_selector(*_args):
        raise RuntimeError("PRIVATE_SELECTOR_EXCEPTION_SENTINEL")

    council = CouncilOS(
        FrameworkLLM(),
        retriever=lambda *_args, **_kwargs: KnowledgeRetrievalResult(status="no_matches"),
        framework_selector=broken_selector,
    )
    result = await council.deliberate("Should we change pricing?")

    assert result.verdict.verdict.value == "TEST"
    assert "framework_selector_unavailable" in result.errors
    assert result.framework_selection_summary is not None
    assert result.framework_selection_summary.selected_framework_ids == []
    assert "PRIVATE_SELECTOR_EXCEPTION_SENTINEL" not in result.model_dump_json()


@pytest.mark.asyncio
async def test_framework_summary_tracks_selection_retrieval_and_rejections():
    llm = FrameworkEvidenceLLM()

    def selector(query, profile, routed_ids):
        target = "marketing" if "marketing" in routed_ids else routed_ids[0]
        return FrameworkSelection(
            policy_version="framework-selector-v1",
            matches=[
                FrameworkMatch(
                    framework_id="positioning_category",
                    score=9,
                    reason_labels=["primary_domain", "decision_kind"],
                    assigned_expert_ids=[target],
                )
            ],
            by_expert={eid: (["positioning_category"] if eid == target else []) for eid in routed_ids},
        )

    council = CouncilOS(
        llm,
        retriever=lambda *_args, **_kwargs: KnowledgeRetrievalResult(status="ok", chunks=[]),
        framework_selector=selector,
    )
    result = await council.deliberate("marketing positioning category decision")

    summary = result.framework_selection_summary
    assert summary is not None
    assert summary.selected_framework_ids == ["positioning_category"]
    assert summary.rejected_framework_ids == ["positioning_category"]
    assert "marketing" in summary.retrieval_status_by_expert
