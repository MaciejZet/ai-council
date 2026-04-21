"""
Base Agent Class
=================
Abstrakcyjna klasa bazowa dla wszystkich agentów w radzie
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, AsyncGenerator
import asyncio

from src.llm_providers import LLMProvider, LLMResponse, get_provider


@dataclass
class AgentResponse:
    """Odpowiedź agenta z danymi o tokenach"""
    agent_name: str
    role: str
    perspective: str
    content: str
    provider_used: str
    # Token usage
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model: str = ""
    
    @property
    def usage(self) -> Dict[str, int]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens
        }
    

@dataclass
class AgentConfig:
    """Konfiguracja agenta"""
    name: str
    role: str
    emoji: str = "🤖"
    personality: str = ""
    enabled: bool = True
    preferred_provider: Optional[str] = None


class BaseAgent(ABC):
    """
    Abstrakcyjna klasa bazowa dla agentów
    
    Każdy agent ma:
    - Unikalną osobowość (system prompt)
    - Perspektywę analizy
    - Możliwość korzystania z kontekstu z bazy wiedzy
    """
    
    def __init__(self, config: AgentConfig, provider: Optional[LLMProvider] = None):
        self.config = config
        self.provider = provider or get_provider(config.preferred_provider)
    
    @property
    def name(self) -> str:
        return self.config.name
    
    @property
    def role(self) -> str:
        return self.config.role
    
    @property
    def emoji(self) -> str:
        return self.config.emoji
    
    @abstractmethod
    def get_system_prompt(self) -> str:
        """Zwraca system prompt definiujący osobowość agenta"""
        pass
    
    def build_user_prompt(self, query: str, context: List[str]) -> str:
        """
        Buduje prompt użytkownika z zapytaniem i kontekstem
        """
        context_section = ""
        if context:
            context_section = (
                "\n\n## Kontekst z bazy wiedzy:\n"
                + "\n---\n".join(context)
            )
        
        return f"""## Zapytanie użytkownika:
{query}
{context_section}

## Twoja analiza:
Przeanalizuj powyższe z perspektywy swojej roli jako {self.role}.
Odpowiedz po polsku, strukturalnie i konkretnie. Bądź zwięzły ale kompletny -
dostarcz wartościową analizę bez zbędnego gadania."""
    
    async def analyze(self, query: str, context: List[str] = None) -> AgentResponse:
        """
        Analizuje zapytanie z perspektywy agenta
        Zwraca AgentResponse z danymi o tokenach
        """
        context = context or []
        
        system_prompt = self.get_system_prompt()
        user_prompt = self.build_user_prompt(query, context)
        
        # Oblicz dynamiczny limit tokenów
        max_tokens = self._calculate_dynamic_max_tokens(query)
        
        # LLMResponse zawiera teraz usage data
        llm_response: LLMResponse = await self.provider.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.7,
            max_tokens=max_tokens
        )
        
        # Smart Truncation: Jeśli odpowiedź jest ucięta (brak kropki/znaku końca), przytnij do ostatniego zdania
        content = llm_response.content
        if max_tokens and len(content) > 0 and content[-1] not in ['.', '!', '?', '"', "'", '\n']:
             content = self._smart_truncate(content)

        return AgentResponse(
            agent_name=f"{self.emoji} {self.name}",
            role=self.role,
            perspective=self.config.personality[:100] + "..." if len(self.config.personality) > 100 else self.config.personality,
            content=content,
            provider_used=self.provider.get_name(),
            prompt_tokens=llm_response.prompt_tokens,
            completion_tokens=llm_response.completion_tokens,
            total_tokens=llm_response.total_tokens,
            model=llm_response.model
        )
    
    async def analyze_stream(
        self, 
        query: str, 
        context: List[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Streamuje odpowiedź agenta token po tokenie
        """
        context = context or []
        
        system_prompt = self.get_system_prompt()
        user_prompt = self.build_user_prompt(query, context)
        
        # Oblicz dynamiczny limit tokenów
        max_tokens = self._calculate_dynamic_max_tokens(query)
        
        async for token in self.provider.generate_stream(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.7,
            max_tokens=max_tokens
        ):
            yield token

    def _calculate_dynamic_max_tokens(self, query: str) -> Optional[int]:
        """
        Oblicza dynamiczny limit tokenów na podstawie długości/złożoności zapytania.
        Zapewnia rozsądne limity dla wszystkich typów pytań.
        """
        word_count = len(query.split())

        # Krótkie pytania (1-10 słów) - średnia odpowiedź
        if word_count <= 10:
            return 1000  # ~750 słów, wystarczy na pełną odpowiedź

        # Średnie pytania (11-30 słów) - dłuższa odpowiedź
        elif word_count <= 30:
            return 1500  # ~1100 słów

        # Długie pytania (31-50 słów) - szczegółowa odpowiedź
        elif word_count <= 50:
            return 2000  # ~1500 słów

        # Bardzo długie pytania (50+ słów) - kompleksowa odpowiedź
        else:
            return 2500  # ~1900 słów

    def _smart_truncate(self, text: str) -> str:
        """Przycina tekst do ostatniego pełnego zdania"""
        import re
        # Szukamy ostatniego wystąpienia znaku końca zdania
        match = list(re.finditer(r'[.!?\n]', text))
        if match:
            last_idx = match[-1].end()
            return text[:last_idx]
        return text
    
    def build_reaction_prompt(
        self, 
        query: str, 
        context: List[str],
        other_response: 'AgentResponse',
        my_previous: Optional['AgentResponse'] = None
    ) -> str:
        """Buduje prompt do reakcji na innego agenta"""
        context_section = ""
        if context:
            context_section = "\n\n## Kontekst z bazy wiedzy:\n" + "\n---\n".join(context[:2])
        
        my_previous_section = ""
        if my_previous:
            my_previous_section = f"\n\n## Twoje poprzednie stanowisko:\n{my_previous.content[:500]}..."
        
        return f"""## Zapytanie użytkownika:
{query}
{context_section}
{my_previous_section}

## Stanowisko {other_response.agent_name} ({other_response.role}):
{other_response.content}

## Twoja reakcja jako {self.role}:
Skomentuj powyższe stanowisko z perspektywy swojej roli. Możesz:
- Zgodzić się i rozwinąć
- Nie zgodzić się i podać kontrargumenty  
- Uzupełnić o brakujące aspekty
- Wskazać ryzyka lub możliwości

Odpowiedz zwięźle (2-3 akapity), po polsku. Zacznij od jasnego stanowiska: "Zgadzam się...", "Nie zgadzam się...", lub "Chciałbym uzupełnić..."."""
    
    async def react_stream(
        self,
        query: str,
        context: List[str],
        other_response: 'AgentResponse',
        my_previous: Optional['AgentResponse'] = None
    ) -> AsyncGenerator[str, None]:
        """
        Streamuje reakcję na odpowiedź innego agenta
        """
        system_prompt = self.get_system_prompt()
        user_prompt = self.build_reaction_prompt(query, context, other_response, my_previous)
        
        async for token in self.provider.generate_stream(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.7
        ):
            yield token
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}', role='{self.role}')"


class AgentRegistry:
    """
    Rejestr wszystkich dostępnych agentów
    """
    
    def __init__(self):
        self._agents: dict[str, BaseAgent] = {}
    
    def register(self, agent: BaseAgent) -> None:
        """Rejestruje agenta"""
        self._agents[agent.name] = agent
    
    def unregister(self, name: str) -> None:
        """Wyrejestrowuje agenta"""
        if name in self._agents:
            del self._agents[name]
    
    def get(self, name: str) -> Optional[BaseAgent]:
        """Zwraca agenta po nazwie"""
        return self._agents.get(name)
    
    def get_all(self) -> List[BaseAgent]:
        """Zwraca wszystkich zarejestrowanych agentów"""
        return list(self._agents.values())
    
    def get_enabled(self) -> List[BaseAgent]:
        """Zwraca tylko włączonych agentów"""
        return [a for a in self._agents.values() if a.config.enabled]
    
    def toggle(self, name: str, enabled: bool) -> bool:
        """Włącza/wyłącza agenta"""
        if name in self._agents:
            self._agents[name].config.enabled = enabled
            return True
        return False
    
    def list_names(self) -> List[str]:
        """Zwraca listę nazw agentów"""
        return list(self._agents.keys())


# Globalny rejestr agentów
agent_registry = AgentRegistry()
