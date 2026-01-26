"""
Deep Competitor Analyzer
========================
Głęboka analiza konkurencji SEO:
- Scraping struktury nagłówków H1-H6
- Analiza długości treści
- Identyfikacja brakujących tematów przez NLP
"""

import re
import asyncio
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field
from collections import Counter
import httpx
from bs4 import BeautifulSoup


@dataclass
class HeadingNode:
    """Pojedynczy nagłówek z hierarchią"""
    level: int  # 1-6
    text: str
    children: List["HeadingNode"] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "level": self.level,
            "text": self.text,
            "children": [c.to_dict() for c in self.children]
        }


@dataclass
class CompetitorPage:
    """Dane o stronie konkurenta"""
    url: str
    title: str = ""
    meta_description: str = ""
    word_count: int = 0
    headings: List[HeadingNode] = field(default_factory=list)
    heading_texts: List[str] = field(default_factory=list)
    main_topics: List[str] = field(default_factory=list)
    content_snippet: str = ""
    fetch_error: str = ""


@dataclass
class CompetitorAnalysisResult:
    """Wynik analizy konkurencji"""
    keyword: str
    competitors: List[CompetitorPage] = field(default_factory=list)
    
    # Word count stats
    avg_word_count: int = 0
    min_word_count: int = 0
    max_word_count: int = 0
    recommended_word_count: int = 0
    
    # Common headings
    common_headings: List[str] = field(default_factory=list)
    common_heading_patterns: List[str] = field(default_factory=list)
    
    # Topic gaps
    all_topics: List[str] = field(default_factory=list)
    missing_topics: List[str] = field(default_factory=list)
    topic_frequency: Dict[str, int] = field(default_factory=dict)
    
    def to_context_string(self) -> str:
        """Formatuje jako kontekst dla LLM"""
        lines = [f"GŁĘBOKA ANALIZA KONKURENCJI DLA: {self.keyword}"]
        lines.append(f"Przeanalizowano {len(self.competitors)} stron konkurencji.\n")
        
        # Word count
        lines.append("DŁUGOŚĆ TREŚCI:")
        lines.append(f"- Średnia: {self.avg_word_count} słów")
        lines.append(f"- Zakres: {self.min_word_count} - {self.max_word_count} słów")
        lines.append(f"- Rekomendowana długość: {self.recommended_word_count}+ słów\n")
        
        # Common headings
        if self.common_headings:
            lines.append("POPULARNE NAGŁÓWKI (używane przez konkurencję):")
            for h in self.common_headings[:10]:
                lines.append(f"- {h}")
            lines.append("")
        
        # Topic gaps
        if self.missing_topics:
            lines.append("BRAKUJĄCE TEMATY (poruszone przez konkurencję):")
            for t in self.missing_topics[:10]:
                lines.append(f"- {t}")
        
        return "\n".join(lines)


class CompetitorAnalyzer:
    """
    Głęboka analiza stron konkurencji
    
    Features:
    - Scraping heading structure (H1-H6)
    - Word count analysis
    - NLP topic extraction
    - Gap identification
    """
    
    # Polskie stop words
    STOP_WORDS = {
        "i", "w", "z", "na", "do", "o", "się", "to", "jest", "nie",
        "co", "jak", "za", "po", "od", "ze", "że", "dla", "czy", "lub",
        "oraz", "ale", "też", "który", "która", "które", "tego", "tej",
        "tym", "tą", "te", "ten", "ta", "są", "być", "był", "była",
        "można", "więc", "tylko", "już", "przez", "przy", "tak", "gdy",
        "a", "an", "the", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will",
        "would", "could", "should", "may", "might", "must", "shall"
    }
    
    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout
    
    async def analyze_competitors(
        self,
        keyword: str,
        competitor_urls: List[str],
        our_content: str = ""
    ) -> CompetitorAnalysisResult:
        """
        Analizuje strony konkurencji
        
        Args:
            keyword: Słowo kluczowe
            competitor_urls: Lista URL-i konkurentów
            our_content: Nasza treść do porównania (opcjonalnie)
            
        Returns:
            CompetitorAnalysisResult z pełną analizą
        """
        result = CompetitorAnalysisResult(keyword=keyword)
        
        # 1. Pobierz i przeanalizuj każdą stronę
        tasks = [self._analyze_page(url) for url in competitor_urls[:10]]
        pages = await asyncio.gather(*tasks, return_exceptions=True)
        
        for page in pages:
            if isinstance(page, CompetitorPage) and not page.fetch_error:
                result.competitors.append(page)
        
        if not result.competitors:
            return result
        
        # 2. Analiza word count
        word_counts = [p.word_count for p in result.competitors if p.word_count > 0]
        if word_counts:
            result.avg_word_count = sum(word_counts) // len(word_counts)
            result.min_word_count = min(word_counts)
            result.max_word_count = max(word_counts)
            # Rekomenduj 10-20% więcej niż średnia
            result.recommended_word_count = int(result.avg_word_count * 1.15)
        
        # 3. Znajdź wspólne nagłówki
        result.common_headings = self._find_common_headings(result.competitors)
        result.common_heading_patterns = self._find_heading_patterns(result.competitors)
        
        # 4. Ekstrakcja tematów i gap analysis
        all_topics = self._extract_all_topics(result.competitors)
        result.all_topics = list(all_topics.keys())[:30]
        result.topic_frequency = dict(all_topics.most_common(30))
        
        # 5. Jeśli mamy naszą treść, znajdź brakujące tematy
        if our_content:
            our_topics = self._extract_topics_from_text(our_content)
            result.missing_topics = self._find_missing_topics(
                all_topics, our_topics
            )
        else:
            # Pokaż najpopularniejsze tematy
            result.missing_topics = [t for t, _ in all_topics.most_common(15)]
        
        return result
    
    async def _analyze_page(self, url: str) -> CompetitorPage:
        """Analizuje pojedynczą stronę"""
        page = CompetitorPage(url=url)
        
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (compatible; SEOBot/1.0)"}
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
                html = response.text
                
            soup = BeautifulSoup(html, "html.parser")
            
            # Title
            title_tag = soup.find("title")
            page.title = title_tag.get_text().strip() if title_tag else ""
            
            # Meta description
            meta_desc = soup.find("meta", attrs={"name": "description"})
            if meta_desc:
                page.meta_description = meta_desc.get("content", "")
            
            # Usuń niepotrzebne elementy
            for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
                tag.decompose()
            
            # Wyciągnij tekst
            main_content = soup.find("main") or soup.find("article") or soup.body
            if main_content:
                text = main_content.get_text(separator=" ", strip=True)
                page.word_count = len(text.split())
                page.content_snippet = text[:500]
                
                # Wyciągnij tematy
                page.main_topics = self._extract_topics_from_text(text)[:10]
            
            # Wyciągnij nagłówki
            page.headings = self._extract_headings(soup)
            page.heading_texts = self._flatten_headings(page.headings)
            
        except Exception as e:
            page.fetch_error = str(e)
        
        return page
    
    def _extract_headings(self, soup: BeautifulSoup) -> List[HeadingNode]:
        """Wyciąga hierarchię nagłówków"""
        headings = []
        
        for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
            level = int(tag.name[1])
            text = tag.get_text().strip()
            if text:
                headings.append(HeadingNode(level=level, text=text))
        
        return headings
    
    def _flatten_headings(self, headings: List[HeadingNode]) -> List[str]:
        """Spłaszcza nagłówki do listy tekstów"""
        texts = []
        for h in headings:
            texts.append(h.text)
            texts.extend(self._flatten_headings(h.children))
        return texts
    
    def _find_common_headings(self, pages: List[CompetitorPage]) -> List[str]:
        """Znajduje wspólne/podobne nagłówki"""
        all_headings = []
        for page in pages:
            all_headings.extend(page.heading_texts)
        
        # Normalizuj i licz
        normalized = Counter()
        for h in all_headings:
            # Normalizacja: lowercase, usuń liczby
            norm = re.sub(r'\d+', '', h.lower()).strip()
            if len(norm) > 3:
                normalized[norm] += 1
        
        # Zwróć te, które pojawiają się w >1 stronie
        common = [h for h, count in normalized.most_common(20) if count > 1]
        return common
    
    def _find_heading_patterns(self, pages: List[CompetitorPage]) -> List[str]:
        """Znajduje wzorce nagłówków"""
        patterns = []
        
        # Szukaj wzorców typu "Jak...", "Co to...", "Najlepsze..."
        pattern_starters = [
            r'^jak\s+',
            r'^co\s+to\s+',
            r'^dlaczego\s+',
            r'^najlepsze?\s+',
            r'^poradnik\s+',
            r'^przewodnik\s+',
            r'^\d+\s+',  # "10 sposobów..."
            r'^top\s+\d+',
        ]
        
        for page in pages:
            for heading in page.heading_texts:
                h_lower = heading.lower()
                for pattern in pattern_starters:
                    if re.match(pattern, h_lower):
                        patterns.append(heading)
                        break
        
        return list(set(patterns))[:10]
    
    def _extract_topics_from_text(self, text: str) -> List[str]:
        """Wyciąga główne tematy z tekstu (proste NLP)"""
        # Tokenizacja
        words = re.findall(r'\b[a-ząćęłńóśźżA-ZĄĆĘŁŃÓŚŹŻ]{4,}\b', text.lower())
        
        # Usuń stop words
        words = [w for w in words if w not in self.STOP_WORDS]
        
        # Licz częstość
        freq = Counter(words)
        
        # Zwróć top tematy
        return [word for word, _ in freq.most_common(20)]
    
    def _extract_all_topics(self, pages: List[CompetitorPage]) -> Counter:
        """Wyciąga tematy ze wszystkich stron"""
        all_topics = Counter()
        
        for page in pages:
            # Z nagłówków (ważniejsze)
            for heading in page.heading_texts:
                topics = self._extract_topics_from_text(heading)
                for t in topics:
                    all_topics[t] += 2  # Waga 2 dla nagłówków
            
            # Z main topics
            for t in page.main_topics:
                all_topics[t] += 1
        
        return all_topics
    
    def _find_missing_topics(
        self,
        competitor_topics: Counter,
        our_topics: List[str]
    ) -> List[str]:
        """Znajduje tematy, które ma konkurencja, a my nie"""
        our_set = set(our_topics)
        
        missing = []
        for topic, count in competitor_topics.most_common(30):
            if topic not in our_set and count >= 2:
                missing.append(topic)
        
        return missing[:15]
    
    def generate_recommendations(
        self,
        result: CompetitorAnalysisResult
    ) -> List[str]:
        """Generuje rekomendacje na podstawie analizy"""
        recommendations = []
        
        # Word count
        if result.recommended_word_count:
            recommendations.append(
                f"📝 Napisz minimum {result.recommended_word_count} słów "
                f"(średnia konkurencji: {result.avg_word_count})"
            )
        
        # Missing topics
        if result.missing_topics:
            topics_str = ", ".join(result.missing_topics[:5])
            recommendations.append(
                f"🎯 Uwzględnij brakujące tematy: {topics_str}"
            )
        
        # Common headings
        if result.common_headings:
            recommendations.append(
                f"📌 Popularne nagłówki u konkurencji: rozważ podobne sekcje"
            )
        
        return recommendations


async def analyze_competitors_with_serp(
    keyword: str,
    serp_urls: List[str],
    our_content: str = ""
) -> CompetitorAnalysisResult:
    """
    Convenience function - analizuje konkurencję z wyników SERP
    """
    analyzer = CompetitorAnalyzer()
    return await analyzer.analyze_competitors(
        keyword=keyword,
        competitor_urls=serp_urls,
        our_content=our_content
    )


if __name__ == "__main__":
    async def test():
        analyzer = CompetitorAnalyzer()
        
        # Test z przykładowymi URL-ami
        test_urls = [
            "https://www.nazwa.pl/hosting/wordpress/",
        ]
        
        result = await analyzer.analyze_competitors(
            keyword="hosting wordpress",
            competitor_urls=test_urls
        )
        
        print(result.to_context_string())
        print("\nRekomendacje:")
        for rec in analyzer.generate_recommendations(result):
            print(f"  {rec}")
    
    asyncio.run(test())
