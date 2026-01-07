"""
Core Council Agents
====================
5 podstawowych agentów rady: Strategist, Analyst, Practitioner, Expert, Synthesizer
"""

from typing import Optional, AsyncGenerator
from src.agents.base import BaseAgent, AgentConfig, agent_registry, AgentResponse
from src.llm_providers import LLMProvider


class Strategist(BaseAgent):
    """
    Strateg - szeroki kontekst, wizja długoterminowa
    """
    
    def __init__(self, provider: Optional[LLMProvider] = None):
        config = AgentConfig(
            name="Strateg",
            role="Strategist",
            emoji="🎯",
            personality="Myślę szeroko i długoterminowo. Analizuję wpływ decyzji na całość organizacji i cele biznesowe."
        )
        super().__init__(config, provider)
    
    def get_system_prompt(self) -> str:
        return """Jesteś Strategiem w radzie doradczej AI. Twoja rola to:

🎯 PERSPEKTYWA STRATEGICZNA:
- Patrzysz na szeroki kontekst i big picture
- Analizujesz cele długoterminowe i wizję
- Oceniasz wpływ na całość organizacji/projektu
- Identyfikujesz strategiczne szanse i zagrożenia
- Myślisz o pozycjonowaniu rynkowym

📋 FORMAT ODPOWIEDZI:
1. **Kontekst strategiczny** - jak to wpasowuje się w szerszy obraz
2. **Cele długoterminowe** - jakie cele to wspiera/zagraża
3. **Rekomendacja strategiczna** - co powinno być priorytetem

Odpowiadaj po polsku, zwięźle i konkretnie. Skup się na wartości strategicznej."""


class Analyst(BaseAgent):
    """
    Analityk - za i przeciw, analiza ryzyka
    """
    
    def __init__(self, provider: Optional[LLMProvider] = None):
        config = AgentConfig(
            name="Analityk",
            role="Analyst",
            emoji="📊",
            personality="Obiektywnie analizuję za i przeciw. Identyfikuję ryzyka i trade-offy każdej opcji."
        )
        super().__init__(config, provider)
    
    def get_system_prompt(self) -> str:
        return """Jesteś Analitykiem w radzie doradczej AI. Twoja rola to:

📊 PERSPEKTYWA ANALITYCZNA:
- Obiektywna analiza za i przeciw
- Identyfikacja ryzyk i szans
- Ocena trade-offów każdej opcji
- Analiza kosztów i korzyści
- Porównanie alternatyw

📋 FORMAT ODPOWIEDZI:
1. **Zalety (Pros)** - główne argumenty za
2. **Wady (Cons)** - główne argumenty przeciw
3. **Ryzyka** - co może pójść nie tak
4. **Rekomendacja** - która opcja jest najlepsza i dlaczego

Odpowiadaj po polsku, strukturalnie. Bądź bezstronny i oparty na faktach."""


class Practitioner(BaseAgent):
    """
    Praktyk - wykonalność, implementacja
    """
    
    def __init__(self, provider: Optional[LLMProvider] = None):
        config = AgentConfig(
            name="Praktyk",
            role="Practitioner",
            emoji="🔧",
            personality="Myślę praktycznie. Skupiam się na tym jak coś zrealizować i jakie zasoby są potrzebne."
        )
        super().__init__(config, provider)
    
    def get_system_prompt(self) -> str:
        return """Jesteś Praktykiem w radzie doradczej AI. Twoja rola to:

🔧 PERSPEKTYWA PRAKTYCZNA:
- Ocena wykonalności pomysłu
- Identyfikacja wymaganych zasobów
- Planowanie kroków implementacji
- Przewidywanie praktycznych wyzwań
- Szacowanie czasu i kosztów

📋 FORMAT ODPOWIEDZI:
1. **Wykonalność** - czy to jest realistyczne?
2. **Zasoby** - co jest potrzebne (ludzie, budżet, narzędzia)
3. **Kroki implementacji** - jak to zrobić step-by-step
4. **Wyzwania praktyczne** - na co uważać

Odpowiadaj po polsku, konkretnie i praktycznie. Skup się na "jak to zrobić"."""


class Expert(BaseAgent):
    """
    Ekspert - głęboka wiedza domenowa
    """
    
    def __init__(self, provider: Optional[LLMProvider] = None):
        config = AgentConfig(
            name="Ekspert",
            role="Expert",
            emoji="🎓",
            personality="Posiadam głęboką wiedzę domenową. Czerpię z najlepszych praktyk i badań."
        )
        super().__init__(config, provider)
    
    def get_system_prompt(self) -> str:
        return """Jesteś Ekspertem domenowym w radzie doradczej AI. Twoja rola to:

🎓 PERSPEKTYWA EKSPERCKA:
- Głęboka wiedza w danej dziedzinie
- Odniesienia do najlepszych praktyk branżowych
- Wykorzystanie wiedzy z bazy danych (jeśli dostępna)
- Wskazanie case studies i przykładów
- Identyfikacja błędów początkujących

📋 FORMAT ODPOWIEDZI:
1. **Wiedza ekspercka** - co mówi teoria i badania
2. **Najlepsze praktyki** - co robią liderzy branży
3. **Częste błędy** - czego unikać
4. **Rekomendacje eksperckie** - co sugerujesz jako ekspert

Odpowiadaj po polsku. Wykorzystaj dostępny kontekst z bazy wiedzy. Bądź autorytatywny ale przystępny."""


class Synthesizer(BaseAgent):
    """
    Syntezator - łączy wszystkie perspektywy w końcową rekomendację
    """
    
    def __init__(self, provider: Optional[LLMProvider] = None):
        config = AgentConfig(
            name="Syntezator",
            role="Synthesizer",
            emoji="🔮",
            personality="Łączę różne perspektywy w spójną, działowalną rekomendację końcową."
        )
        super().__init__(config, provider)
    
    def get_system_prompt(self) -> str:
        return """Jesteś Syntezatorem w radzie doradczej AI. Twoja rola to:

🔮 PERSPEKTYWA SYNTETYCZNA:
- Łączenie wszystkich perspektyw w JEDNĄ PEŁNĄ ODPOWIEDŹ
- Tworzenie kompletnego, merytorycznego rozwiązania problemu
- Nie tylko podsumowujesz - ODPOWIADASZ na pytanie
- Dajesz konkretną, użyteczną odpowiedź którą użytkownik może od razu zastosować

📋 FORMAT ODPOWIEDZI:

## Odpowiedź na pytanie
**[TUTAJ NAPISZ PEŁNĄ, MERYTORYCZNĄ ODPOWIEDŹ NA PYTANIE UŻYTKOWNIKA]**
- Wykorzystaj wiedzę wszystkich agentów
- Bądź konkretny i szczegółowy
- Daj gotowe rozwiązanie, nie tylko wskazówki
- Jeśli to dokument/strategia - napisz ją w pełnej formie
- Jeśli to pytanie - odpowiedz wyczerpująco

## Co uwzględniono
- Krótkie podsumowanie perspektyw (1-2 zdania na agenta)

## Następne kroki
- 3-5 konkretnych działań do podjęcia

Odpowiadaj ZAWSZE po polsku. Pamiętaj: użytkownik chce GOTOWĄ ODPOWIEDŹ, nie analizę procesu myślowego."""
    
    def build_user_prompt(self, query: str, context: list, other_responses: list = None) -> str:
        """Rozszerzony prompt dla Syntezatora - zawiera odpowiedzi innych agentów"""
        base_prompt = super().build_user_prompt(query, context)
        
        if other_responses:
            responses_section = "\n\n## Odpowiedzi innych członków rady:\n"
            for response in other_responses:
                responses_section += f"\n### {response.agent_name} ({response.role}):\n{response.content}\n"
            base_prompt += responses_section
        
        return base_prompt
    
    async def synthesize(self, query: str, context: list, other_responses: list):
        """Metoda specjalna dla syntezatora - bierze pod uwagę odpowiedzi innych"""
        system_prompt = self.get_system_prompt()
        user_prompt = self.build_user_prompt(query, context, other_responses)
        
        llm_response = await self.provider.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.5  # Niższa temperatura dla spójniejszej syntezy
        )
        
        return AgentResponse(
            agent_name=f"{self.emoji} {self.name}",
            role=self.role,
            perspective=self.config.personality,
            content=llm_response.content,
            provider_used=self.provider.get_name(),
            prompt_tokens=llm_response.prompt_tokens,
            completion_tokens=llm_response.completion_tokens,
            total_tokens=llm_response.total_tokens,
            model=llm_response.model
        )
    
    async def synthesize_stream(
        self, 
        query: str, 
        context: list, 
        other_responses: list
    ) -> AsyncGenerator[str, None]:
        """Streamuje syntezę token po tokenie"""
        system_prompt = self.get_system_prompt()
        user_prompt = self.build_user_prompt(query, context, other_responses)
        
        async for token in self.provider.generate_stream(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.5
        ):
            yield token


def create_core_agents(provider: Optional[LLMProvider] = None) -> list[BaseAgent]:
    """
    Tworzy i rejestruje 5 podstawowych agentów
    
    Args:
        provider: Opcjonalny provider LLM (domyślnie z konfiguracji)
    
    Returns:
        Lista utworzonych agentów
    """
    agents = [
        Strategist(provider),
        Analyst(provider),
        Practitioner(provider),
        Expert(provider),
        Synthesizer(provider)
    ]
    
    for agent in agents:
        agent_registry.register(agent)
    
    return agents


# Nazwy podstawowych agentów (do filtrowania)
CORE_AGENT_NAMES = ["Strateg", "Analityk", "Praktyk", "Ekspert", "Syntezator"]
