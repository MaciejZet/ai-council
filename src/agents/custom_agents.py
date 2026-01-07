"""
Custom Agents
==============
Agenty tworzone przez użytkownika z pełną konfiguracją persony, promptu i narzędzi
"""

import uuid
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime

from src.agents.base import BaseAgent, AgentConfig, agent_registry
from src.llm_providers import LLMProvider, get_provider


@dataclass
class CustomAgentConfig:
    """Konfiguracja agenta utworzonego przez użytkownika"""
    id: str = ""
    name: str = "Nowy Agent"
    emoji: str = "🤖"
    role: str = "Custom Agent"
    persona: str = ""                    # Opis osobowości agenta
    system_prompt: str = ""              # Pełny system prompt
    template_id: Optional[str] = None    # ID użytego szablonu
    tools: List[str] = field(default_factory=list)  # ["web_search", "code_exec", "knowledge_base"]
    context_limit: int = 5000            # Limit tokenów kontekstu
    memory_type: str = "session"         # "session" | "persistent"
    enabled: bool = True
    created_at: str = ""
    updated_at: str = ""
    
    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())[:8]
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "emoji": self.emoji,
            "role": self.role,
            "persona": self.persona,
            "system_prompt": self.system_prompt,
            "template_id": self.template_id,
            "tools": self.tools,
            "context_limit": self.context_limit,
            "memory_type": self.memory_type,
            "enabled": self.enabled,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CustomAgentConfig':
        return cls(
            id=data.get("id", ""),
            name=data.get("name", "Nowy Agent"),
            emoji=data.get("emoji", "🤖"),
            role=data.get("role", "Custom Agent"),
            persona=data.get("persona", ""),
            system_prompt=data.get("system_prompt", ""),
            template_id=data.get("template_id"),
            tools=data.get("tools", []),
            context_limit=data.get("context_limit", 5000),
            memory_type=data.get("memory_type", "session"),
            enabled=data.get("enabled", True),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", "")
        )


class CustomAgent(BaseAgent):
    """
    Agent utworzony przez użytkownika z własną konfiguracją.
    Rozszerza BaseAgent o dodatkowe możliwości.
    """
    
    def __init__(self, custom_config: CustomAgentConfig, provider: LLMProvider = None):
        # Konwersja CustomAgentConfig na standardowy AgentConfig
        agent_config = AgentConfig(
            name=custom_config.name,
            emoji=custom_config.emoji,
            role=custom_config.role,
            personality=custom_config.persona,
            enabled=custom_config.enabled
        )
        super().__init__(agent_config, provider)
        
        self.custom_config = custom_config
        self._system_prompt = custom_config.system_prompt
        self.tools = custom_config.tools
        self.context_limit = custom_config.context_limit
    
    @property
    def agent_id(self) -> str:
        return self.custom_config.id
    
    def get_system_prompt(self) -> str:
        """Zwraca customowy system prompt"""
        if self._system_prompt:
            return self._system_prompt
        
        # Fallback - generuj prompt z persony
        return f"""Jesteś {self.name} - {self.role}.

{self.custom_config.persona}

Odpowiadaj po polsku, profesjonalnie i merytorycznie.
Wykorzystuj swoją ekspertyzę do udzielania wartościowych porad."""
    
    def has_tool(self, tool_name: str) -> bool:
        """Sprawdza czy agent ma dostęp do danego narzędzia"""
        return tool_name in self.tools
    
    def build_user_prompt(self, query: str, context: List[str] = None) -> str:
        """Buduje prompt użytkownika z uwzględnieniem limitu kontekstu"""
        context = context or []
        
        base_prompt = f"## Pytanie użytkownika:\n{query}"
        
        if context and self.has_tool("knowledge_base"):
            # Ogranicz kontekst do limitu
            context_text = "\n---\n".join(context)
            if len(context_text) > self.context_limit:
                context_text = context_text[:self.context_limit] + "..."
            
            base_prompt = f"""## Kontekst z bazy wiedzy:
{context_text}

{base_prompt}"""
        
        return base_prompt


def create_custom_agent(config: CustomAgentConfig, provider: LLMProvider = None) -> CustomAgent:
    """Tworzy i rejestruje custom agenta"""
    agent = CustomAgent(config, provider)
    agent_registry.register(agent)
    return agent


def get_custom_agent_info(config: CustomAgentConfig) -> Dict[str, Any]:
    """Zwraca informacje o custom agencie do wyświetlenia w UI"""
    return {
        "id": config.id,
        "name": config.name,
        "emoji": config.emoji,
        "role": config.role,
        "persona": config.persona[:100] + "..." if len(config.persona) > 100 else config.persona,
        "tools": config.tools,
        "enabled": config.enabled,
        "is_custom": True
    }
