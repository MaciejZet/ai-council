"""
Ahrefs Data Importer
====================
Import danych z eksportów Ahrefs (bez bezpośredniej integracji API)
Obsługuje CSV i wklejany tekst z tabel
"""

import re
import csv
import io
from typing import List, Dict, Optional
from dataclasses import dataclass, field


@dataclass
class KeywordData:
    """Pojedynczy keyword z metrykami"""
    keyword: str
    volume: int = 0
    difficulty: int = 0  # KD (Keyword Difficulty)
    cpc: float = 0.0
    cps: float = 0.0  # Clicks Per Search
    parent_topic: str = ""
    intent: str = ""  # informational, commercial, transactional, navigational


@dataclass
class AhrefsData:
    """Zaimportowane dane z Ahrefs"""
    keywords: List[KeywordData] = field(default_factory=list)
    source: str = ""  # "csv" lub "text"
    raw_import: str = ""
    
    def get_primary_keywords(self, min_volume: int = 100) -> List[str]:
        """Zwraca główne słowa kluczowe (high volume)"""
        return [kw.keyword for kw in self.keywords if kw.volume >= min_volume]
    
    def get_long_tail(self, max_volume: int = 100) -> List[str]:
        """Zwraca long-tail keywords (low volume)"""
        return [kw.keyword for kw in self.keywords if 0 < kw.volume < max_volume]
    
    def get_low_difficulty(self, max_kd: int = 30) -> List[str]:
        """Zwraca keywords z niską trudnością"""
        return [kw.keyword for kw in self.keywords if kw.difficulty <= max_kd]
    
    def to_context_string(self) -> str:
        """Formatuje jako kontekst dla LLM"""
        if not self.keywords:
            return ""
        
        lines = ["SŁOWA KLUCZOWE Z AHREFS:"]
        
        # Sortuj po volume
        sorted_kw = sorted(self.keywords, key=lambda x: x.volume, reverse=True)
        
        for kw in sorted_kw[:20]:  # Max 20 keywords
            line = f"- {kw.keyword}"
            if kw.volume:
                line += f" (vol: {kw.volume}"
                if kw.difficulty:
                    line += f", KD: {kw.difficulty}"
                line += ")"
            lines.append(line)
        
        return "\n".join(lines)


class AhrefsImporter:
    """
    Importuje dane z eksportów Ahrefs
    
    Supported formats:
    - CSV export (Keywords Explorer, Site Explorer)
    - Pasted text from Ahrefs tables (tab-separated)
    """
    
    # Mapowanie nagłówków Ahrefs na nasze pola
    HEADER_MAP = {
        "keyword": "keyword",
        "keywords": "keyword",
        "search query": "keyword",
        "volume": "volume",
        "search volume": "volume",
        "global volume": "volume",
        "difficulty": "difficulty",
        "kd": "difficulty",
        "keyword difficulty": "difficulty",
        "cpc": "cpc",
        "cpc (usd)": "cpc",
        "cps": "cps",
        "clicks per search": "cps",
        "parent topic": "parent_topic",
        "intent": "intent",
        "sf": "intent"  # Search Features sometimes used for intent
    }
    
    def parse_csv(self, content: str) -> AhrefsData:
        """
        Parsuje eksport CSV z Ahrefs
        
        Args:
            content: Zawartość pliku CSV
            
        Returns:
            AhrefsData z zaimportowanymi keywordami
        """
        keywords = []
        
        try:
            reader = csv.DictReader(io.StringIO(content))
            
            # Mapuj nagłówki
            field_map = {}
            if reader.fieldnames:
                for header in reader.fieldnames:
                    normalized = header.lower().strip()
                    if normalized in self.HEADER_MAP:
                        field_map[header] = self.HEADER_MAP[normalized]
            
            for row in reader:
                kw_data = self._extract_keyword_from_row(row, field_map)
                if kw_data:
                    keywords.append(kw_data)
                    
        except csv.Error:
            # Fallback do tekstu tab-separated
            return self.parse_text(content)
        
        return AhrefsData(
            keywords=keywords,
            source="csv",
            raw_import=content[:1000]  # Zachowaj sample
        )
    
    def parse_text(self, content: str) -> AhrefsData:
        """
        Parsuje wklejony tekst z tabeli Ahrefs
        (najczęściej tab-separated po skopiowaniu z przeglądarki)
        
        Args:
            content: Wklejony tekst
            
        Returns:
            AhrefsData z zaimportowanymi keywordami
        """
        keywords = []
        lines = content.strip().split("\n")
        
        if not lines:
            return AhrefsData(source="text", raw_import=content)
        
        # Sprawdź czy pierwsza linia to nagłówki
        first_line = lines[0].lower()
        has_header = any(h in first_line for h in ["keyword", "volume", "difficulty"])
        
        # Próbuj wykryć separator
        separator = self._detect_separator(lines[0])
        
        # Parsuj nagłówki
        field_map = {}
        start_idx = 0
        if has_header:
            headers = lines[0].split(separator)
            for i, header in enumerate(headers):
                normalized = header.lower().strip()
                if normalized in self.HEADER_MAP:
                    field_map[i] = self.HEADER_MAP[normalized]
            start_idx = 1
        else:
            # Bez nagłówków - zakładamy: keyword, volume, difficulty
            field_map = {0: "keyword", 1: "volume", 2: "difficulty"}
        
        for line in lines[start_idx:]:
            if not line.strip():
                continue
            
            parts = line.split(separator)
            kw_data = self._extract_keyword_from_parts(parts, field_map)
            if kw_data:
                keywords.append(kw_data)
        
        return AhrefsData(
            keywords=keywords,
            source="text",
            raw_import=content[:1000]
        )
    
    def _detect_separator(self, line: str) -> str:
        """Wykrywa separator (tab, comma, semicolon)"""
        if "\t" in line:
            return "\t"
        elif ";" in line:
            return ";"
        elif "," in line and line.count(",") > 1:
            return ","
        return "\t"  # Default
    
    def _extract_keyword_from_row(self, row: Dict, field_map: Dict[str, str]) -> Optional[KeywordData]:
        """Ekstraktuje KeywordData z wiersza CSV"""
        data = {}
        
        for orig_header, our_field in field_map.items():
            if orig_header in row:
                data[our_field] = row[orig_header]
        
        if "keyword" not in data or not data["keyword"]:
            return None
        
        return KeywordData(
            keyword=str(data.get("keyword", "")).strip(),
            volume=self._parse_int(data.get("volume", 0)),
            difficulty=self._parse_int(data.get("difficulty", 0)),
            cpc=self._parse_float(data.get("cpc", 0)),
            cps=self._parse_float(data.get("cps", 0)),
            parent_topic=str(data.get("parent_topic", "")),
            intent=str(data.get("intent", ""))
        )
    
    def _extract_keyword_from_parts(self, parts: List[str], field_map: Dict[int, str]) -> Optional[KeywordData]:
        """Ekstraktuje KeywordData z listy części"""
        data = {}
        
        for idx, field_name in field_map.items():
            if idx < len(parts):
                data[field_name] = parts[idx].strip()
        
        if "keyword" not in data or not data["keyword"]:
            return None
        
        return KeywordData(
            keyword=str(data.get("keyword", "")).strip(),
            volume=self._parse_int(data.get("volume", 0)),
            difficulty=self._parse_int(data.get("difficulty", 0)),
            cpc=self._parse_float(data.get("cpc", 0)),
            cps=self._parse_float(data.get("cps", 0)),
            parent_topic=str(data.get("parent_topic", "")),
            intent=str(data.get("intent", ""))
        )
    
    def _parse_int(self, value) -> int:
        """Parsuje int z różnych formatów (1,000 -> 1000)"""
        if isinstance(value, int):
            return value
        if not value:
            return 0
        
        # Usuń separatory tysięcy i inne znaki
        cleaned = re.sub(r"[^\d]", "", str(value))
        try:
            return int(cleaned) if cleaned else 0
        except ValueError:
            return 0
    
    def _parse_float(self, value) -> float:
        """Parsuje float z różnych formatów ($1.50 -> 1.50)"""
        if isinstance(value, (int, float)):
            return float(value)
        if not value:
            return 0.0
        
        # Usuń walutę i inne znaki
        cleaned = re.sub(r"[^\d.]", "", str(value))
        try:
            return float(cleaned) if cleaned else 0.0
        except ValueError:
            return 0.0


if __name__ == "__main__":
    # Test parser
    importer = AhrefsImporter()
    
    # Test tab-separated text
    test_text = """Keyword\tVolume\tKD
hosting wordpress\t5000\t35
najlepszy hosting\t3000\t28
tani hosting\t1500\t22
hosting dla bloga\t800\t18"""
    
    result = importer.parse_text(test_text)
    print(f"Zaimportowano {len(result.keywords)} keywords:")
    for kw in result.keywords:
        print(f"  - {kw.keyword}: vol={kw.volume}, KD={kw.difficulty}")
    
    print(f"\nKontekst dla LLM:\n{result.to_context_string()}")
