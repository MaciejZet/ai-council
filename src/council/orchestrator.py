"""
Council Orchestrator
=====================
Koordynuje naradę agentów - zbiera kontekst, wywołuje agentów równolegle, syntetyzuje wyniki
Z pełnym śledzeniem tokenów i kosztów
"""

import asyncio
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime

from src.agents.base import BaseAgent, AgentResponse, agent_registry
from src.agents.core_agents import Synthesizer, create_core_agents, CORE_AGENT_NAMES
from src.knowledge.retriever import query_knowledge, format_context_for_agent, format_sources_for_display
from src.llm_providers import calculate_cost
from src.utils.logger import setup_logger

_orchestrator_logger = setup_logger("ai_council.council")


@dataclass
class UsageStats:
    """Statystyki użycia tokenów i kosztów"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    
    def add(self, prompt: int, completion: int, model: str):
        """Dodaje tokeny i oblicza koszt"""
        self.prompt_tokens += prompt
        self.completion_tokens += completion
        self.total_tokens += prompt + completion
        self.total_cost += calculate_cost(model, prompt, completion)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "total_cost": round(self.total_cost, 6)
        }


@dataclass
class CouncilDeliberation:
    """Pełna odpowiedź rady z danymi o tokenach"""
    query: str
    timestamp: str
    context_used: List[str]
    sources: List[Dict[str, Any]]
    agent_responses: List[AgentResponse]
    synthesis: Optional[AgentResponse]
    total_agents: int
    providers_used: List[str]
    # Token usage
    usage: UsageStats = field(default_factory=UsageStats)


class Council:
    """
    Orkiestruje naradę agentów
    """
    
    def __init__(self, use_knowledge_base: bool = True, knowledge_top_k: int = 5):
        self.use_knowledge_base = use_knowledge_base
        self.knowledge_top_k = knowledge_top_k
        self._synthesizer: Optional[Synthesizer] = None
    
    def _get_agents(self, include_specialists: bool = True) -> List[BaseAgent]:
        """Pobiera listę aktywnych agentów (bez Syntezatora)"""
        agents = agent_registry.get_enabled()
        
        non_synthesizers = []
        for agent in agents:
            if isinstance(agent, Synthesizer):
                self._synthesizer = agent
            else:
                non_synthesizers.append(agent)
        
        return non_synthesizers
    
    def _get_context(self, query: str) -> tuple[List[str], List[Dict[str, Any]]]:
        """Pobiera kontekst z bazy wiedzy"""
        if not self.use_knowledge_base:
            return [], []
        
        try:
            chunks = query_knowledge(query, top_k=self.knowledge_top_k)
            texts = [chunk["text"] for chunk in chunks]
            sources = format_sources_for_display(chunks)
            return texts, sources
        except Exception as e:
            _orchestrator_logger.warning("Błąd pobierania kontekstu z bazy wiedzy: %s", e)
            return [], []
    
    async def deliberate(
        self,
        query: str,
        agents: Optional[List[BaseAgent]] = None,
        include_synthesis: bool = True
    ) -> CouncilDeliberation:
        """
        Przeprowadza naradę rady z pełnym śledzeniem tokenów
        """
        # Inicjalizuj licznik użycia
        usage = UsageStats()
        self._synthesizer = None

        # Pobierz agentów: jawna lista (bez rejestru) lub z rejestru
        if agents is not None:
            working: List[BaseAgent] = []
            for agent in agents:
                if isinstance(agent, Synthesizer):
                    self._synthesizer = agent
                else:
                    working.append(agent)
            agents = working
        else:
            agents = self._get_agents()

        if not agents:
            create_core_agents()
            agents = self._get_agents()
        
        # Pobierz kontekst z bazy wiedzy
        context, sources = self._get_context(query)
        
        # Wywołaj agentów równolegle
        tasks = [agent.analyze(query, context) for agent in agents]
        responses: List[AgentResponse] = await asyncio.gather(*tasks)
        
        # Zbierz tokeny z odpowiedzi agentów
        for response in responses:
            usage.add(
                response.prompt_tokens,
                response.completion_tokens,
                response.model
            )
        
        # Synteza końcowa
        synthesis = None
        if include_synthesis and self._synthesizer:
            synthesis = await self._synthesizer.synthesize(query, context, responses)
            # Dodaj tokeny syntezy
            usage.add(
                synthesis.prompt_tokens,
                synthesis.completion_tokens,
                synthesis.model
            )
        
        # Zbierz użytych providerów
        providers = list(set(r.provider_used for r in responses))
        if synthesis:
            providers.append(synthesis.provider_used)
        
        return CouncilDeliberation(
            query=query,
            timestamp=datetime.now().isoformat(),
            context_used=context,
            sources=sources,
            agent_responses=responses,
            synthesis=synthesis,
            total_agents=len(responses) + (1 if synthesis else 0),
            providers_used=list(set(providers)),
            usage=usage
        )
    
    async def quick_deliberate(self, query: str) -> str:
        """Szybka narada - zwraca tylko syntezę jako tekst"""
        result = await self.deliberate(query)
        
        if result.synthesis:
            return result.synthesis.content
        
        return "\n\n---\n\n".join(
            f"**{r.agent_name}:**\n{r.content}"
            for r in result.agent_responses
        )


def format_deliberation_markdown(deliberation: CouncilDeliberation) -> str:
    """Formatuje deliberację jako markdown z danymi o tokenach"""
    parts = [
        f"# 🏛️ Narada Rady AI",
        f"**Zapytanie:** {deliberation.query}",
        f"**Czas:** {deliberation.timestamp}",
        f"**Agenci:** {deliberation.total_agents}",
        f"**Providery:** {', '.join(deliberation.providers_used)}",
        f"**Tokeny:** {deliberation.usage.total_tokens:,} (koszt: ${deliberation.usage.total_cost:.4f})",
        "",
        "---",
        ""
    ]
    
    # Kontekst
    if deliberation.context_used:
        parts.append("## 📚 Kontekst z bazy wiedzy")
        parts.append(f"Znaleziono {len(deliberation.context_used)} relevantnych fragmentów.")
        parts.append("")
    
    # Odpowiedzi
    parts.append("## 👥 Perspektywy agentów")
    parts.append("")
    
    for response in deliberation.agent_responses:
        parts.append(f"### {response.agent_name}")
        parts.append(f"*{response.role} • {response.provider_used} • {response.total_tokens} tokenów*")
        parts.append("")
        parts.append(response.content)
        parts.append("")
        parts.append("---")
        parts.append("")
    
    # Synteza
    if deliberation.synthesis:
        parts.append("## 🔮 Końcowa synteza")
        parts.append("")
        parts.append(deliberation.synthesis.content)
    
    return "\n".join(parts)


# Singleton
_council_instance: Optional[Council] = None


def get_council(use_knowledge_base: bool = True) -> Council:
    """Zwraca globalną instancję Council"""
    global _council_instance
    if _council_instance is None:
        _council_instance = Council(use_knowledge_base=use_knowledge_base)
    return _council_instance
