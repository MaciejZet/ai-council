"""
Brand Info Manager
==================
Zarządzanie informacjami o marce/firmie dla kontekstu artykułów SEO
"""

import json
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass, field, asdict


@dataclass
class BrandInfo:
    """Dane o marce/firmie do wplatania w artykuły"""
    name: str = ""
    description: str = ""
    value_proposition: str = ""
    tone_of_voice: str = "professional"  # professional, friendly, expert, casual
    key_products: List[str] = field(default_factory=list)
    target_audience: str = ""
    unique_selling_points: List[str] = field(default_factory=list)
    preferred_cta: str = ""
    do_not_mention: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "BrandInfo":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class BrandInfoManager:
    """Zarządza danymi o marce (load/save do JSON)"""
    
    DEFAULT_PATH = Path(__file__).parent.parent.parent / "data" / "brand_info.json"
    
    def __init__(self, path: Optional[Path] = None):
        self.path = path or self.DEFAULT_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
    
    def load(self) -> BrandInfo:
        """Wczytuje dane o marce z pliku JSON"""
        if not self.path.exists():
            # Zwróć domyślne puste dane
            return BrandInfo()
        
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return BrandInfo.from_dict(data)
        except (json.JSONDecodeError, IOError):
            return BrandInfo()
    
    def save(self, info: BrandInfo) -> bool:
        """Zapisuje dane o marce do pliku JSON"""
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(info.to_dict(), f, ensure_ascii=False, indent=2)
            return True
        except IOError:
            return False
    
    def update(self, updates: dict) -> BrandInfo:
        """Aktualizuje wybrane pola"""
        current = self.load()
        for key, value in updates.items():
            if hasattr(current, key):
                setattr(current, key, value)
        self.save(current)
        return current
    
    def get_context_prompt(self) -> str:
        """
        Generuje prompt do wstrzyknięcia kontekstu marki dla LLM.
        Zwraca pusty string jeśli brak danych o marce.
        """
        info = self.load()
        
        # Jeśli brak nazwy - brak kontekstu
        if not info.name:
            return ""
        
        sections = []
        sections.append(f"INFORMACJE O MARCE: {info.name}")
        
        if info.description:
            sections.append(f"Opis: {info.description}")
        
        if info.value_proposition:
            sections.append(f"Propozycja wartości: {info.value_proposition}")
        
        if info.target_audience:
            sections.append(f"Grupa docelowa: {info.target_audience}")
        
        if info.key_products:
            sections.append(f"Główne produkty/usługi: {', '.join(info.key_products)}")
        
        if info.unique_selling_points:
            sections.append(f"USP: {', '.join(info.unique_selling_points)}")
        
        if info.preferred_cta:
            sections.append(f"Preferowane CTA: {info.preferred_cta}")
        
        if info.tone_of_voice:
            tone_map = {
                "professional": "profesjonalny, rzeczowy",
                "friendly": "przyjazny, przystępny",
                "expert": "ekspercki, autorytatywny",
                "casual": "swobodny, konwersacyjny"
            }
            tone_desc = tone_map.get(info.tone_of_voice, info.tone_of_voice)
            sections.append(f"Ton komunikacji: {tone_desc}")
        
        if info.do_not_mention:
            sections.append(f"NIE WSPOMINAJ O: {', '.join(info.do_not_mention)}")
        
        return "\n".join(sections)


if __name__ == "__main__":
    # Test
    manager = BrandInfoManager()
    
    # Utwórz przykładowe dane
    info = BrandInfo(
        name="CometWeb",
        description="Agencja digital marketingowa",
        value_proposition="Zwiększamy sprzedaż przez marketing online",
        tone_of_voice="professional",
        key_products=["SEO", "Google Ads", "Social Media"],
        target_audience="Małe i średnie firmy B2B",
        unique_selling_points=["15 lat doświadczenia", "Gwarancja wyników"],
        preferred_cta="Skontaktuj się z nami",
        do_not_mention=["konkurencja X", "stare usługi"]
    )
    
    manager.save(info)
    print("Zapisano dane marki")
    
    loaded = manager.load()
    print(f"Wczytano: {loaded.name}")
    
    prompt = manager.get_context_prompt()
    print(f"\nPrompt kontekstowy:\n{prompt}")
