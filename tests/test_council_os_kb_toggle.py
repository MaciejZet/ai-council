import json

import pytest

from src.council.business_routing import profile_problem, route_experts
from src.council.council_os import CouncilOS
from src.knowledge.private_models import KnowledgeRetrievalResult
from src.llm_providers import LLMResponse


class BlindFakeLLM:
    async def generate(self, system_prompt, user_prompt, temperature=0.7, max_tokens=None):
        expert_id = system_prompt.split("[EXPERT_ID:", 1)[1].split("]", 1)[0]
        return LLMResponse(
            content=json.dumps(
                {
                    "expert_id": expert_id,
                    "vote": "TEST",
                    "recommendation": "synthetic",
                    "confidence": 0.5,
                    "claims": [],
                    "assumptions": [],
                    "risks": [],
                    "what_changes_my_mind": [],
                }
            ),
            model="fake",
        )


class CountingRetriever:
    def __init__(self):
        self.calls = 0

    def __call__(self, query, **kwargs):
        self.calls += 1
        return KnowledgeRetrievalResult(status="ok", chunks=[])


@pytest.mark.asyncio
async def test_disabled_knowledge_base_skips_retriever_and_marks_memos_disabled():
    query = "Should we change our strategy?"
    experts = route_experts(profile_problem(query))
    retriever = CountingRetriever()
    council = CouncilOS(
        BlindFakeLLM(),
        retriever=retriever,
        use_knowledge_base=False,
    )

    blind = await council._run_blind_memos(query, experts)

    assert retriever.calls == 0
    assert set(blind.knowledge_status_by_expert.values()) == {"disabled"}
    assert {memo.knowledge_status for memo in blind.memos} == {"disabled"}
