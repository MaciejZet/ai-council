"""
Council Orchestrator
=====================
Koordynuje naradę agentów, zbiera kontekst, wywołuje agentów równolegle i syntetyzuje wyniki.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.agents.base import AgentResponse, BaseAgent, agent_registry
from src.agents.core_agents import Synthesizer, create_core_agents
from src.council.quality import (
    critic_review,
    llm_agent_weights,
    preset_instructions,
    synthesize_with_critic_and_weights,
)
from src.knowledge.retriever import format_sources_for_display, query_knowledge_result
from src.llm_providers import LLMProvider, calculate_cost
from src.utils.logger import setup_logger

_orchestrator_logger = setup_logger("ai_council.council")


@dataclass
class UsageStats:
    """Statystyki użycia tokenów i kosztów."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0

    def add(self, prompt: int, completion: int, model: str) -> None:
        """Dodaje tokeny i oblicza koszt."""
        self.prompt_tokens += prompt
        self.completion_tokens += completion
        self.total_tokens += prompt + completion
        self.total_cost += calculate_cost(model, prompt, completion)

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "total_cost": round(self.total_cost, 6),
        }


@dataclass
class CouncilDeliberation:
    """Pełna odpowiedź rady z danymi o tokenach i stanie bazy wiedzy."""

    query: str
    timestamp: str
    context_used: list[str]
    sources: list[dict[str, Any]]
    agent_responses: list[AgentResponse]
    synthesis: AgentResponse | None
    total_agents: int
    providers_used: list[str]
    usage: UsageStats = field(default_factory=UsageStats)
    behavior_preset: str = "default"
    critic_notes: str | None = None
    agent_weights: list[dict[str, Any]] | None = None
    knowledge_status: str = "disabled"
    knowledge_error_code: str | None = None


class Council:
    """Orkiestruje naradę agentów."""

    def __init__(
        self,
        use_knowledge_base: bool = True,
        knowledge_top_k: int = 5,
        knowledge_namespace: str | None = None,
    ):
        self.use_knowledge_base = use_knowledge_base
        self.knowledge_top_k = knowledge_top_k
        self.knowledge_namespace = knowledge_namespace or os.getenv("PINECONE_PRIVATE_NAMESPACE") or None
        self._synthesizer: Synthesizer | None = None

    def _get_agents(self, include_specialists: bool = True) -> list[BaseAgent]:
        """Pobiera listę aktywnych agentów bez Syntezatora."""
        agents = agent_registry.get_enabled()
        non_synthesizers: list[BaseAgent] = []
        for agent in agents:
            if isinstance(agent, Synthesizer):
                self._synthesizer = agent
            else:
                non_synthesizers.append(agent)
        return non_synthesizers

    def _get_context(
        self,
        query: str,
        *,
        hybrid: bool = False,
    ) -> tuple[list[str], list[dict[str, Any]], str, str | None]:
        """Pobiera kontekst i jawny status dostępności bazy wiedzy."""
        if not self.use_knowledge_base:
            return [], [], "disabled", None

        try:
            result = query_knowledge_result(
                query,
                top_k=self.knowledge_top_k,
                hybrid=hybrid,
                namespace=self.knowledge_namespace,
            )
            texts = [chunk["text"] for chunk in result.chunks]
            sources = format_sources_for_display(result.chunks)
            return texts, sources, result.status, result.error_code
        except Exception as exc:
            _orchestrator_logger.warning(
                "Knowledge retrieval failed error_type=%s",
                type(exc).__name__,
            )
            return [], [], "unavailable", "retrieval_exception"

    async def deliberate(
        self,
        query: str,
        agents: list[BaseAgent] | None = None,
        include_synthesis: bool = True,
        llm: LLMProvider | None = None,
        behavior_preset: str = "default",
        enable_critic: bool = False,
        enable_weighted_voting: bool = False,
        hybrid_search: bool = False,
    ) -> CouncilDeliberation:
        """Przeprowadza naradę rady z pełnym śledzeniem tokenów."""
        usage = UsageStats()
        self._synthesizer = None

        if agents is not None:
            working: list[BaseAgent] = []
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

        preset = (behavior_preset or "default").strip().lower()
        effective_query = query + preset_instructions(preset)

        context, sources, knowledge_status, knowledge_error_code = self._get_context(
            query,
            hybrid=hybrid_search,
        )

        if preset == "kb_only" and self.use_knowledge_base and not context:
            synth = None
            if knowledge_status == "unavailable":
                kb_message = (
                    "Prywatna baza wiedzy jest obecnie niedostępna; "
                    "źródła nie zostały zweryfikowane."
                )
            else:
                kb_message = (
                    "W bazie wiedzy nie znaleziono fragmentów pasujących do tego pytania. "
                    "Dodaj dokumenty (import) lub wyłącz preset „tylko fakty z KB”."
                )

            if include_synthesis and self._synthesizer:
                synth = AgentResponse(
                    agent_name=f"{self._synthesizer.emoji} {self._synthesizer.name}",
                    role=self._synthesizer.role,
                    perspective="",
                    content=kb_message,
                    provider_used=self._synthesizer.provider.get_name(),
                    prompt_tokens=0,
                    completion_tokens=0,
                    total_tokens=0,
                    model=getattr(self._synthesizer.provider, "model", "") or "",
                )
            return CouncilDeliberation(
                query=query,
                timestamp=datetime.now().isoformat(),
                context_used=context,
                sources=sources,
                agent_responses=[],
                synthesis=synth,
                total_agents=1 if synth else 0,
                providers_used=[synth.provider_used] if synth else [],
                usage=usage,
                behavior_preset=preset,
                critic_notes=None,
                agent_weights=None,
                knowledge_status=knowledge_status,
                knowledge_error_code=knowledge_error_code,
            )

        tasks = [agent.analyze(effective_query, context) for agent in agents]
        responses: list[AgentResponse] = await asyncio.gather(*tasks)

        for response in responses:
            usage.add(response.prompt_tokens, response.completion_tokens, response.model)

        synthesis = None
        critic_notes: str | None = None
        weights_payload: list[dict[str, Any]] | None = None
        model_for_extra = responses[0].model if responses else "gpt-4o"

        if include_synthesis and self._synthesizer:
            synth_llm = llm or self._synthesizer.provider
            use_quality = enable_critic or enable_weighted_voting
            if use_quality:
                if enable_critic:
                    critic_notes, prompt_tokens, completion_tokens = await critic_review(
                        synth_llm,
                        query,
                        context,
                        responses,
                    )
                    usage.add(prompt_tokens, completion_tokens, model_for_extra)

                weights_list: list[float] | None = None
                if enable_weighted_voting:
                    weights_list, prompt_tokens, completion_tokens = await llm_agent_weights(
                        synth_llm,
                        query,
                        responses,
                    )
                    usage.add(prompt_tokens, completion_tokens, model_for_extra)
                    weights_payload = [
                        {"agent": responses[index].agent_name, "weight": float(weights_list[index])}
                        for index in range(len(responses))
                    ]

                synthesis = await synthesize_with_critic_and_weights(
                    self._synthesizer,
                    effective_query,
                    context,
                    responses,
                    critic_text=critic_notes,
                    weights=weights_list,
                    preset=preset,
                )
                usage.add(
                    synthesis.prompt_tokens,
                    synthesis.completion_tokens,
                    synthesis.model,
                )
            else:
                synthesis = await self._synthesizer.synthesize(
                    effective_query,
                    context,
                    responses,
                )
                usage.add(
                    synthesis.prompt_tokens,
                    synthesis.completion_tokens,
                    synthesis.model,
                )

        providers = list({response.provider_used for response in responses})
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
            usage=usage,
            behavior_preset=preset,
            critic_notes=critic_notes,
            agent_weights=weights_payload,
            knowledge_status=knowledge_status,
            knowledge_error_code=knowledge_error_code,
        )

    async def quick_deliberate(self, query: str) -> str:
        """Szybka narada zwracająca tylko syntezę jako tekst."""
        result = await self.deliberate(query)
        if result.synthesis:
            return result.synthesis.content
        return "\n\n---\n\n".join(
            f"**{response.agent_name}:**\n{response.content}" for response in result.agent_responses
        )


def format_deliberation_markdown(deliberation: CouncilDeliberation) -> str:
    """Formatuje deliberację jako markdown z danymi o tokenach."""
    parts = [
        "# 🏛️ Narada Rady AI",
        f"**Zapytanie:** {deliberation.query}",
        f"**Czas:** {deliberation.timestamp}",
        f"**Agenci:** {deliberation.total_agents}",
        f"**Providery:** {', '.join(deliberation.providers_used)}",
        f"**Tokeny:** {deliberation.usage.total_tokens:,} "
        f"(koszt: ${deliberation.usage.total_cost:.4f})",
        "",
        "---",
        "",
    ]

    if deliberation.knowledge_status == "unavailable":
        parts.append(
            "⚠️ Baza wiedzy była niedostępna podczas tej narady; "
            "odpowiedź nie powinna być traktowana jako zweryfikowana względem prywatnych źródeł."
        )
        parts.append("")

    if deliberation.context_used:
        parts.append("## 📚 Kontekst z bazy wiedzy")
        parts.append(f"Znaleziono {len(deliberation.context_used)} relevantnych fragmentów.")
        parts.append("")

    parts.append("## 👥 Perspektywy agentów")
    parts.append("")

    for response in deliberation.agent_responses:
        parts.append(f"### {response.agent_name}")
        parts.append(
            f"*{response.role} • {response.provider_used} • {response.total_tokens} tokenów*"
        )
        parts.append("")
        parts.append(response.content)
        parts.append("")
        parts.append("---")
        parts.append("")

    if deliberation.synthesis:
        parts.append("## 🔮 Końcowa synteza")
        parts.append("")
        parts.append(deliberation.synthesis.content)
    return "\n".join(parts)


_council_instance: Council | None = None


def get_council(use_knowledge_base: bool = True) -> Council:
    """Zwraca globalną instancję Council."""
    global _council_instance
    if _council_instance is None:
        _council_instance = Council(use_knowledge_base=use_knowledge_base)
    return _council_instance
