"""
SERP Analyzer
=============
Analiza konkurencji w wynikach wyszukiwania Google
Wykorzystuje Tavily lub DuckDuckGo do uzyskania SERP
"""

import os
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class CompetitorArticle:
    """Artykuł konkurencji z SERP"""
    title: str
    url: str
    snippet: str
    position: int = 0
    domain: str = ""
    headings: List[str] = field(default_factory=list)
    word_count: int = 0
    content_preview: str = ""


@dataclass
class SERPAnalysisResult:
    """Wynik analizy SERP"""
    keyword: str
    competitors: List[CompetitorArticle] = field(default_factory=list)
    common_themes: List[str] = field(default_factory=list)
    content_gaps: List[str] = field(default_factory=list)
    suggested_angles: List[str] = field(default_factory=list)
    avg_word_count: int = 0
    
    def to_context_string(self) -> str:
        """Formatuje jako kontekst dla LLM"""
        if not self.competitors:
            return ""
        
        lines = [f"ANALIZA SERP DLA: {self.keyword}"]
        lines.append(f"Znaleziono {len(self.competitors)} konkurencyjnych artykułów.\n")
        
        lines.append("KONKURENCJA:")
        for i, comp in enumerate(self.competitors[:5], 1):
            lines.append(f"{i}. {comp.title}")
            lines.append(f"   URL: {comp.domain}")
            if comp.snippet:
                lines.append(f"   Snippet: {comp.snippet[:150]}...")
        
        if self.common_themes:
            lines.append(f"\nWSPÓLNE TEMATY: {', '.join(self.common_themes)}")
        
        if self.content_gaps:
            lines.append(f"\nLUKI CONTENTOWE (co brakuje konkurencji): {', '.join(self.content_gaps)}")
        
        if self.suggested_angles:
            lines.append(f"\nSUGEROWANE KĄTY: {', '.join(self.suggested_angles)}")
        
        if self.avg_word_count:
            lines.append(f"\nŚrednia długość artykułów: ~{self.avg_word_count} słów")
        
        return "\n".join(lines)


class SERPAnalyzer:
    """
    Analizuje wyniki SERP dla danego słowa kluczowego
    
    Features:
    - Top 10 results via Tavily/DuckDuckGo
    - Content gap analysis
    - Common headings extraction (via URL analysis)
    - Unique angle suggestions
    """
    
    def __init__(self, use_tavily: bool = True):
        self.use_tavily = use_tavily and bool(os.getenv("TAVILY_API_KEY"))
    
    async def analyze(
        self,
        keyword: str,
        location: str = "pl",
        max_competitors: int = 5
    ) -> SERPAnalysisResult:
        """
        Analizuje SERP dla słowa kluczowego
        
        Args:
            keyword: Słowo kluczowe do analizy
            location: Kod kraju (pl, en, de, etc.)
            max_competitors: Maksymalna liczba konkurentów do analizy
            
        Returns:
            SERPAnalysisResult z danymi o konkurencji
        """
        # Pobierz wyniki wyszukiwania
        if self.use_tavily:
            search_results = await self._search_tavily(keyword, max_competitors)
        else:
            search_results = await self._search_duckduckgo(keyword, max_competitors)
        
        if not search_results:
            return SERPAnalysisResult(keyword=keyword)
        
        # Konwertuj na CompetitorArticle
        competitors = []
        for i, result in enumerate(search_results, 1):
            competitors.append(CompetitorArticle(
                title=result.get("title", ""),
                url=result.get("url", ""),
                snippet=result.get("snippet", ""),
                position=i,
                domain=self._extract_domain(result.get("url", ""))
            ))
        
        # Analiza tematów i luk
        common_themes = self._extract_common_themes(competitors)
        content_gaps = self._identify_content_gaps(keyword, competitors)
        suggested_angles = self._suggest_unique_angles(keyword, competitors)
        
        return SERPAnalysisResult(
            keyword=keyword,
            competitors=competitors,
            common_themes=common_themes,
            content_gaps=content_gaps,
            suggested_angles=suggested_angles,
            avg_word_count=1500  # Estimate, could be improved with content analysis
        )
    
    async def _search_tavily(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Wyszukiwanie przez Tavily API"""
        import httpx
        
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            return []
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": api_key,
                        "query": query,
                        "max_results": max_results,
                        "search_depth": "advanced",
                        "include_answer": True
                    }
                )
                response.raise_for_status()
                data = response.json()
                
                results = []
                for item in data.get("results", []):
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "snippet": item.get("content", "")[:300]
                    })
                
                return results
                
        except Exception as e:
            print(f"Tavily search error: {e}")
            return []
    
    async def _search_duckduckgo(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Fallback wyszukiwanie przez DuckDuckGo"""
        import httpx
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    "https://api.duckduckgo.com/",
                    params={
                        "q": query,
                        "format": "json",
                        "no_html": 1
                    }
                )
                response.raise_for_status()
                data = response.json()
                
                results = []
                
                # Abstract
                if data.get("Abstract"):
                    results.append({
                        "title": data.get("Heading", ""),
                        "url": data.get("AbstractURL", ""),
                        "snippet": data.get("Abstract", "")
                    })
                
                # Related topics
                for topic in data.get("RelatedTopics", [])[:max_results]:
                    if isinstance(topic, dict) and topic.get("Text"):
                        results.append({
                            "title": topic.get("Text", "")[:100],
                            "url": topic.get("FirstURL", ""),
                            "snippet": topic.get("Text", "")
                        })
                
                return results[:max_results]
                
        except Exception as e:
            print(f"DuckDuckGo search error: {e}")
            return []
    
    def _extract_domain(self, url: str) -> str:
        """Wyciąga domenę z URL"""
        from urllib.parse import urlparse
        try:
            parsed = urlparse(url)
            return parsed.netloc
        except:
            return ""
    
    def _extract_common_themes(self, competitors: List[CompetitorArticle]) -> List[str]:
        """Identyfikuje wspólne tematy w tytułach i snippetach"""
        themes = []
        
        # Proste podejście: znajdź powtarzające się słowa
        all_text = " ".join([
            f"{c.title} {c.snippet}" for c in competitors
        ]).lower()
        
        # Popularne słowa związane z contentem
        theme_keywords = [
            "poradnik", "jak", "najlepszy", "porównanie", "recenzja",
            "2024", "2025", "kompletny", "przewodnik", "lista",
            "krok po kroku", "dla początkujących", "zaawansowany"
        ]
        
        for kw in theme_keywords:
            if kw in all_text:
                themes.append(kw)
        
        return themes[:5]
    
    def _identify_content_gaps(
        self, 
        keyword: str, 
        competitors: List[CompetitorArticle]
    ) -> List[str]:
        """Identyfikuje luki contentowe"""
        gaps = []
        
        all_content = " ".join([c.snippet.lower() for c in competitors])
        
        # Potencjalne luki - tematy które mogą brakować
        potential_gaps = [
            ("case study", "brak case studies / przykładów z życia"),
            ("cena", "brak porównania cen"),
            ("opinia", "brak opinii użytkowników"),
            ("alternatyw", "brak alternatyw"),
            ("wad", "brak omówienia wad"),
            ("dla kogo", "brak określenia grupy docelowej"),
            ("2025", "brak aktualnych informacji"),
            ("video", "brak materiałów video"),
            ("check", "brak checklisty / podsumowania")
        ]
        
        for check, gap_name in potential_gaps:
            if check not in all_content:
                gaps.append(gap_name)
        
        return gaps[:5]
    
    def _suggest_unique_angles(
        self, 
        keyword: str, 
        competitors: List[CompetitorArticle]
    ) -> List[str]:
        """Sugeruje unikalne kąty dla artykułu"""
        suggestions = [
            f"Głęboka analiza {keyword} z perspektywy eksperta",
            f"Aktualne trendy w {keyword} na 2025",
            f"Mało znane fakty o {keyword}",
            f"{keyword} - przewodnik z case studies",
            f"Błędy które popełniają początkujący w {keyword}"
        ]
        
        # Dodaj sugestie bazując na lukach
        return suggestions[:3]


async def analyze_serp_with_llm(
    keyword: str,
    serp_result: SERPAnalysisResult,
    llm_provider
) -> SERPAnalysisResult:
    """
    Wzbogaca analizę SERP przez LLM
    
    Args:
        keyword: Słowo kluczowe
        serp_result: Wstępna analiza
        llm_provider: Provider LLM (OpenAI, etc.)
        
    Returns:
        Wzbogacona analiza
    """
    if not serp_result.competitors:
        return serp_result
    
    # Przygotuj prompt
    competitor_info = "\n".join([
        f"- {c.title}: {c.snippet[:150]}"
        for c in serp_result.competitors[:5]
    ])
    
    prompt = f"""Analizuję konkurencję SERP dla słowa kluczowego: "{keyword}"

Znalezieni konkurenci:
{competitor_info}

Na podstawie powyższych danych:
1. Zidentyfikuj 3 główne tematy poruszane przez konkurencję
2. Wskaż 3 luki contentowe - czego brakuje konkurencji?
3. Zaproponuj 3 unikalne kąty/podejścia dla nowego artykułu

Odpowiedz w formacie JSON:
{{
    "common_themes": ["temat1", "temat2", "temat3"],
    "content_gaps": ["luka1", "luka2", "luka3"],
    "suggested_angles": ["kąt1", "kąt2", "kąt3"]
}}"""

    try:
        response = await llm_provider.generate(
            system_prompt="Jesteś ekspertem SEO. Analizujesz konkurencję SERP.",
            user_prompt=prompt,
            temperature=0.3
        )

        import json
        import re

        raw = response.content.strip()
        json_blob = raw
        fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
        if fence:
            json_blob = fence.group(1).strip()
        start, end = json_blob.find("{"), json_blob.rfind("}")
        if start != -1 and end != -1 and end > start:
            data = json.loads(json_blob[start : end + 1])
            serp_result.common_themes = data.get("common_themes", serp_result.common_themes)
            serp_result.content_gaps = data.get("content_gaps", serp_result.content_gaps)
            serp_result.suggested_angles = data.get("suggested_angles", serp_result.suggested_angles)

    except Exception as e:
        print(f"LLM SERP analysis error: {e}")
    
    return serp_result


if __name__ == "__main__":
    import asyncio
    
    async def test():
        analyzer = SERPAnalyzer(use_tavily=False)  # Use DuckDuckGo for test
        
        result = await analyzer.analyze("hosting wordpress")
        print(result.to_context_string())
    
    asyncio.run(test())
