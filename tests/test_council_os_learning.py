import json

import pytest

from src.council.council_os import CouncilOS
from src.council.expert_registry import EXPERT_REGISTRY
from src.council.council_os_models import AnalogDecision, ExpertCalibrationSignal, LearningContext
from src.knowledge.private_models import KnowledgeRetrievalResult
from src.llm_providers import LLMResponse

ACCEPTED_ID = "HIST_ACCEPTED_ID"
REJECTED_ID = "HIST_REJECTED_ID"


class RecordingLLM:
    def __init__(self):
        self.calls = []

    @staticmethod
    def _stage(system_prompt):
        for stage in ("BLIND", "REBUTTAL", "RED_TEAM", "EVIDENCE_JUDGE", "CHAIRMAN"):
            if f"[STAGE:{stage}]" in system_prompt:
                return stage
        raise AssertionError("missing stage")

    @staticmethod
    def _expert_id(system_prompt):
        if "[EXPERT_ID:" not in system_prompt:
            return None
        return system_prompt.split("[EXPERT_ID:", 1)[1].split("]", 1)[0]

    async def generate(self, system_prompt, user_prompt, temperature=0.7, max_tokens=None):
        stage = self._stage(system_prompt)
        expert_id = self._expert_id(system_prompt)
        self.calls.append(
            {"stage": stage, "expert_id": expert_id, "system": system_prompt, "user": user_prompt}
        )
        if stage == "BLIND":
            vote = "NO-GO" if expert_id == "growth" else "GO"
            payload = {
                "expert_id": expert_id,
                "vote": vote,
                "recommendation": "current case only",
                "confidence": 0.7,
                "claims": [],
                "assumptions": [],
                "risks": [],
                "what_changes_my_mind": [],
            }
        elif stage == "REBUTTAL":
            payload = {
                "expert_id": expert_id,
                "strongest_agreement": "a",
                "strongest_disagreement": "d",
                "assumption_to_test": "x",
                "revised_vote": "TEST",
                "revised_confidence": 0.65,
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
                    "accepted_analogy_ids": [ACCEPTED_ID],
                    "rejected_analogies": [
                        {"decision_id": REJECTED_ID, "reason": "current_evidence_conflict"}
                    ],
                    "usable_calibration_expert_ids": ["growth"],
                    "too_weak_calibration_expert_ids": ["sales"],
                    "current_evidence_conflicts": [REJECTED_ID],
                },
                "parse_error": False,
            }
        elif stage == "CHAIRMAN":
            payload = {
                "verdict": "TEST",
                "recommendation": "Run a current-case test.",
                "confidence": 0.71,
                "consensus": "mixed",
                "key_disagreement": "current evidence",
                "minority_report": "growth dissents",
                "assumptions": [],
                "evidence_gaps": [],
                "what_would_change_decision": [],
                "next_experiment": None,
            }
        else:
            raise AssertionError(stage)
        return LLMResponse(content=json.dumps(payload), model="fake")


def retriever(query, **kwargs):
    return KnowledgeRetrievalResult(status="ok", chunks=[{"text": "CURRENT_PRIVATE_EVIDENCE"}])


def learning_context():
    return LearningContext(
        status="ok",
        expert_signals=[
            ExpertCalibrationSignal(
                expert_id="growth",
                primary_domain="growth",
                sample_size=18,
                sample_strength="normal",
                hit_rate=0.83,
                mean_confidence=0.72,
                brier_like_error=0.12,
                confidence_bias=-0.11,
                reliability_rank=1,
                flags=[],
            ),
            ExpertCalibrationSignal(
                expert_id="sales",
                primary_domain="growth",
                sample_size=7,
                sample_strength="weak",
                hit_rate=0.57,
                mean_confidence=0.81,
                brier_like_error=0.34,
                confidence_bias=0.24,
                reliability_rank=2,
                flags=["overconfidence"],
            ),
        ],
        analog_decisions=[
            AnalogDecision(
                decision_id=ACCEPTED_ID,
                primary_domain="growth",
                decision_kind="pricing",
                reversibility="reversible",
                risk_level="medium",
                verdict="TEST",
                verdict_confidence=0.7,
                resolved_vote="TEST",
                outcome_status="success",
                similarity_score=11,
                matching_dimensions=["primary_domain", "decision_kind"],
            ),
            AnalogDecision(
                decision_id=REJECTED_ID,
                primary_domain="growth",
                decision_kind="pricing",
                reversibility="reversible",
                risk_level="medium",
                verdict="GO",
                verdict_confidence=0.9,
                resolved_vote="NO-GO",
                outcome_status="failure",
                similarity_score=10,
                matching_dimensions=["primary_domain"],
            ),
        ],
        bias_alerts=["overconfidence"],
        protected_minority_expert_ids=["growth"],
        scored_history_count=18,
    )


@pytest.mark.asyncio
async def test_learning_is_loaded_only_after_all_blind_calls_and_never_leaks_into_blind_prompts():
    llm = RecordingLLM()
    provider_calls = []

    def provider(profile, routed_expert_ids, blind_memos):
        provider_calls.append([call["stage"] for call in llm.calls])
        return learning_context()

    council = CouncilOS(llm, retriever=retriever, learning_context_provider=provider)
    result = await council.deliberate(
        "Should growth and sales change pricing with a reversible experiment?"
    )

    assert len(provider_calls) == 1
    assert len(provider_calls[0]) >= 4
    assert set(provider_calls[0]) == {"BLIND"}
    blind_calls = [call for call in llm.calls if call["stage"] == "BLIND"]
    assert all(
        ACCEPTED_ID not in call["user"] and REJECTED_ID not in call["user"]
        for call in blind_calls
    )
    assert result.learning_context_summary is not None
    assert result.learning_context_summary.status == "ok"


@pytest.mark.asyncio
async def test_stage_exposure_and_evidence_judge_filtering_keep_rejected_analogy_away_from_chairman():
    llm = RecordingLLM()
    council = CouncilOS(llm, retriever=retriever, learning_context_provider=lambda *_: learning_context())

    result = await council.deliberate(
        "Should growth and sales change pricing with a reversible experiment?"
    )

    rebuttal_users = [call["user"] for call in llm.calls if call["stage"] == "REBUTTAL"]
    assert any(ACCEPTED_ID in text for text in rebuttal_users)
    red_user = next(call["user"] for call in llm.calls if call["stage"] == "RED_TEAM")
    assert "overconfidence" in red_user
    assert "growth" in red_user
    evidence_user = next(call["user"] for call in llm.calls if call["stage"] == "EVIDENCE_JUDGE")
    assert ACCEPTED_ID in evidence_user and REJECTED_ID in evidence_user
    chairman = next(call for call in llm.calls if call["stage"] == "CHAIRMAN")
    assert ACCEPTED_ID in chairman["user"]
    assert REJECTED_ID not in chairman["user"]
    assert "protected minority" in chairman["system"].lower()
    assert result.learning_context_summary.rejected_analogies[0].decision_id == REJECTED_ID
    assert result.learning_context_summary.influenced_final_stage is True


@pytest.mark.asyncio
async def test_learning_provider_failure_is_sanitized_and_does_not_break_deliberation():
    llm = RecordingLLM()

    def broken_provider(*_args):
        raise RuntimeError("PRIVATE_STORAGE_EXCEPTION_SENTINEL")

    council = CouncilOS(llm, retriever=retriever, learning_context_provider=broken_provider)
    result = await council.deliberate(
        "Should growth and sales change pricing with a reversible experiment?"
    )

    assert result.verdict.verdict.value == "TEST"
    assert "learning_context_unavailable" in result.errors
    dumped = result.model_dump_json()
    assert "PRIVATE_STORAGE_EXCEPTION_SENTINEL" not in dumped
    assert result.learning_context_summary.status == "unavailable"


def test_blind_prompt_contains_a_valid_json_schema_example():
    council = CouncilOS(RecordingLLM(), retriever=retriever)
    prompt = council._blind_system_prompt(EXPERT_REGISTRY["strategy"])
    schema = prompt[prompt.index("{") :]

    parsed = json.loads(schema)
    assert parsed["expert_id"] == "strategy"
    assert parsed["assumptions"] == ["string"]
    assert parsed["risks"] == ["string"]
    assert parsed["what_changes_my_mind"] == ["string"]
