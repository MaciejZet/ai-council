import json

import pytest

from src.council.business_routing import profile_problem, route_experts
from src.council.council_os import CouncilOS
from src.council.council_os_models import DecisionVote
from src.knowledge.private_models import KnowledgeRetrievalResult
from src.llm_providers import LLMResponse


class DeliberationFakeLLM:
    def __init__(self, *, malformed_stages=None, malformed_blind_experts=None):
        self.calls = []
        self.malformed_stages = set(malformed_stages or [])
        self.malformed_blind_experts = set(malformed_blind_experts or [])

    @staticmethod
    def _stage(system_prompt):
        for stage in ("BLIND", "REBUTTAL", "RED_TEAM", "EVIDENCE_JUDGE", "CHAIRMAN"):
            if f"[STAGE:{stage}]" in system_prompt:
                return stage
        raise AssertionError("missing stage marker")

    @staticmethod
    def _expert_id(system_prompt):
        if "[EXPERT_ID:" not in system_prompt:
            return None
        return system_prompt.split("[EXPERT_ID:", 1)[1].split("]", 1)[0]

    async def generate(self, system_prompt, user_prompt, temperature=0.7, max_tokens=None):
        stage = self._stage(system_prompt)
        expert_id = self._expert_id(system_prompt)
        self.calls.append(
            {
                "stage": stage,
                "expert_id": expert_id,
                "system": system_prompt,
                "user": user_prompt,
            }
        )

        if stage in self.malformed_stages:
            return LLMResponse(content="not-json", model="fake")
        if stage == "BLIND" and expert_id in self.malformed_blind_experts:
            return LLMResponse(content="not-json", model="fake")

        if stage == "BLIND":
            payload = {
                "expert_id": expert_id,
                "vote": "TEST",
                "recommendation": f"synthetic memo {expert_id}",
                "confidence": 0.7,
                "claims": [],
                "assumptions": ["synthetic assumption"],
                "risks": ["synthetic risk"],
                "what_changes_my_mind": ["synthetic evidence"],
            }
        elif stage == "REBUTTAL":
            payload = {
                "expert_id": expert_id,
                "strongest_agreement": "synthetic agreement",
                "strongest_disagreement": "synthetic disagreement",
                "assumption_to_test": "synthetic assumption",
                "revised_vote": "TEST",
                "revised_confidence": 0.68,
            }
        elif stage == "RED_TEAM":
            payload = {
                "failure_modes": ["synthetic failure mode"],
                "challenged_assumptions": ["synthetic assumption"],
                "double_crux_questions": ["synthetic double crux"],
                "premature_consensus": False,
                "contrarian_case": "",
                "parse_error": False,
            }
        elif stage == "EVIDENCE_JUDGE":
            payload = {
                "supported_claims": ["synthetic supported claim"],
                "weak_or_unsupported_claims": [],
                "contradictions": [],
                "evidence_gaps": [],
                "knowledge_status_by_expert": {},
                "framework_fact_confusions": [],
                "parse_error": False,
            }
        elif stage == "CHAIRMAN":
            payload = {
                "verdict": "TEST",
                "recommendation": "Run the discriminating synthetic pilot.",
                "confidence": 0.72,
                "consensus": "Broad agreement on testing first.",
                "key_disagreement": "Expected size of upside.",
                "minority_report": "A minority would defer until more evidence exists.",
                "assumptions": ["Synthetic assumption"],
                "evidence_gaps": [],
                "what_would_change_decision": ["Synthetic customer evidence"],
                "next_experiment": {
                    "action": "Run pilot",
                    "metric": "conversion",
                    "threshold": "10%",
                    "timeline": "14 days",
                    "kill_criteria": "below 2%",
                },
            }
        else:
            raise AssertionError(f"unexpected stage: {stage}")
        return LLMResponse(content=json.dumps(payload), model="fake")


class DeliberationFakeRetriever:
    def __init__(self, unavailable_alias=None):
        self.unavailable_alias = unavailable_alias

    def __call__(self, query, **kwargs):
        aliases = kwargs.get("experts") or []
        if self.unavailable_alias and self.unavailable_alias in aliases:
            return KnowledgeRetrievalResult(
                status="unavailable",
                error_code="synthetic_unavailable",
            )
        return KnowledgeRetrievalResult(
            status="ok",
            chunks=[
                {
                    "text": "PRIVATE_SYNTHETIC_CHUNK",
                    "title": "Synthetic Source",
                    "doc_id": "synthetic-doc",
                    "source_type": "synthesis",
                    "chunk_index": 0,
                    "score": 0.9,
                }
            ],
        )


@pytest.mark.asyncio
async def test_deliberate_orders_all_phases_chairman_last_and_sanitizes_result():
    llm = DeliberationFakeLLM()
    council = CouncilOS(
        llm,
        retriever=DeliberationFakeRetriever(),
        knowledge_namespace="private-test",
    )

    result = await council.deliberate("Should we change pricing and positioning with a pilot?")

    stages = [call["stage"] for call in llm.calls]
    last_blind = max(index for index, stage in enumerate(stages) if stage == "BLIND")
    first_rebuttal = min(index for index, stage in enumerate(stages) if stage == "REBUTTAL")
    red_index = stages.index("RED_TEAM")
    evidence_index = stages.index("EVIDENCE_JUDGE")
    chairman_index = stages.index("CHAIRMAN")
    assert last_blind < first_rebuttal < red_index < evidence_index < chairman_index
    assert chairman_index == len(stages) - 1
    assert result.verdict.verdict == DecisionVote.TEST
    assert 4 <= len(result.routed_experts) <= 5
    assert "PRIVATE_SYNTHETIC_CHUNK" not in result.model_dump_json()


@pytest.mark.asyncio
async def test_malformed_chairman_output_returns_typed_defer():
    llm = DeliberationFakeLLM(malformed_stages={"CHAIRMAN"})
    council = CouncilOS(
        llm,
        retriever=DeliberationFakeRetriever(),
        knowledge_namespace="private-test",
    )

    result = await council.deliberate("Should we change our pricing strategy?")

    assert result.verdict.verdict == DecisionVote.DEFER
    assert "chairman_parse_error" in result.verdict.evidence_gaps
    assert llm.calls[-1]["stage"] == "CHAIRMAN"


@pytest.mark.asyncio
async def test_fewer_than_two_domain_memos_defers_without_review_or_chairman():
    query = "Should we change pricing and sales execution?"
    experts = route_experts(profile_problem(query))
    malformed = {expert.id for expert in experts[1:]}
    llm = DeliberationFakeLLM(malformed_blind_experts=malformed)
    council = CouncilOS(
        llm,
        retriever=DeliberationFakeRetriever(),
        knowledge_namespace="private-test",
    )

    result = await council.deliberate(query)

    assert len(result.memos) == 1
    assert result.verdict.verdict == DecisionVote.DEFER
    assert "insufficient_domain_memos" in result.verdict.evidence_gaps
    assert {call["stage"] for call in llm.calls} == {"BLIND"}


@pytest.mark.asyncio
async def test_unavailable_private_knowledge_survives_full_pipeline():
    llm = DeliberationFakeLLM()
    council = CouncilOS(
        llm,
        retriever=DeliberationFakeRetriever(unavailable_alias="strategy"),
        knowledge_namespace="private-test",
    )

    result = await council.deliberate("Should we change our competitive strategy?")

    assert result.knowledge_status_by_expert["strategy"] == "unavailable"
    assert result.evidence is not None
    assert result.evidence.knowledge_status_by_expert["strategy"] == "unavailable"
