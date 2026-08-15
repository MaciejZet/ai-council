import json

import pytest

from src.council.business_routing import profile_problem, route_experts
from src.council.council_os import CouncilOS
from src.council.council_os_models import DecisionVote
from src.knowledge.private_models import KnowledgeRetrievalResult
from src.llm_providers import LLMResponse


class FakeLLM:
    def __init__(self, *, blind_votes=None, malformed_stages=None):
        self.calls = []
        self.blind_votes = blind_votes or {}
        self.malformed_stages = set(malformed_stages or [])

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

        if stage == "BLIND":
            vote = self.blind_votes.get(expert_id, DecisionVote.TEST)
            vote_value = vote.value if isinstance(vote, DecisionVote) else str(vote)
            payload = {
                "expert_id": expert_id,
                "vote": vote_value,
                "recommendation": f"PEER_MEMO_SENTINEL_{expert_id}",
                "confidence": 0.7,
                "claims": [],
                "assumptions": [],
                "risks": [],
                "what_changes_my_mind": [],
            }
        elif stage == "REBUTTAL":
            payload = {
                "expert_id": expert_id,
                "strongest_agreement": "synthetic agreement",
                "strongest_disagreement": "synthetic disagreement",
                "assumption_to_test": "synthetic assumption",
                "revised_vote": "TEST",
                "revised_confidence": 0.65,
            }
        elif stage == "RED_TEAM":
            premature = "PREMATURE_CONSENSUS=true" in user_prompt
            payload = {
                "failure_modes": ["synthetic failure mode"],
                "challenged_assumptions": ["synthetic assumption"],
                "double_crux_questions": ["synthetic double crux"],
                "premature_consensus": premature,
                "contrarian_case": "synthetic contrarian case" if premature else "",
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
        else:
            raise AssertionError(f"unexpected stage in this test fixture: {stage}")
        return LLMResponse(content=json.dumps(payload), model="fake")


class FakeRetriever:
    def __init__(self, unavailable_alias=None):
        self.calls = []
        self.unavailable_alias = unavailable_alias

    def __call__(self, query, **kwargs):
        self.calls.append((query, kwargs))
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
async def test_blind_round_uses_role_specific_retrieval_and_isolates_peer_memos():
    query = "Should we change pricing, positioning and sales execution?"
    experts = route_experts(profile_problem(query))
    llm = FakeLLM()
    retriever = FakeRetriever()
    council = CouncilOS(
        llm,
        retriever=retriever,
        knowledge_namespace="private-test",
        knowledge_top_k=4,
    )

    blind = await council._run_blind_memos(query, experts)

    assert len(blind.memos) == len(experts)
    assert len(retriever.calls) == len(experts)
    for (_, kwargs), expert in zip(retriever.calls, experts, strict=True):
        assert kwargs["domains"] == list(expert.domains)
        assert kwargs["experts"] == list(expert.retrieval_experts)
        assert kwargs["namespace"] == "private-test"
        assert kwargs["top_k"] == 4

    blind_prompts = [call["user"] for call in llm.calls if call["stage"] == "BLIND"]
    assert len(blind_prompts) == len(experts)
    assert all("PRIVATE_SYNTHETIC_CHUNK" in prompt for prompt in blind_prompts)
    assert all("PEER_MEMO_SENTINEL" not in prompt for prompt in blind_prompts)
    assert all(memo.expert_id in {expert.id for expert in experts} for memo in blind.memos)

    assert blind.source_inventory
    assert all(
        "text" not in source
        for sources in blind.source_inventory.values()
        for source in sources
    )


@pytest.mark.asyncio
async def test_blind_round_preserves_unavailable_knowledge_status():
    query = "Should we change our competitive strategy next quarter?"
    experts = route_experts(profile_problem(query))
    llm = FakeLLM()
    retriever = FakeRetriever(unavailable_alias="strategy")
    council = CouncilOS(llm, retriever=retriever, knowledge_namespace="private-test")

    blind = await council._run_blind_memos(query, experts)

    strategy_memo = next(memo for memo in blind.memos if memo.expert_id == "strategy")
    assert strategy_memo.knowledge_status == "unavailable"
    assert blind.knowledge_status_by_expert["strategy"] == "unavailable"
    assert blind.source_inventory["strategy"] == []


@pytest.mark.asyncio
async def test_rebuttals_begin_after_blind_round_and_only_then_see_peer_memos():
    query = "Should we change pricing and sales execution?"
    profile = profile_problem(query)
    experts = route_experts(profile)
    llm = FakeLLM()
    council = CouncilOS(llm, retriever=FakeRetriever(), knowledge_namespace="private-test")

    blind = await council._run_blind_memos(query, experts)
    rebuttals = await council._run_rebuttals(query, profile, experts, blind.memos)

    assert len(rebuttals) == len(blind.memos)
    stages = [call["stage"] for call in llm.calls]
    last_blind = max(index for index, stage in enumerate(stages) if stage == "BLIND")
    first_rebuttal = min(index for index, stage in enumerate(stages) if stage == "REBUTTAL")
    assert last_blind < first_rebuttal

    for call in (item for item in llm.calls if item["stage"] == "REBUTTAL"):
        peer_section = call["user"].split("Peer blind memos:", 1)[1]
        assert "PEER_MEMO_SENTINEL_" in peer_section
        assert f"PEER_MEMO_SENTINEL_{call['expert_id']}" not in peer_section


@pytest.mark.asyncio
async def test_red_team_requires_contrarian_case_only_above_eighty_percent_consensus():
    query = "Should we change strategy and pricing?"
    profile = profile_problem(query)
    experts = route_experts(profile, min_experts=5, max_experts=5)
    unanimous_votes = {expert.id: DecisionVote.GO for expert in experts}
    llm = FakeLLM(blind_votes=unanimous_votes)
    council = CouncilOS(llm, retriever=FakeRetriever(), knowledge_namespace="private-test")

    blind = await council._run_blind_memos(query, experts)
    rebuttals = await council._run_rebuttals(query, profile, experts, blind.memos)
    red_team = await council._run_red_team(query, profile, blind.memos, rebuttals)

    red_call = next(call for call in llm.calls if call["stage"] == "RED_TEAM")
    assert "PREMATURE_CONSENSUS=true" in red_call["user"]
    assert "REQUIRED: construct the strongest credible contrarian case" in red_call["user"]
    assert red_team.premature_consensus is True

    four_of_five = {expert.id: DecisionVote.GO for expert in experts}
    four_of_five[experts[-1].id] = DecisionVote.TEST
    llm = FakeLLM(blind_votes=four_of_five)
    council = CouncilOS(llm, retriever=FakeRetriever(), knowledge_namespace="private-test")
    blind = await council._run_blind_memos(query, experts)
    rebuttals = await council._run_rebuttals(query, profile, experts, blind.memos)
    red_team = await council._run_red_team(query, profile, blind.memos, rebuttals)

    red_call = next(call for call in llm.calls if call["stage"] == "RED_TEAM")
    assert "PREMATURE_CONSENSUS=false" in red_call["user"]
    assert red_team.premature_consensus is False


@pytest.mark.asyncio
async def test_evidence_judge_receives_provenance_but_not_private_chunk_text():
    query = "Should we change our pricing strategy?"
    profile = profile_problem(query)
    experts = route_experts(profile)
    llm = FakeLLM()
    council = CouncilOS(llm, retriever=FakeRetriever(), knowledge_namespace="private-test")

    blind = await council._run_blind_memos(query, experts)
    rebuttals = await council._run_rebuttals(query, profile, experts, blind.memos)
    red_team = await council._run_red_team(query, profile, blind.memos, rebuttals)
    evidence = await council._run_evidence_judge(
        query,
        profile,
        blind,
        blind.memos,
        rebuttals,
        red_team,
    )

    evidence_call = next(call for call in llm.calls if call["stage"] == "EVIDENCE_JUDGE")
    assert "synthetic-doc" in evidence_call["user"]
    assert "Synthetic Source" in evidence_call["user"]
    assert "knowledge_status" in evidence_call["user"]
    assert "PRIVATE_SYNTHETIC_CHUNK" not in evidence_call["user"]
    assert evidence.knowledge_status_by_expert == blind.knowledge_status_by_expert


@pytest.mark.asyncio
async def test_red_team_and_evidence_judge_parse_failures_are_explicit():
    query = "Should we change our strategy?"
    profile = profile_problem(query)
    experts = route_experts(profile)
    llm = FakeLLM(malformed_stages={"RED_TEAM", "EVIDENCE_JUDGE"})
    council = CouncilOS(llm, retriever=FakeRetriever(), knowledge_namespace="private-test")

    blind = await council._run_blind_memos(query, experts)
    rebuttals = await council._run_rebuttals(query, profile, experts, blind.memos)
    red_team = await council._run_red_team(query, profile, blind.memos, rebuttals)
    evidence = await council._run_evidence_judge(
        query,
        profile,
        blind,
        blind.memos,
        rebuttals,
        red_team,
    )

    assert red_team.parse_error is True
    assert "red_team_parse_error" in red_team.failure_modes
    assert evidence.parse_error is True
    assert "evidence_judge_parse_error" in evidence.evidence_gaps
