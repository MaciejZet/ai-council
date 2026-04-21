"""
Debate Orchestrator
====================
Zarządza wielorundową debatą agentów z reakcjami i konsensusem
"""

import asyncio
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, AsyncGenerator
from datetime import datetime
import json

from src.agents.base import BaseAgent, AgentResponse, agent_registry
from src.agents.core_agents import Synthesizer, create_core_agents, CORE_AGENT_NAMES
from src.knowledge.retriever import query_knowledge, format_sources_for_display
from src.llm_providers import LLMProvider, calculate_cost


async def extract_debate_structure_llm(
    llm: LLMProvider,
    query: str,
    debate_summary: str,
) -> tuple[List[str], List[str], Dict[str, Any]]:
    """
    Wyodrębnia punkty zgodne, sporne i mapę rozbieżności (LLM + JSON).
    """
    import re

    prompt = f"""Przeanalizuj debatę ekspertów i zwróć WYŁĄCZNIE poprawny JSON (bez markdown):
{{
  "consensus_points": ["krótki punkt 1", "punkt 2"],
  "disagreement_points": ["kontrowersja 1", "kontrowersja 2"],
  "disagreement_map": {{
     "temat lub teza": {{"agent_a": "stanowisko", "agent_b": "inne stanowisko"}}
  }}
}}
Pytanie użytkownika: {query[:2000]}

Transkrypt debaty:
{debate_summary[:14000]}
"""
    try:
        response = await llm.generate(
            system_prompt="Jesteś analitykiem debat. Odpowiadasz wyłącznie JSON.",
            user_prompt=prompt,
            temperature=0.2,
        )
        raw = response.content.strip()
        fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
        if fence:
            raw = fence.group(1).strip()
        start, end = raw.find("{"), raw.rfind("}")
        if start == -1 or end == -1:
            return [], [], {}
        data = json.loads(raw[start : end + 1])
        cons = [str(x) for x in data.get("consensus_points", []) if x][:8]
        dis = [str(x) for x in data.get("disagreement_points", []) if x][:8]
        dmap = data.get("disagreement_map", {})
        if not isinstance(dmap, dict):
            dmap = {}
        return cons, dis, dmap
    except Exception as exc:
        print(f"Debate structure extraction error: {exc}")
        return [], [], {}


@dataclass
class DebateRound:
    """Pojedyncza runda debaty"""
    round_number: int
    round_type: str  # "initial", "reaction", "consensus"
    responses: List[AgentResponse] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "round_number": self.round_number,
            "round_type": self.round_type,
            "responses": [
                {
                    "agent_name": r.agent_name,
                    "role": r.role,
                    "content": r.content,
                    "reacting_to": getattr(r, 'reacting_to', None)
                }
                for r in self.responses
            ]
        }


@dataclass
class DebateResult:
    """Pełny wynik debaty"""
    query: str
    timestamp: str
    rounds: List[DebateRound]
    consensus_points: List[str]
    disagreement_points: List[str]
    final_recommendation: str
    total_rounds: int
    sources: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "timestamp": self.timestamp,
            "rounds": [r.to_dict() for r in self.rounds],
            "consensus_points": self.consensus_points,
            "disagreement_points": self.disagreement_points,
            "final_recommendation": self.final_recommendation,
            "total_rounds": self.total_rounds,
            "sources": self.sources
        }


class DebateOrchestrator:
    """
    Orkiestruje wielorundową debatę między agentami
    """
    
    def __init__(
        self, 
        use_knowledge_base: bool = True,
        knowledge_top_k: int = 5
    ):
        self.use_knowledge_base = use_knowledge_base
        self.knowledge_top_k = knowledge_top_k
    
    def _get_agents(self) -> List[BaseAgent]:
        """Pobiera aktywnych agentów (bez Syntezatora)"""
        agents = agent_registry.get_enabled()
        return [a for a in agents if not isinstance(a, Synthesizer)]
    
    def _get_synthesizer(self) -> Optional[Synthesizer]:
        """Pobiera Syntezatora"""
        agents = agent_registry.get_enabled()
        for a in agents:
            if isinstance(a, Synthesizer):
                return a
        return None
    
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
    
    async def run_debate_stream(
        self,
        query: str,
        max_rounds: int = 3,
        llm: Optional[LLMProvider] = None
    ) -> AsyncGenerator[str, None]:
        """
        Przeprowadza debatę ze streamingiem SSE
        
        Yields: SSE events jako JSON strings
        """
        from src.agents.core_agents import Strategist, Analyst, Practitioner, Expert, Synthesizer as SynthesizerClass
        
        # Utworz agentów z podanym LLM lub domyślnym
        if llm:
            agents = [
                Strategist(llm),
                Analyst(llm),
                Practitioner(llm),
                Expert(llm),
            ]
            synthesizer = SynthesizerClass(llm)
        else:
            agents = self._get_agents()
            synthesizer = self._get_synthesizer()
        
        # Pobierz kontekst
        context, sources = self._get_context(query)
        
        # Wyślij źródła
        yield f"data: {json.dumps({'event': 'sources', 'sources': sources})}\n\n"
        
        all_rounds: List[DebateRound] = []
        all_responses: Dict[str, AgentResponse] = {}  # agent_name -> ostatnia odpowiedź
        
        # ========== RUNDA 1: STANOWISKA POCZĄTKOWE ==========
        yield f"data: {json.dumps({'event': 'round_start', 'round': 1, 'type': 'initial', 'title': 'Stanowiska początkowe'})}\n\n"
        
        round1 = DebateRound(round_number=1, round_type="initial")
        
        for agent in agents:
            yield f"data: {json.dumps({'event': 'agent_start', 'agent': agent.name, 'emoji': agent.emoji, 'role': agent.role, 'round': 1})}\n\n"
            
            full_response = ""
            async for token in agent.analyze_stream(query, context):
                full_response += token
                yield f"data: {json.dumps({'event': 'delta', 'agent': agent.name, 'content': token})}\n\n"
            
            response = AgentResponse(
                agent_name=f"{agent.emoji} {agent.name}",
                role=agent.role,
                perspective="",
                content=full_response,
                provider_used=agent.provider.get_name()
            )
            round1.responses.append(response)
            all_responses[agent.name] = response
            
            yield f"data: {json.dumps({'event': 'agent_done', 'agent': agent.name, 'round': 1})}\n\n"
        
        all_rounds.append(round1)
        yield f"data: {json.dumps({'event': 'round_done', 'round': 1})}\n\n"
        
        # ========== RUNDA 2: REAKCJE (Agenci komentują się nawzajem) ==========
        if max_rounds >= 2:
            yield f"data: {json.dumps({'event': 'round_start', 'round': 2, 'type': 'reaction', 'title': 'Reakcje i komentarze'})}\n\n"
            
            round2 = DebateRound(round_number=2, round_type="reaction")
            
            for i, agent in enumerate(agents):
                # Każdy agent komentuje odpowiedź INNEGO agenta
                other_agent_idx = (i + 1) % len(agents)
                other_agent = agents[other_agent_idx]
                other_response = all_responses.get(other_agent.name)
                
                if not other_response:
                    continue
                
                yield f"data: {json.dumps({'event': 'agent_start', 'agent': agent.name, 'emoji': agent.emoji, 'role': agent.role, 'round': 2, 'reacting_to': other_agent.name})}\n\n"
                
                # Użyj metody react dla komentarza
                full_response = ""
                async for token in agent.react_stream(
                    query=query,
                    context=context,
                    other_response=other_response,
                    my_previous=all_responses.get(agent.name)
                ):
                    full_response += token
                    yield f"data: {json.dumps({'event': 'delta', 'agent': agent.name, 'content': token})}\n\n"
                
                response = AgentResponse(
                    agent_name=f"{agent.emoji} {agent.name}",
                    role=agent.role,
                    perspective="",
                    content=full_response,
                    provider_used=agent.provider.get_name()
                )
                # Dodaj info o tym kogo komentuje
                response.reacting_to = other_agent.name
                round2.responses.append(response)
                all_responses[agent.name] = response  # Aktualizuj
                
                yield f"data: {json.dumps({'event': 'agent_done', 'agent': agent.name, 'round': 2})}\n\n"
            
            all_rounds.append(round2)
            yield f"data: {json.dumps({'event': 'round_done', 'round': 2})}\n\n"
        
        # ========== RUNDA 3: KONSENSUS (Syntezator analizuje) ==========
        if max_rounds >= 3 and synthesizer:
            yield f"data: {json.dumps({'event': 'round_start', 'round': 3, 'type': 'consensus', 'title': 'Analiza konsensusu'})}\n\n"

            debate_context = self._build_debate_summary(all_rounds)
            structured_consensus: List[str] = []
            structured_disagreement: List[str] = []
            disagreement_map: Dict[str, Any] = {}
            if llm:
                structured_consensus, structured_disagreement, disagreement_map = await extract_debate_structure_llm(
                    llm, query, debate_context
                )
                yield f"data: {json.dumps({'event': 'debate_analysis', 'consensus_points': structured_consensus, 'disagreement_points': structured_disagreement, 'disagreement_map': disagreement_map})}\n\n"

            yield f"data: {json.dumps({'event': 'agent_start', 'agent': 'Syntezator', 'emoji': '🔮', 'role': 'Consensus Builder', 'round': 3})}\n\n"

            analysis_block = ""
            if structured_consensus or structured_disagreement:
                analysis_block = f"""
## WSTĘPNA ANALIZA STRUKTURALNA
**Zbieżności:** {json.dumps(structured_consensus, ensure_ascii=False)}
**Rozbieżności:** {json.dumps(structured_disagreement, ensure_ascii=False)}
**Mapa niezgodności:** {json.dumps(disagreement_map, ensure_ascii=False)}
"""

            consensus_prompt = f"""## ORYGINALNE PYTANIE UŻYTKOWNIKA:
{query}
{analysis_block}
## DEBATA EKSPERTÓW:
{debate_context}

## TWOJE ZADANIE:
Na podstawie powyższej debaty, przygotuj odpowiedź w następującym formacie:

---

# Rekomendacja Rady

## 1. Podsumowanie perspektyw
Krótko opisz co wniósł każdy ekspert (1-2 zdania na agenta):
- **Strateg**: [jego kluczowy wkład]
- **Analityk**: [jego kluczowy wkład]  
- **Praktyk**: [jego kluczowy wkład]
- **Ekspert**: [jego kluczowy wkład]

**Punkty zbieżne:** [w czym się zgadzają]
**Punkty rozbieżne:** [gdzie są różnice zdań]

## 2. ODPOWIEDŹ NA PYTANIE 
**NAJWAŻNIEJSZA SEKCJA - odpowiedz BEZPOŚREDNIO na pytanie użytkownika!**

Wykorzystując przemyślenia wszystkich agentów, daj KONKRETNĄ odpowiedź:
- Jeśli użytkownik prosił o strategię → napisz konkretną strategię
- Jeśli prosił o pytania → zadaj konkretne, przemyślane pytania
- Jeśli prosił o ulepszenie dokumentu → daj ulepszoną wersję
- Jeśli prosił o analizę → daj konkretne wnioski i rekomendacje
- Jeśli prosił o plan → daj szczegółowy plan działania

NIE pisz ogólników typu "powinieneś doprecyzować". Daj GOTOWĄ odpowiedź.

## 3. Następne kroki
3-5 konkretnych działań do podjęcia natychmiast.

---
Odpowiedz w formacie markdown, jasno i strukturalnie. Pamiętaj: użytkownik chce GOTOWĄ odpowiedź opartą na przemyśleniach ekspertów, nie tylko opis co eksperci powiedzieli."""

            full_response = ""
            # Użyj syntezy z kontekstem debaty
            mock_responses = list(all_responses.values())
            
            async for token in synthesizer.synthesize_stream(consensus_prompt, context, mock_responses):
                full_response += token
                yield f"data: {json.dumps({'event': 'delta', 'agent': 'Syntezator', 'content': token})}\n\n"
            
            yield f"data: {json.dumps({'event': 'agent_done', 'agent': 'Syntezator', 'round': 3})}\n\n"
            yield f"data: {json.dumps({'event': 'round_done', 'round': 3})}\n\n"
            
            # Parsuj konsensus z odpowiedzi (uproszczone)
            consensus_points, disagreement_points = self._parse_consensus(full_response)
            
            yield f"data: {json.dumps({'event': 'consensus', 'consensus_points': consensus_points, 'disagreement_points': disagreement_points})}\n\n"
        
        # ========== ZAKOŃCZENIE ==========
        yield f"data: {json.dumps({'event': 'complete', 'total_rounds': len(all_rounds), 'total_agents': len(agents)})}\n\n"
    
    def _build_debate_summary(self, rounds: List[DebateRound]) -> str:
        """Buduje podsumowanie debaty dla syntezatora"""
        parts = []
        
        for round in rounds:
            parts.append(f"### Runda {round.round_number}: {round.round_type.upper()}")
            for resp in round.responses:
                reacting_info = f" (w reakcji na {getattr(resp, 'reacting_to', '')})" if hasattr(resp, 'reacting_to') and resp.reacting_to else ""
                parts.append(f"\n**{resp.agent_name}**{reacting_info}:\n{resp.content[:500]}...")
            parts.append("")
        
        return "\n".join(parts)
    
    def _parse_consensus(self, text: str) -> tuple[List[str], List[str]]:
        """
        Parsuje punkty konsensusu i sporne z odpowiedzi syntezatora.
        Uproszczona wersja - wyciąga bullet points.
        """
        consensus = []
        disagreements = []
        
        lines = text.split('\n')
        current_section = None
        
        for line in lines:
            line_lower = line.lower()

            if (
                "konsensus" in line_lower
                or "zgadzaj" in line_lower
                or "zbieżn" in line_lower
                or "✅" in line
            ):
                current_section = "consensus"
            elif (
                "sporn" in line_lower
                or "różnic" in line_lower
                or "rozbieżn" in line_lower
                or "niezgodn" in line_lower
                or "⚠️" in line
            ):
                current_section = "disagreements"
            elif 'rekomendacja' in line_lower or '🎯' in line:
                current_section = None
            elif line.strip().startswith(('-', '•', '*', '1.', '2.', '3.', '4.', '5.')):
                clean_line = line.strip().lstrip('-•*0123456789. ')
                if clean_line and len(clean_line) > 5:
                    if current_section == 'consensus':
                        consensus.append(clean_line[:100])
                    elif current_section == 'disagreements':
                        disagreements.append(clean_line[:100])
        
        return consensus[:5], disagreements[:4]
