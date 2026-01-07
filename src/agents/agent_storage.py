"""
Agent Storage
==============
Przechowywanie custom agents w JSON
"""

import json
import os
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from src.agents.custom_agents import CustomAgentConfig


# Ścieżka do pliku z agentami
DATA_DIR = Path(__file__).parent.parent.parent / "data"
AGENTS_FILE = DATA_DIR / "custom_agents.json"


def ensure_data_dir():
    """Upewnia się że katalog data istnieje"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not AGENTS_FILE.exists():
        AGENTS_FILE.write_text("[]")


def load_all() -> List[CustomAgentConfig]:
    """Ładuje wszystkich custom agentów"""
    ensure_data_dir()
    
    try:
        data = json.loads(AGENTS_FILE.read_text())
        return [CustomAgentConfig.from_dict(item) for item in data]
    except Exception as e:
        print(f"⚠️ Błąd wczytywania agentów: {e}")
        return []


def save_all(agents: List[CustomAgentConfig]):
    """Zapisuje wszystkich agentów"""
    ensure_data_dir()
    data = [agent.to_dict() for agent in agents]
    AGENTS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def get(agent_id: str) -> Optional[CustomAgentConfig]:
    """Pobiera agenta po ID"""
    agents = load_all()
    for agent in agents:
        if agent.id == agent_id:
            return agent
    return None


def save(config: CustomAgentConfig) -> str:
    """Zapisuje nowego agenta, zwraca ID"""
    agents = load_all()
    
    # Sprawdź czy już istnieje
    existing_idx = None
    for i, agent in enumerate(agents):
        if agent.id == config.id:
            existing_idx = i
            break
    
    config.updated_at = datetime.now().isoformat()
    
    if existing_idx is not None:
        agents[existing_idx] = config
    else:
        if not config.created_at:
            config.created_at = datetime.now().isoformat()
        agents.append(config)
    
    save_all(agents)
    return config.id


def update(agent_id: str, updates: Dict[str, Any]) -> Optional[CustomAgentConfig]:
    """Aktualizuje agenta"""
    agents = load_all()
    
    for i, agent in enumerate(agents):
        if agent.id == agent_id:
            # Aktualizuj pola
            agent_dict = agent.to_dict()
            agent_dict.update(updates)
            agent_dict["updated_at"] = datetime.now().isoformat()
            agents[i] = CustomAgentConfig.from_dict(agent_dict)
            save_all(agents)
            return agents[i]
    
    return None


def delete(agent_id: str) -> bool:
    """Usuwa agenta"""
    agents = load_all()
    original_len = len(agents)
    agents = [a for a in agents if a.id != agent_id]
    
    if len(agents) < original_len:
        save_all(agents)
        return True
    return False


def toggle_enabled(agent_id: str) -> Optional[bool]:
    """Przełącza status enabled agenta"""
    agents = load_all()
    
    for agent in agents:
        if agent.id == agent_id:
            agent.enabled = not agent.enabled
            agent.updated_at = datetime.now().isoformat()
            save_all(agents)
            return agent.enabled
    
    return None


def get_enabled() -> List[CustomAgentConfig]:
    """Zwraca tylko włączonych agentów"""
    return [a for a in load_all() if a.enabled]
