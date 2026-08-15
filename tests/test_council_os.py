import importlib

import pytest

from src.council.business_routing import profile_problem, route_experts
from src.knowledge.private_models import KnowledgeRetrievalResult
from src.llm_providers import LLMResponse

council_os_module = importlib.import_module("src.council.council_os")
CouncilOS = council_os_module.CouncilOS


class FakeLLM:
    def __init__(self):
        self.calls = []

    async def generate(self, system_prompt, user_prompt, temperature=0.7, max_tokens=None):
        self.calls.append((system_prompt, user_prompt))
        expert_id = system_prompt.split("[EXPERT_ID:", 1)[1].split("]", 1)[0]
        return LLMResponse(
            content=(
                '{"expert_id":"%s","vote":"TEST",'
                '"recommendation":"PEER_MEMO_SENTINEL_%s",'
                '"confidence":0.7,"claims":[],"assumptions":[],"risks":[],'
                '"what_changes_my_mind":[]}' % (expert_id, expert_id)
            ),
            model="fake",
        )


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

    blind_prompts = [
        user_prompt
        for system_prompt, user_prompt in llm.calls
        if "[STAGE:BLIND]" in system_prompt
    ]
    assert len(blind_prompts) == len(experts)
    assert all("PRIVATE_SYNTHETIC_CHUNK" in prompt for prompt in blind_prompts)
    assert all("PEER_MEMO_SENTINEL" not in prompt for prompt in blind_prompts)
    assert all(memo.expert_id in {expert.id for expert in experts} for memo in blind.memos)

    assert blind.source_inventory
    assert all("text" not in source for sources in blind.source_inventory.values() for source in sources)


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
