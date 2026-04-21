"""
Fast Mode - Szybkie odpowiedzi bez pełnej rady
================================================
Dla prostych zapytań - tylko 1 agent, bez syntezy
Czas: 2-3 sekundy zamiast 15-25 sekund
"""

from src.agents.core_agents import Strategist
from src.llm_providers import LLMProvider
from src.agents.base import AgentResponse

async def fast_response(query: str, provider: LLMProvider, context: list = None) -> AgentResponse:
    """
    Szybka odpowiedź - tylko Strategist

    Args:
        query: Pytanie użytkownika
        provider: Provider LLM
        context: Opcjonalny kontekst

    Returns:
        AgentResponse z odpowiedzią
    """
    strategist = Strategist(provider)
    response = await strategist.analyze(query, context or [])
    return response
