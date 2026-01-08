"""
Council Modes - Różne tryby narady
===================================
Deep Dive, Speed Round, Devil's Advocate, SWOT, Red Team
"""

import json
from typing import List, Optional, Dict, Any, AsyncGenerator
from abc import ABC, abstractmethod

from src.agents.base import AgentConfig, AgentResponse
from src.agents.core_agents import Strategist, Analyst, Practitioner, Expert, Synthesizer
from src.llm_providers import LLMProvider, OpenAIProvider
from src.knowledge.retriever import query_knowledge, format_sources_for_display


class CouncilMode(ABC):
    """Bazowa klasa dla trybów narady"""
    
    name: str = "base"
    emoji: str = "🏛️"
    description: str = ""
    
    def __init__(self, use_knowledge_base: bool = True):
        self.use_knowledge_base = use_knowledge_base
    
    @abstractmethod
    async def run_stream(
        self, 
        query: str, 
        llm: Optional[LLMProvider] = None
    ) -> AsyncGenerator[str, None]:
        """Streamuje przebieg narady jako SSE events"""
        pass
    
    def _sse(self, event: str, data: Dict[str, Any]) -> str:
        """Format SSE event"""
        data["event"] = event
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
    
    def _get_context(self, query: str) -> tuple[List[str], List[Dict]]:
        """Pobiera kontekst z bazy wiedzy"""
        if not self.use_knowledge_base:
            return [], []
        try:
            chunks = query_knowledge(query, top_k=5)
            context = [c["text"] for c in chunks]
            sources = format_sources_for_display(chunks)
            return context, sources
        except Exception as e:
            print(f"KB error: {e}")
            return [], []


# ========== 🔬 DEEP DIVE ==========
class DeepDiveMode(CouncilMode):
    """Jeden ekspert analizuje dogłębnie przez wiele iteracji"""
    
    name = "deep_dive"
    emoji = "🔬"
    description = "Dogłębna analiza przez jednego eksperta w 4 rundach"
    
    async def run_stream(
        self, 
        query: str, 
        llm: Optional[LLMProvider] = None
    ) -> AsyncGenerator[str, None]:
        llm = llm or OpenAIProvider()
        context, sources = self._get_context(query)
        
        yield self._sse("sources", {"sources": sources})
        yield self._sse("mode_start", {"mode": self.name, "emoji": self.emoji})
        
        rounds = [
            ("Analiza problemu", "Przeanalizuj problem dogłębnie. Zidentyfikuj kluczowe aspekty i wyzwania."),
            ("Pytania doprecyzowujące", "Jakie pytania należy zadać, aby lepiej zrozumieć problem? Co wymaga wyjaśnienia?"),
            ("Pogłębiona analiza", "Na podstawie dotychczasowej analizy, rozwiń najważniejsze wątki. Szukaj niuansów."),
            ("Rekomendacje", "Sformułuj konkretne, praktyczne rekomendacje. Co należy zrobić krok po kroku?")
        ]
        
        all_analysis = ""
        
        for i, (round_name, instruction) in enumerate(rounds, 1):
            yield self._sse("round_start", {
                "round": i, 
                "title": round_name,
                "type": "deep_dive"
            })
            
            yield self._sse("agent_start", {
                "agent": "Ekspert",
                "emoji": "🎓",
                "role": round_name,
                "round": i
            })
            
            prompt = f"""Pytanie użytkownika: {query}

Dotychczasowa analiza:
{all_analysis if all_analysis else "(To jest pierwsza runda)"}

Kontekst z bazy wiedzy:
{chr(10).join(context[:3]) if context else "(brak)"}

TWOJE ZADANIE W TEJ RUNDZIE: {instruction}

Odpowiedz szczegółowo i merytorycznie."""
            
            round_content = ""
            async for token in llm.generate_stream(
                system_prompt="Jesteś ekspertem przeprowadzającym dogłębną analizę. Bądź szczegółowy, metodyczny i praktyczny.",
                user_prompt=prompt,
                temperature=0.7
            ):
                round_content += token
                yield self._sse("delta", {"agent": "Ekspert", "content": token})
            
            all_analysis += f"\n\n## {round_name}\n{round_content}"
            
            yield self._sse("agent_done", {"agent": "Ekspert"})
            yield self._sse("round_done", {"round": i})
        
        yield self._sse("complete", {"total_rounds": 4, "total_agents": 1})


# ========== ⚡ SPEED ROUND ==========
class SpeedRoundMode(CouncilMode):
    """Szybkie 2-3 zdaniowe odpowiedzi od wszystkich agentów"""
    
    name = "speed_round"
    emoji = "⚡"
    description = "Szybkie opinie - max 2-3 zdania od każdego"
    
    async def run_stream(
        self, 
        query: str, 
        llm: Optional[LLMProvider] = None
    ) -> AsyncGenerator[str, None]:
        llm = llm or OpenAIProvider()
        context, sources = self._get_context(query)
        
        yield self._sse("sources", {"sources": sources})
        yield self._sse("mode_start", {"mode": self.name, "emoji": self.emoji})
        
        agents = [
            ("Strateg", "🎯", "Szeroka perspektywa"),
            ("Analityk", "📊", "Za i przeciw"),
            ("Praktyk", "🔧", "Wykonalność"),
            ("Ekspert", "🎓", "Wiedza domenowa"),
            ("Innowator", "💡", "Kreatywne podejście"),
        ]
        
        yield self._sse("round_start", {"round": 1, "title": "Speed Round", "type": "speed"})
        
        for agent_name, emoji, role in agents:
            yield self._sse("agent_start", {
                "agent": agent_name,
                "emoji": emoji,
                "role": role,
                "round": 1
            })
            
            prompt = f"""Pytanie: {query}

WAŻNE: Odpowiedz w MAKSYMALNIE 2-3 zdaniach. Bądź konkretny i zwięzły.
Twoja perspektywa: {role}"""
            
            async for token in llm.generate_stream(
                system_prompt=f"Jesteś {agent_name}. Odpowiadaj BARDZO krótko - max 2-3 zdania. Bądź konkretny.",
                user_prompt=prompt,
                temperature=0.7,
                max_tokens=100
            ):
                yield self._sse("delta", {"agent": agent_name, "content": token})
            
            yield self._sse("agent_done", {"agent": agent_name})
        
        yield self._sse("round_done", {"round": 1})
        yield self._sse("complete", {"total_rounds": 1, "total_agents": len(agents)})


# ========== 🎯 DEVIL'S ADVOCATE ==========
class DevilsAdvocateMode(CouncilMode):
    """Jeden broni pomysłu, inni atakują"""
    
    name = "devils_advocate"
    emoji = "🎯"
    description = "Defender vs Attackers - testowanie pomysłu"
    
    async def run_stream(
        self, 
        query: str, 
        llm: Optional[LLMProvider] = None
    ) -> AsyncGenerator[str, None]:
        llm = llm or OpenAIProvider()
        context, sources = self._get_context(query)
        
        yield self._sse("sources", {"sources": sources})
        yield self._sse("mode_start", {"mode": self.name, "emoji": self.emoji})
        
        # Runda 1: Defender przedstawia argumenty ZA
        yield self._sse("round_start", {"round": 1, "title": "Obrona", "type": "defense"})
        yield self._sse("agent_start", {
            "agent": "Obrońca",
            "emoji": "🛡️",
            "role": "Argumenty ZA",
            "round": 1
        })
        
        defense_content = ""
        async for token in llm.generate_stream(
            system_prompt="Jesteś obrońcą tego pomysłu. Przedstaw WSZYSTKIE możliwe argumenty ZA. Bądź przekonujący i entuzjastyczny.",
            user_prompt=f"Pomysł do obrony: {query}\n\nPrzedstaw mocne argumenty ZA tym pomysłem.",
            temperature=0.7
        ):
            defense_content += token
            yield self._sse("delta", {"agent": "Obrońca", "content": token})
        
        yield self._sse("agent_done", {"agent": "Obrońca"})
        yield self._sse("round_done", {"round": 1})
        
        # Runda 2-3: Atakujący
        attackers = [
            ("Sceptyk", "😈", "Potencjalne problemy"),
            ("Pesymista", "⚠️", "Najgorszy scenariusz"),
        ]
        
        attack_content = ""
        for i, (name, emoji, role) in enumerate(attackers, 2):
            yield self._sse("round_start", {"round": i, "title": f"Atak #{i-1}", "type": "attack"})
            yield self._sse("agent_start", {
                "agent": name,
                "emoji": emoji,
                "role": role,
                "round": i
            })
            
            prompt = f"""Pomysł: {query}

Obrona: {defense_content}

Twoim zadaniem jest ZAATAKOWAĆ ten pomysł. Znajdź słabe punkty, problemy, ryzyka.
Perspektywa: {role}"""
            
            agent_content = ""
            async for token in llm.generate_stream(
                system_prompt=f"Jesteś {name}. Twoim zadaniem jest krytykować i szukać problemów. Bądź bezlitosny ale merytoryczny.",
                user_prompt=prompt,
                temperature=0.7
            ):
                agent_content += token
                yield self._sse("delta", {"agent": name, "content": token})
            
            attack_content += f"\n\n{name}: {agent_content}"
            yield self._sse("agent_done", {"agent": name})
            yield self._sse("round_done", {"round": i})
        
        # Runda 4: Obrońca odpowiada
        yield self._sse("round_start", {"round": 4, "title": "Odpowiedź obrony", "type": "response"})
        yield self._sse("agent_start", {
            "agent": "Obrońca",
            "emoji": "🛡️",
            "role": "Odpowiedź na krytykę",
            "round": 4
        })
        
        async for token in llm.generate_stream(
            system_prompt="Jesteś obrońcą. Odpowiedz na krytykę - weź pod uwagę dobre punkty, ale broń tego co można obronić.",
            user_prompt=f"Pomysł: {query}\n\nKrytyka:\n{attack_content}\n\nOdpowiedz na te zarzuty.",
            temperature=0.7
        ):
            yield self._sse("delta", {"agent": "Obrońca", "content": token})
        
        yield self._sse("agent_done", {"agent": "Obrońca"})
        yield self._sse("round_done", {"round": 4})
        
        # Runda 5: Werdykt
        yield self._sse("round_start", {"round": 5, "title": "Werdykt", "type": "verdict"})
        yield self._sse("agent_start", {
            "agent": "Sędzia",
            "emoji": "⚖️",
            "role": "Werdykt końcowy",
            "round": 5
        })
        
        async for token in llm.generate_stream(
            system_prompt="Jesteś bezstronnym sędzią. Oceń debatę i wydaj werdykt - czy pomysł jest wart realizacji?",
            user_prompt=f"Pomysł: {query}\n\nObrona: {defense_content}\n\nAtaki: {attack_content}\n\nWydaj werdykt.",
            temperature=0.7
        ):
            yield self._sse("delta", {"agent": "Sędzia", "content": token})
        
        yield self._sse("agent_done", {"agent": "Sędzia"})
        yield self._sse("round_done", {"round": 5})
        yield self._sse("complete", {"total_rounds": 5, "total_agents": 4})


# ========== 📊 SWOT ==========
class SWOTMode(CouncilMode):
    """Analiza SWOT - 4 agentów + synteza"""
    
    name = "swot"
    emoji = "📊"
    description = "Analiza SWOT: Strengths, Weaknesses, Opportunities, Threats"
    
    async def run_stream(
        self, 
        query: str, 
        llm: Optional[LLMProvider] = None
    ) -> AsyncGenerator[str, None]:
        llm = llm or OpenAIProvider()
        context, sources = self._get_context(query)
        
        yield self._sse("sources", {"sources": sources})
        yield self._sse("mode_start", {"mode": self.name, "emoji": self.emoji})
        
        swot_agents = [
            ("Strengths", "💪", "Mocne strony", "Znajdź WSZYSTKIE mocne strony, zalety, atuty. Co działa dobrze? Jakie są przewagi?"),
            ("Weaknesses", "🔻", "Słabe strony", "Znajdź WSZYSTKIE słabe strony, wady, problemy. Co można poprawić? Jakie są luki?"),
            ("Opportunities", "🌟", "Szanse", "Znajdź WSZYSTKIE szanse, możliwości, potencjał. Jakie trendy można wykorzystać? Co może pomóc?"),
            ("Threats", "⚠️", "Zagrożenia", "Znajdź WSZYSTKIE zagrożenia, ryzyka, przeszkody. Co może pójść nie tak? Jakie są niebezpieczeństwa?"),
        ]
        
        swot_results = {}
        
        for i, (name, emoji, role, instruction) in enumerate(swot_agents, 1):
            yield self._sse("round_start", {"round": i, "title": name, "type": "swot"})
            yield self._sse("agent_start", {
                "agent": name,
                "emoji": emoji,
                "role": role,
                "round": i
            })
            
            prompt = f"""Analizujesz: {query}

Kontekst: {chr(10).join(context[:2]) if context else "(brak)"}

TWOJE ZADANIE: {instruction}

Wymień minimum 3-5 punktów. Bądź konkretny i praktyczny."""
            
            agent_content = ""
            async for token in llm.generate_stream(
                system_prompt=f"Jesteś analitykiem SWOT skupionym na {role}. Bądź dokładny i wyczerpujący.",
                user_prompt=prompt,
                temperature=0.7
            ):
                agent_content += token
                yield self._sse("delta", {"agent": name, "content": token})
            
            swot_results[name] = agent_content
            yield self._sse("agent_done", {"agent": name})
            yield self._sse("round_done", {"round": i})
        
        # Synteza SWOT
        yield self._sse("round_start", {"round": 5, "title": "Synteza SWOT", "type": "synthesis"})
        yield self._sse("agent_start", {
            "agent": "Syntezator",
            "emoji": "🔮",
            "role": "Podsumowanie SWOT",
            "round": 5
        })
        
        synthesis_prompt = f"""Analiza SWOT dla: {query}

STRENGTHS (Mocne strony):
{swot_results.get('Strengths', '')}

WEAKNESSES (Słabe strony):
{swot_results.get('Weaknesses', '')}

OPPORTUNITIES (Szanse):
{swot_results.get('Opportunities', '')}

THREATS (Zagrożenia):
{swot_results.get('Threats', '')}

Stwórz podsumowanie tej analizy SWOT. Wskaż:
1. Najważniejsze wnioski
2. Rekomendowane działania
3. Priorytety"""
        
        async for token in llm.generate_stream(
            system_prompt="Jesteś ekspertem od strategii. Podsumuj analizę SWOT i daj praktyczne rekomendacje.",
            user_prompt=synthesis_prompt,
            temperature=0.7
        ):
            yield self._sse("delta", {"agent": "Syntezator", "content": token})
        
        yield self._sse("agent_done", {"agent": "Syntezator"})
        yield self._sse("round_done", {"round": 5})
        yield self._sse("complete", {"total_rounds": 5, "total_agents": 5})


# ========== 🧐 KRYTYK (Business Validation) ==========
class RedTeamMode(CouncilMode):
    """Krytyczna weryfikacja biznesowa pomysłu/strategii"""
    
    name = "red_team"
    emoji = "🧐"
    description = "Krytyk - bezlitosna weryfikacja Twojego pomysłu"
    
    async def run_stream(
        self, 
        query: str, 
        llm: Optional[LLMProvider] = None
    ) -> AsyncGenerator[str, None]:
        llm = llm or OpenAIProvider()
        context, sources = self._get_context(query)
        
        yield self._sse("sources", {"sources": sources})
        yield self._sse("mode_start", {"mode": self.name, "emoji": self.emoji})
        
        # === RUNDA 1: Zrozumienie pomysłu ===
        yield self._sse("round_start", {"round": 1, "title": "Analiza pomysłu", "type": "analysis"})
        yield self._sse("agent_start", {
            "agent": "Moderator",
            "emoji": "📋",
            "role": "Podsumowanie pomysłu",
            "round": 1
        })
        
        summary_content = ""
        async for token in llm.generate_stream(
            system_prompt="Jesteś moderatorem Red Team. Podsumuj pomysł użytkownika w kilku punktach, identyfikując kluczowe założenia, które wymagają weryfikacji.",
            user_prompt=f"""Pomysł/strategia do weryfikacji: {query}

Kontekst: {chr(10).join(context[:2]) if context else "(brak)"}

Streść pomysł i wylistuj 3-5 KLUCZOWYCH ZAŁOŻEŃ, które zespół Red Team powinien przetestować.""",
            temperature=0.6
        ):
            summary_content += token
            yield self._sse("delta", {"agent": "Moderator", "content": token})
        
        yield self._sse("agent_done", {"agent": "Moderator"})
        yield self._sse("round_done", {"round": 1})
        
        # === RUNDY 2-6: Ataki biznesowe ===
        red_team_members = [
            ("Inwestor-Sceptyk", "💰", "Due Diligence", 
             """Jesteś doświadczonym inwestorem VC/PE. Widziałeś setki pitch decków.
Twoim zadaniem jest ZNALEŹĆ SŁABOŚCI tego pomysłu z perspektywy inwestycyjnej:
- Czy model biznesowy ma sens? 
- Czy unit economics się zgadzają?
- Czy to jest skalowalny biznes?
- Jakie są red flags dla inwestora?
- Dlaczego mógłbym NIE zainwestować?"""),

            ("Klient-Sceptyk", "🛒", "Voice of Customer",
             """Jesteś wymagającym, sceptycznym potencjalnym klientem.
Twoim zadaniem jest zakwestionować WARTOŚĆ dla klienta:
- Dlaczego miałbym to kupić/używać?
- Co mnie powstrzymuje?
- Jakie mam alternatywy (w tym: nic nie robić)?
- Czy cena jest uzasadniona?
- Jakie są moje obawy i wątpliwości?"""),

            ("Doświadczony Przedsiębiorca", "🎯", "Reality Check",
             """Jesteś przedsiębiorcą, który zbudował i sprzedał kilka firm. Znasz realia.
Twoim zadaniem jest pokazać PRAKTYCZNE PROBLEMY:
- Co może pójść nie tak operacyjnie?
- Gdzie są ukryte koszty i komplikacje?
- Jakie zasoby są NAPRAWDĘ potrzebne?
- Jakie błędy popełniają nowicjusze w tej branży?
- Co ty byś zrobił inaczej?"""),

            ("Analityk Rynku", "📊", "Market Reality",
             """Jesteś analitykiem rynku z 15-letnim doświadczeniem.
Twoim zadaniem jest ZWERYFIKOWAĆ ZAŁOŻENIA RYNKOWE:
- Czy rynek jest wystarczająco duży (TAM/SAM/SOM)?
- Jaka jest prawdziwa konkurencja?
- Czy timing jest odpowiedni?
- Jakie trendy mogą pomóc lub zaszkodzić?
- Jakie są bariery wejścia?"""),

            ("Konkurent", "🎭", "Competitive Response",
             """Jesteś CEO głównego konkurenta w tej branży.
Właśnie dowiedziałeś się o tym pomyśle. Twoja reakcja:
- Jak bym skopiował/ulepszył ten pomysł?
- Jakie mam przewagi, których oni nie mają?
- Jak bym ich zniszczył lub zablokował?
- Gdzie widzę ich słabości?
- Co bym im powiedział, żeby się poddali?"""),
        ]
        
        all_critiques = []
        
        for i, (name, emoji, role, system_prompt) in enumerate(red_team_members, 2):
            yield self._sse("round_start", {"round": i, "title": f"🔴 {role}", "type": "attack"})
            yield self._sse("agent_start", {
                "agent": name,
                "emoji": emoji,
                "role": role,
                "round": i
            })
            
            user_prompt = f"""Pomysł do weryfikacji: {query}

Podsumowanie i założenia:
{summary_content}

Przeprowadź BEZLITOSNĄ, ale MERYTORYCZNĄ krytykę z Twojej perspektywy. 
Bądź konkretny - podawaj przykłady, liczby, scenariusze.
Twoja opinia może uratować kogoś przed kosztownym błędem."""
            
            agent_content = ""
            async for token in llm.generate_stream(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.8
            ):
                agent_content += token
                yield self._sse("delta", {"agent": name, "content": token})
            
            all_critiques.append(f"### {emoji} {name} ({role})\n{agent_content}")
            yield self._sse("agent_done", {"agent": name})
            yield self._sse("round_done", {"round": i})
        
        # === RUNDA 7: Odpowiedź obrony ===
        yield self._sse("round_start", {"round": 7, "title": "Odpowiedź na krytykę", "type": "defense"})
        yield self._sse("agent_start", {
            "agent": "Adwokat Pomysłu",
            "emoji": "🛡️",
            "role": "Obrona i odpowiedzi",
            "round": 7
        })
        
        defense_content = ""
        async for token in llm.generate_stream(
            system_prompt="""Jesteś obrońcą tego pomysłu. Przeczytaj wszystkie krytyki i:
1. Przyznaj rację tam, gdzie krytyka jest słuszna
2. Obroń to, co można obronić (z argumentami)
3. Zaproponuj jak rozwiązać uzasadnione obawy
4. Wskaż co wymaga dalszej analizy""",
            user_prompt=f"""Pomysł: {query}

Krytyki zespołu Red Team:
{chr(10).join(all_critiques)}

Odpowiedz na te zarzuty uczciwie i konstruktywnie.""",
            temperature=0.7
        ):
            defense_content += token
            yield self._sse("delta", {"agent": "Adwokat Pomysłu", "content": token})
        
        yield self._sse("agent_done", {"agent": "Adwokat Pomysłu"})
        yield self._sse("round_done", {"round": 7})
        
        # === RUNDA 8: Raport końcowy ===
        yield self._sse("round_start", {"round": 8, "title": "Raport Red Team", "type": "report"})
        yield self._sse("agent_start", {
            "agent": "Raport Red Team",
            "emoji": "📑",
            "role": "Podsumowanie weryfikacji",
            "round": 8
        })
        
        async for token in llm.generate_stream(
            system_prompt="""Jesteś lead'em zespołu Red Team. Stwórz profesjonalny raport końcowy.""",
            user_prompt=f"""Pomysł: {query}

Wszystkie krytyki:
{chr(10).join(all_critiques)}

Odpowiedź obrony:
{defense_content}

Stwórz RAPORT RED TEAM w formacie:

## 🚨 Krytyczne Ryzyka (showstoppers)
(Problemy, które mogą zabić projekt jeśli nie zostaną rozwiązane)

## ⚠️ Istotne Wyzwania
(Poważne problemy wymagające uwagi)

## 💡 Sugestie Ulepszeń
(Co warto przemyśleć/zmienić)

## ✅ Mocne Strony
(Co zostało pozytywnie zweryfikowane)

## 📋 Następne Kroki
(Co autor powinien zrobić dalej)

## WERDYKT: [Proceed / Proceed with Changes / Pivot / Kill]
(Z krótkim uzasadnieniem)""",
            temperature=0.6
        ):
            yield self._sse("delta", {"agent": "Raport Red Team", "content": token})
        
        yield self._sse("agent_done", {"agent": "Raport Red Team"})
        yield self._sse("round_done", {"round": 8})
        yield self._sse("complete", {"total_rounds": 8, "total_agents": 7})


# ========== REGISTRY ==========
COUNCIL_MODES: Dict[str, type] = {
    "deep_dive": DeepDiveMode,
    "speed_round": SpeedRoundMode,
    "devils_advocate": DevilsAdvocateMode,
    "swot": SWOTMode,
    "red_team": RedTeamMode,
}

def get_mode(mode_name: str) -> Optional[CouncilMode]:
    """Zwraca instancję trybu na podstawie nazwy"""
    mode_class = COUNCIL_MODES.get(mode_name)
    if mode_class:
        return mode_class()
    return None

def list_modes() -> List[Dict[str, str]]:
    """Zwraca listę dostępnych trybów"""
    return [
        {"id": mode_id, "name": cls.name, "emoji": cls.emoji, "description": cls.description}
        for mode_id, cls in COUNCIL_MODES.items()
    ]
