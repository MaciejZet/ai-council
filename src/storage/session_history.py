"""
Session History Storage
========================
Zapisuje i wczytuje historię narad do/z plików JSON
"""

import os
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict


# Ścieżka do folderu z sesjami
SESSIONS_DIR = Path(__file__).parent.parent.parent / "data" / "sessions"


@dataclass
class SessionMetadata:
    """Metadane sesji"""
    id: str
    timestamp: str
    query: str
    council_type: str  # "standard" lub "historical"
    agents_used: List[str]
    model: str
    provider: str
    total_tokens: int = 0
    cost_usd: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SessionData:
    """Pełne dane sesji"""
    metadata: SessionMetadata
    responses: List[Dict[str, Any]] = field(default_factory=list)
    synthesis: Optional[str] = None
    sources: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "metadata": self.metadata.to_dict(),
            "responses": self.responses,
            "synthesis": self.synthesis,
            "sources": self.sources
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionData":
        """Tworzy obiekt z danych słownikowych"""
        metadata = SessionMetadata(**data["metadata"])
        return cls(
            metadata=metadata,
            responses=data.get("responses", []),
            synthesis=data.get("synthesis"),
            sources=data.get("sources", [])
        )


class SessionHistory:
    """
    Zarządza historią sesji narad
    """
    
    def __init__(self, sessions_dir: Path = SESSIONS_DIR):
        self.sessions_dir = sessions_dir
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_session_path(self, session_id: str) -> Path:
        """Zwraca ścieżkę do pliku sesji"""
        return self.sessions_dir / f"{session_id}.json"
    
    def save_session(self, session: SessionData) -> str:
        """
        Zapisuje sesję do pliku JSON
        
        Returns:
            ID sesji
        """
        session_path = self._get_session_path(session.metadata.id)
        
        with open(session_path, "w", encoding="utf-8") as f:
            json.dump(session.to_dict(), f, ensure_ascii=False, indent=2)
        
        return session.metadata.id
    
    def load_session(self, session_id: str) -> Optional[SessionData]:
        """
        Wczytuje sesję z pliku
        
        Returns:
            SessionData lub None jeśli nie znaleziono
        """
        session_path = self._get_session_path(session_id)
        
        if not session_path.exists():
            return None
        
        with open(session_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        return SessionData.from_dict(data)
    
    def list_sessions(
        self, 
        limit: int = 20, 
        council_type: Optional[str] = None
    ) -> List[SessionMetadata]:
        """
        Zwraca listę sesji (tylko metadane), posortowanych od najnowszej
        
        Args:
            limit: Maksymalna liczba sesji do zwrócenia
            council_type: Filtr typu rady ("standard", "historical")
        
        Returns:
            Lista metadanych sesji
        """
        sessions = []
        
        for session_file in self.sessions_dir.glob("*.json"):
            try:
                with open(session_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                metadata = SessionMetadata(**data["metadata"])
                
                # Filtruj po typie
                if council_type and metadata.council_type != council_type:
                    continue
                
                sessions.append(metadata)
            except (json.JSONDecodeError, KeyError):
                continue
        
        # Sortuj od najnowszej
        sessions.sort(key=lambda x: x.timestamp, reverse=True)
        
        return sessions[:limit]
    
    def delete_session(self, session_id: str) -> bool:
        """
        Usuwa sesję
        
        Returns:
            True jeśli usunięto, False jeśli nie znaleziono
        """
        session_path = self._get_session_path(session_id)
        
        if session_path.exists():
            session_path.unlink()
            return True
        return False
    
    def search_sessions(self, query: str, limit: int = 10) -> List[SessionMetadata]:
        """
        Wyszukuje sesje po treści zapytania
        
        Args:
            query: Tekst do wyszukania
            limit: Maksymalna liczba wyników
        
        Returns:
            Lista pasujących metadanych sesji
        """
        query_lower = query.lower()
        matches = []
        
        for session_file in self.sessions_dir.glob("*.json"):
            try:
                with open(session_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                # Szukaj w zapytaniu i syntezie
                if query_lower in data["metadata"]["query"].lower():
                    matches.append(SessionMetadata(**data["metadata"]))
                elif data.get("synthesis") and query_lower in data["synthesis"].lower():
                    matches.append(SessionMetadata(**data["metadata"]))
                    
            except (json.JSONDecodeError, KeyError):
                continue
        
        # Sortuj od najnowszej
        matches.sort(key=lambda x: x.timestamp, reverse=True)
        
        return matches[:limit]


def create_session_from_result(
    query: str,
    result: Any,  # HistoricalCouncilResult lub DeliberationResult
    council_type: str,
    agents_used: List[str],
    model: str,
    provider: str
) -> SessionData:
    """
    Tworzy obiekt SessionData z wyniku narady
    
    Args:
        query: Oryginalne pytanie
        result: Wynik narady (z dowolnego typu rady)
        council_type: "standard" lub "historical"
        agents_used: Lista ID użytych agentów
        model: Użyty model LLM
        provider: Użyty provider
    
    Returns:
        SessionData gotowy do zapisania
    """
    # Oblicz tokeny i koszt
    total_tokens = 0
    for resp in result.agent_responses:
        total_tokens += getattr(resp, 'total_tokens', 0)
    if result.synthesis:
        total_tokens += getattr(result.synthesis, 'total_tokens', 0)
    
    # Przelicz koszt (uproszczone)
    from src.llm_providers import calculate_cost
    cost = calculate_cost(model, total_tokens // 2, total_tokens // 2)
    
    metadata = SessionMetadata(
        id=str(uuid.uuid4()),
        timestamp=datetime.now().isoformat(),
        query=query,
        council_type=council_type,
        agents_used=agents_used,
        model=model,
        provider=provider,
        total_tokens=total_tokens,
        cost_usd=cost
    )
    
    responses = [
        {
            "agent_name": resp.agent_name,
            "role": resp.role,
            "content": resp.content
        }
        for resp in result.agent_responses
    ]
    
    return SessionData(
        metadata=metadata,
        responses=responses,
        synthesis=result.synthesis.content if result.synthesis else None,
        sources=result.sources if hasattr(result, 'sources') else []
    )


# Globalna instancja
session_history = SessionHistory()
