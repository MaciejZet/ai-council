"""
Tests for Council orchestration (explicit agent lists, synthesizer split).
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.core_agents import Strategist, Synthesizer
from src.council import orchestrator as orchestrator_module
from src.council.orchestrator import Council
from src.knowledge.private_models import KnowledgeRetrievalResult
from src.llm_providers import LLMResponse


@pytest.mark.asyncio
async def test_deliberate_explicit_list_extracts_synthesizer():
    """Synthesizer in the passed list must not be gathered with analyze(); synthesis runs after."""
    mock_llm = MagicMock()
    mock_llm.get_name.return_value = "Test (m)"

    async def fake_generate(*_args, **_kwargs):
        return LLMResponse(
            content="ok",
            prompt_tokens=1,
            completion_tokens=1,
            total_tokens=2,
            model="m",
        )

    mock_llm.generate = AsyncMock(side_effect=fake_generate)

    council = Council(use_knowledge_base=False)
    agents = [Strategist(mock_llm), Synthesizer(mock_llm)]
    result = await council.deliberate("test query", agents=agents, include_synthesis=True)

    assert len(result.agent_responses) == 1
    assert result.synthesis is not None
    assert result.synthesis.content == "ok"
    assert result.knowledge_status == "disabled"
    assert result.knowledge_error_code is None
    assert mock_llm.generate.await_count >= 2


def test_get_context_distinguishes_unavailable_private_knowledge(monkeypatch):
    monkeypatch.setattr(
        orchestrator_module,
        "query_knowledge_result",
        lambda *args, **kwargs: KnowledgeRetrievalResult(
            status="unavailable",
            error_code="pinecone_query_failed",
        ),
    )
    council = Council(use_knowledge_base=True)
    context, sources, status, error_code = council._get_context("synthetic query")
    assert context == []
    assert sources == []
    assert status == "unavailable"
    assert error_code == "pinecone_query_failed"
