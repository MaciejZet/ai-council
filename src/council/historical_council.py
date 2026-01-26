"""
Historical Council Orchestrator
================================
Orkiestruje naradę postaci historycznych (Rada Mędrców)
"""

import asyncio
import json
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, AsyncGenerator
from datetime import datetime

from src.agents.base import AgentResponse
from src.agents.historical_agents import (
    HistoricalAgent, 
    HistoricalSynthesizer,
    create_historical_council,
    HISTORICAL_GROUPS,
    HISTORICAL_AGENTS
)
from src.knowledge.retriever import query_knowledge, format_sources_for_display
from src.llm_providers import LLMProvider


@dataclass
class HistoricalCouncilResult:
    """Wynik narady Rady Mędrców"""
    query: str
    timestamp: str
    agent_responses: List[AgentResponse]
    synthesis: Optional[AgentResponse]
    sources: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "timestamp": self.timestamp,
            "agent_responses": [
                {
                    "agent_name": r.agent_name,
                    "role": r.role,
                    "content": r.content
                }
                for r in self.agent_responses
            ],
            "synthesis": {
                "agent_name": self.synthesis.agent_name,
                "content": self.synthesis.content
            } if self.synthesis else None,
            "sources": self.sources
        }


class HistoricalCouncil:
    """
    Orkiestrator Rady Mędrców - zarządza naradą postaci historycznych
    """
    
    def __init__(
        self,
        use_knowledge_base: bool = True,
        knowledge_top_k: int = 5
    ):
        self.use_knowledge_base = use_knowledge_base
        self.knowledge_top_k = knowledge_top_k
    
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
            print(f"⚠️ Błąd pobierania kontekstu: {e}")
            return [], []
    
    async def deliberate(
        self,
        query: str,
        agent_ids: List[str] = None,
        llm: Optional[LLMProvider] = None
    ) -> HistoricalCouncilResult:
        """
        Przeprowadza naradę Rady Mędrców (synchronicznie)
        
        Args:
            query: Pytanie użytkownika
            agent_ids: Lista ID agentów do użycia (None = wszyscy)
            llm: Provider LLM
        
        Returns:
            HistoricalCouncilResult z odpowiedziami
        """
        # Utwórz agentów
        agents, synthesizer = create_historical_council(agent_ids, llm)
        
        # Pobierz kontekst
        context, sources = self._get_context(query)
        
        # Zbierz odpowiedzi od wszystkich agentów
        agent_responses: List[AgentResponse] = []
        
        for agent in agents:
            response = await agent.analyze(query, context)
            agent_responses.append(response)
        
        # Synteza
        synthesis = await synthesizer.synthesize(query, context, agent_responses)
        
        return HistoricalCouncilResult(
            query=query,
            timestamp=datetime.now().isoformat(),
            agent_responses=agent_responses,
            synthesis=synthesis,
            sources=sources
        )
    
    async def deliberate_stream(
        self,
        query: str,
        agent_ids: List[str] = None,
        llm: Optional[LLMProvider] = None,
        include_synthesis: bool = True
    ) -> AsyncGenerator[str, None]:
        """
        Przeprowadza naradę ze streamingiem SSE
        
        Yields: SSE events jako JSON strings
        """
        # Utwórz agentów
        agents, synthesizer = create_historical_council(agent_ids, llm)
        
        # Pobierz kontekst
        context, sources = self._get_context(query)
        
        # Wyślij źródła
        yield f"data: {json.dumps({'event': 'sources', 'sources': sources})}\n\n"
        
        # Wyślij info o rozpoczęciu
        agent_info = [
            {"id": aid, "name": a.name, "emoji": a.emoji, "role": a.role}
            for aid, a in zip(agent_ids or HISTORICAL_AGENTS.keys(), agents)
        ]
        yield f"data: {json.dumps({'event': 'council_start', 'agents': agent_info, 'title': 'Rada Mędrców'})}\n\n"
        
        all_responses: List[AgentResponse] = []
        
        # ========== RUNDA 1: GŁOSY MĘDRCÓW ==========
        yield f"data: {json.dumps({'event': 'round_start', 'round': 1, 'type': 'voices', 'title': 'Głosy Mędrców'})}\n\n"
        
        for agent in agents:
            yield f"data: {json.dumps({'event': 'agent_start', 'agent': agent.name, 'emoji': agent.emoji, 'role': agent.role, 'round': 1})}\n\n"
            
            full_response = ""
            async for token in agent.analyze_stream(query, context):
                full_response += token
                yield f"data: {json.dumps({'event': 'delta', 'agent': agent.name, 'content': token})}\n\n"
            
            response = AgentResponse(
                agent_name=f"{agent.emoji} {agent.name}",
                role=agent.role,
                perspective=agent.config.personality,
                content=full_response,
                provider_used=agent.provider.get_name()
            )
            all_responses.append(response)
            
            yield f"data: {json.dumps({'event': 'agent_done', 'agent': agent.name, 'round': 1})}\n\n"
        
        yield f"data: {json.dumps({'event': 'round_done', 'round': 1})}\n\n"
        
        # ========== RUNDA 2: SYNTEZA MĄDROŚCI ==========
        if include_synthesis:
            yield f"data: {json.dumps({'event': 'round_start', 'round': 2, 'type': 'synthesis', 'title': 'Mądrość Rady'})}\n\n"
            
            yield f"data: {json.dumps({'event': 'agent_start', 'agent': 'Rada Mędrców', 'emoji': '🔮', 'role': 'Syntezator', 'round': 2})}\n\n"
            
            full_synthesis = ""
            async for token in synthesizer.synthesize_stream(query, context, all_responses):
                full_synthesis += token
                yield f"data: {json.dumps({'event': 'delta', 'agent': 'Rada Mędrców', 'content': token})}\n\n"
            
            yield f"data: {json.dumps({'event': 'agent_done', 'agent': 'Rada Mędrców', 'round': 2})}\n\n"
            yield f"data: {json.dumps({'event': 'round_done', 'round': 2})}\n\n"
        
        # ========== ZAKOŃCZENIE ==========
        yield f"data: {json.dumps({'event': 'complete', 'total_agents': len(agents)})}\n\n"
    
    async def debate_stream(
        self,
        query: str,
        agent_ids: List[str] = None,
        llm: Optional[LLMProvider] = None,
        max_rounds: int = 3
    ) -> AsyncGenerator[str, None]:
        """
        Przeprowadza DEBATĘ ze streamingiem SSE - postacie reagują na siebie nawzajem
        
        Rundy:
        1. Stanowiska początkowe - każda postać odpowiada na pytanie
        2. Reakcje - każda postać komentuje odpowiedź innej
        3. Synteza - Rada łączy wszystkie głosy
        
        Yields: SSE events jako JSON strings
        """
        # Utwórz agentów
        agents, synthesizer = create_historical_council(agent_ids, llm)
        
        # Pobierz kontekst
        context, sources = self._get_context(query)
        
        # Wyślij źródła
        yield f"data: {json.dumps({'event': 'sources', 'sources': sources})}\n\n"
        
        # Info o rozpoczęciu debaty
        agent_info = [
            {"id": aid, "name": a.name, "emoji": a.emoji, "role": a.role}
            for aid, a in zip(agent_ids or HISTORICAL_AGENTS.keys(), agents)
        ]
        yield f"data: {json.dumps({'event': 'debate_start', 'agents': agent_info, 'title': 'Debata Mędrców', 'max_rounds': max_rounds})}\n\n"
        
        all_responses: Dict[str, AgentResponse] = {}
        
        # ========== RUNDA 1: STANOWISKA POCZĄTKOWE ==========
        yield f"data: {json.dumps({'event': 'round_start', 'round': 1, 'type': 'initial', 'title': 'Stanowiska początkowe'})}\n\n"
        
        for agent in agents:
            yield f"data: {json.dumps({'event': 'agent_start', 'agent': agent.name, 'emoji': agent.emoji, 'role': agent.role, 'round': 1})}\n\n"
            
            full_response = ""
            async for token in agent.analyze_stream(query, context):
                full_response += token
                yield f"data: {json.dumps({'event': 'delta', 'agent': agent.name, 'content': token})}\n\n"
            
            response = AgentResponse(
                agent_name=f"{agent.emoji} {agent.name}",
                role=agent.role,
                perspective=agent.config.personality,
                content=full_response,
                provider_used=agent.provider.get_name()
            )
            all_responses[agent.name] = response
            
            yield f"data: {json.dumps({'event': 'agent_done', 'agent': agent.name, 'round': 1})}\n\n"
        
        yield f"data: {json.dumps({'event': 'round_done', 'round': 1})}\n\n"
        
        # ========== RUNDA 2: REAKCJE (każdy komentuje innego) ==========
        if max_rounds >= 2 and len(agents) >= 2:
            yield f"data: {json.dumps({'event': 'round_start', 'round': 2, 'type': 'reaction', 'title': 'Reakcje i komentarze'})}\n\n"
            
            for i, agent in enumerate(agents):
                # Każdy agent komentuje odpowiedź NASTĘPNEGO agenta (cyklicznie)
                other_idx = (i + 1) % len(agents)
                other_agent = agents[other_idx]
                other_response = all_responses.get(other_agent.name)
                
                if not other_response:
                    continue
                
                yield f"data: {json.dumps({'event': 'agent_start', 'agent': agent.name, 'emoji': agent.emoji, 'role': agent.role, 'round': 2, 'reacting_to': other_agent.name})}\n\n"
                
                # Zbuduj prompt reakcji
                full_response = ""
                async for token in agent.react_stream(
                    query=query,
                    context=context,
                    other_response=other_response,
                    my_previous=all_responses.get(agent.name)
                ):
                    full_response += token
                    yield f"data: {json.dumps({'event': 'delta', 'agent': agent.name, 'content': token})}\n\n"
                
                # Aktualizuj odpowiedź
                response = AgentResponse(
                    agent_name=f"{agent.emoji} {agent.name}",
                    role=agent.role,
                    perspective=agent.config.personality,
                    content=full_response,
                    provider_used=agent.provider.get_name()
                )
                response.reacting_to = other_agent.name
                all_responses[agent.name] = response
                
                yield f"data: {json.dumps({'event': 'agent_done', 'agent': agent.name, 'round': 2})}\n\n"
            
            yield f"data: {json.dumps({'event': 'round_done', 'round': 2})}\n\n"
        
        # ========== RUNDA 3: SYNTEZA MĄDROŚCI ==========
        if max_rounds >= 3:
            yield f"data: {json.dumps({'event': 'round_start', 'round': 3, 'type': 'synthesis', 'title': 'Synteza debaty'})}\n\n"
            
            yield f"data: {json.dumps({'event': 'agent_start', 'agent': 'Rada Mędrców', 'emoji': '🔮', 'role': 'Syntezator', 'round': 3})}\n\n"
            
            # Przygotuj kontekst debaty dla syntezatora
            debate_summary = self._build_debate_summary(list(all_responses.values()))
            
            full_synthesis = ""
            async for token in synthesizer.synthesize_stream(
                f"{query}\n\n## PRZEBIEG DEBATY:\n{debate_summary}", 
                context, 
                list(all_responses.values())
            ):
                full_synthesis += token
                yield f"data: {json.dumps({'event': 'delta', 'agent': 'Rada Mędrców', 'content': token})}\n\n"
            
            yield f"data: {json.dumps({'event': 'agent_done', 'agent': 'Rada Mędrców', 'round': 3})}\n\n"
            yield f"data: {json.dumps({'event': 'round_done', 'round': 3})}\n\n"
        
        # ========== ZAKOŃCZENIE ==========
        yield f"data: {json.dumps({'event': 'complete', 'total_agents': len(agents), 'total_rounds': max_rounds})}\n\n"
    
    def _build_debate_summary(self, responses: List[AgentResponse]) -> str:
        """Buduje podsumowanie debaty dla syntezatora"""
        parts = []
        for resp in responses:
            reacting_info = f" (reagując na {getattr(resp, 'reacting_to', '')})" if hasattr(resp, 'reacting_to') and resp.reacting_to else ""
            parts.append(f"**{resp.agent_name}**{reacting_info}:\n{resp.content[:600]}...")
        return "\n\n---\n\n".join(parts)


def format_historical_council_markdown(result: HistoricalCouncilResult) -> str:
    """Formatuje wynik narady jako Markdown do eksportu"""
    
    lines = [
        "# Rada Mędrców - Odpowiedź",
        "",
        f"**Pytanie:** {result.query}",
        f"**Data:** {result.timestamp}",
        "",
        "---",
        "",
    ]
    
    # Synteza na początku
    if result.synthesis:
        lines.extend([
            "## 🔮 Mądrość Rady",
            "",
            result.synthesis.content,
            "",
            "---",
            "",
        ])
    
    # Głosy poszczególnych mędrców
    lines.append("## Głosy Mędrców")
    lines.append("")
    
    for response in result.agent_responses:
        lines.extend([
            f"### {response.agent_name}",
            f"*{response.role}*",
            "",
            response.content,
            "",
            "---",
            "",
        ])
    
    # Źródła
    if result.sources:
        lines.append("## Źródła")
        lines.append("")
        for source in result.sources:
            lines.append(f"- {source.get('title', 'Źródło')}")
        lines.append("")
    
    return "\n".join(lines)
