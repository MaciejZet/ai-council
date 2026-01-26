"""
SEO Article Generator
=====================
Główny generator artykułów zoptymalizowanych pod SEO/AIEO
"""

import os
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime

from .brand_info import BrandInfoManager
from .ahrefs_importer import AhrefsImporter, AhrefsData
from .article_storage import ArticleStorage, Article, ArticleMeta
from .serp_analyzer import SERPAnalyzer, SERPAnalysisResult
from .schema_generator import (
    SchemaGenerator, SchemaOutput,
    TableOfContentsGenerator,
    FeaturedSnippetOptimizer
)


@dataclass
class ArticleResult:
    """Wynik generowania artykułu"""
    success: bool
    article: Optional[Article] = None
    article_html: str = ""
    article_markdown: str = ""
    similar_exists: bool = False
    similar_articles: List[ArticleMeta] = field(default_factory=list)
    serp_analysis: Optional[SERPAnalysisResult] = None
    error: str = ""
    usage: Dict[str, Any] = field(default_factory=dict)
    # SEO Structure Features
    schema_json_ld: str = ""
    schema_html_script: str = ""
    table_of_contents: Dict[str, Any] = field(default_factory=dict)
    featured_snippet_suggestions: Dict[str, Any] = field(default_factory=dict)


class ArticleGenerator:
    """
    Generator artykułów SEO/AIEO
    
    Pipeline:
    1. Analyze target URL (theme, structure, existing content)
    2. Research competitors via SERP analysis
    3. Check for similar existing articles (Pinecone)
    4. Generate outline with unique angles
    5. Enrich with Perplexity for current facts
    6. Generate final article with brand voice
    """
    
    def __init__(self):
        self.brand_manager = BrandInfoManager()
        self.ahrefs_importer = AhrefsImporter()
        self.article_storage = ArticleStorage()
        self.serp_analyzer = SERPAnalyzer()
        self.schema_generator = SchemaGenerator()
        self.toc_generator = TableOfContentsGenerator()
        self.snippet_optimizer = FeaturedSnippetOptimizer()
    
    async def generate(
        self,
        topic: str,
        target_url: str = "",
        keywords: List[str] = None,
        ahrefs_data: str = "",
        min_words: int = 1500,
        include_brand_info: bool = True,
        analyze_serp: bool = True,
        perplexity_model: str = "sonar-pro",
        main_llm_provider = None,
        force_generate: bool = False
    ) -> ArticleResult:
        """
        Generuje artykuł SEO
        
        Args:
            topic: Temat artykułu
            target_url: URL strony docelowej (do analizy kontekstu)
            keywords: Lista słów kluczowych
            ahrefs_data: Dane z Ahrefs (CSV lub tekst)
            min_words: Minimalna liczba słów
            include_brand_info: Czy uwzględnić dane marki
            analyze_serp: Czy analizować konkurencję SERP
            perplexity_model: Model Perplexity (sonar/sonar-pro)
            main_llm_provider: Provider LLM do generowania artykułu
            force_generate: Generuj nawet jeśli podobny artykuł istnieje
            
        Returns:
            ArticleResult z wygenerowanym artykułem
        """
        keywords = keywords or []
        result = ArticleResult(success=False)
        total_tokens = 0
        
        try:
            # 1. Sprawdź czy podobny artykuł już istnieje
            similar = await self.article_storage.find_similar(topic, threshold=0.85)
            if similar and not force_generate:
                result.similar_exists = True
                result.similar_articles = similar
                result.error = f"Znaleziono {len(similar)} podobnych artykułów. Użyj force_generate=True aby kontynuować."
                return result
            
            # 2. Parsuj dane Ahrefs jeśli podane
            ahrefs_parsed: Optional[AhrefsData] = None
            if ahrefs_data:
                if "," in ahrefs_data and "\n" in ahrefs_data:
                    ahrefs_parsed = self.ahrefs_importer.parse_csv(ahrefs_data)
                else:
                    ahrefs_parsed = self.ahrefs_importer.parse_text(ahrefs_data)
                
                # Dodaj keywords z Ahrefs
                if ahrefs_parsed:
                    keywords.extend(ahrefs_parsed.get_primary_keywords())
            
            # 3. Analiza SERP
            serp_result: Optional[SERPAnalysisResult] = None
            if analyze_serp:
                serp_result = await self.serp_analyzer.analyze(
                    topic,
                    max_competitors=5
                )
                result.serp_analysis = serp_result
            
            # 4. Pobierz kontekst marki
            brand_context = ""
            if include_brand_info:
                brand_context = self.brand_manager.get_context_prompt()
            
            # 5. Analiza strony docelowej (jeśli podana)
            target_context = ""
            if target_url:
                target_context = await self._analyze_target_url(target_url)
            
            # 6. Research przez Perplexity
            research_context = ""
            if perplexity_model:
                research_context = await self._research_with_perplexity(
                    topic, 
                    keywords[:5],
                    perplexity_model
                )
            
            # 7. Wygeneruj artykuł
            if main_llm_provider is None:
                from src.llm_providers import OpenAIProvider
                main_llm_provider = OpenAIProvider(model="gpt-4o")
            
            article_content, usage = await self._generate_article_content(
                topic=topic,
                keywords=keywords,
                brand_context=brand_context,
                target_context=target_context,
                serp_context=serp_result.to_context_string() if serp_result else "",
                ahrefs_context=ahrefs_parsed.to_context_string() if ahrefs_parsed else "",
                research_context=research_context,
                min_words=min_words,
                llm_provider=main_llm_provider
            )
            
            total_tokens += usage.get("total_tokens", 0)
            
            # 8. Konwertuj na HTML
            article_html = self._markdown_to_html(article_content)
            
            # 9. Utwórz obiekt artykułu
            article = Article(
                id="",  # Zostanie wygenerowany przy zapisie
                title=self._extract_title(article_content),
                content=article_content,
                content_html=article_html,
                topic=topic,
                target_url=target_url,
                keywords=keywords[:10],
                word_count=len(article_content.split())
            )
            
            # 10. Zapisz do Pinecone
            article.id = await self.article_storage.store(article)
            
            # 11. Generuj Schema JSON-LD
            brand_info = self.brand_manager.load()
            schema_output = self.schema_generator.generate_all(
                title=article.title,
                content=article_content,
                content_html=article_html,
                author=brand_info.name if brand_info.name else "",
                article_url=target_url,
                description=self._extract_description(article_content)
            )
            
            # 12. Generuj Table of Contents
            toc_data = self.toc_generator.generate(article_content)
            
            # 13. Dodaj anchory do treści
            article_content_with_anchors = self.toc_generator.add_anchors_to_content(article_content)
            article_html_with_anchors = self._markdown_to_html(article_content_with_anchors)
            
            # 14. Analiza Featured Snippet
            primary_keyword = keywords[0] if keywords else topic
            snippet_analysis = self.snippet_optimizer.optimize(article_content, primary_keyword)
            
            result.success = True
            result.article = article
            result.article_html = article_html_with_anchors
            result.article_markdown = article_content_with_anchors
            result.usage = {"total_tokens": total_tokens}
            result.schema_json_ld = schema_output.to_json_ld()
            result.schema_html_script = schema_output.to_html_script()
            result.table_of_contents = toc_data
            result.featured_snippet_suggestions = snippet_analysis
            
        except Exception as e:
            result.error = str(e)
        
        return result
    
    async def _analyze_target_url(self, url: str) -> str:
        """Analizuje stronę docelową"""
        from src.plugins.url_analyzer import URLAnalyzerPlugin
        
        analyzer = URLAnalyzerPlugin()
        result = await analyzer.execute(url, max_content_length=3000)
        
        if result.success and result.data:
            return f"""KONTEKST STRONY DOCELOWEJ:
Tytuł: {result.data.get('title', '')}
Opis: {result.data.get('description', '')}
Treść (fragment): {result.data.get('content', '')[:1000]}"""
        
        return ""
    
    async def _research_with_perplexity(
        self, 
        topic: str, 
        keywords: List[str],
        model: str = "sonar-pro"
    ) -> str:
        """Badanie tematu przez Perplexity"""
        from src.llm_providers import PerplexityProvider
        
        try:
            provider = PerplexityProvider(model=model)
            
            keywords_str = ", ".join(keywords[:5]) if keywords else topic
            
            response = await provider.generate(
                system_prompt="Jesteś ekspertem badającym aktualne informacje. Odpowiadaj po polsku.",
                user_prompt=f"""Zbadaj temat: "{topic}"
                
Słowa kluczowe: {keywords_str}

Podaj:
1. 3-5 najważniejszych aktualnych faktów
2. Najnowsze trendy i zmiany (2024-2025)
3. Najczęściej cytowane statystyki
4. Nazwy ekspertów lub źródeł do zacytowania

Odpowiedz zwięźle, max 300 słów.""",
                temperature=0.3
            )
            
            return f"BADANIE PERPLEXITY:\n{response.content}"
            
        except Exception as e:
            print(f"Perplexity research error: {e}")
            return ""
    
    async def _generate_article_content(
        self,
        topic: str,
        keywords: List[str],
        brand_context: str,
        target_context: str,
        serp_context: str,
        ahrefs_context: str,
        research_context: str,
        min_words: int,
        llm_provider
    ) -> tuple[str, Dict[str, Any]]:
        """Generuje treść artykułu"""
        
        # Zbuduj mega-prompt
        context_parts = []
        
        if brand_context:
            context_parts.append(brand_context)
        
        if target_context:
            context_parts.append(target_context)
        
        if serp_context:
            context_parts.append(serp_context)
        
        if ahrefs_context:
            context_parts.append(ahrefs_context)
        
        if research_context:
            context_parts.append(research_context)
        
        context_combined = "\n\n---\n\n".join(context_parts)
        
        keywords_str = ", ".join(keywords[:10]) if keywords else ""
        
        system_prompt = f"""Jesteś ekspertem SEO i copywriterem. Piszesz wysokiej jakości artykuły zoptymalizowane pod wyszukiwarki.

ZASADY:
1. Pisz naturalnie, unikaj keyword stuffing
2. Używaj nagłówków H2 i H3 ze słowami kluczowymi
3. Dodawaj listy punktowane/numerowane
4. Pisz krótkie akapity (2-4 zdania)
5. Dodaj wstęp i podsumowanie
6. Używaj słów kluczowych naturalnie w tekście
7. Minimum {min_words} słów
8. Format Markdown

{brand_context if brand_context else ''}"""

        user_prompt = f"""Napisz artykuł SEO na temat: "{topic}"

SŁOWA KLUCZOWE DO UŻYCIA: {keywords_str}

KONTEKST I BADANIA:
{context_combined}

WYMAGANIA:
- Minimum {min_words} słów
- Unikalna perspektywa różniąca się od konkurencji
- Aktualne informacje (2024-2025)
- Praktyczne porady i przykłady
- Naturalny styl pisania

Napisz kompletny artykuł w formacie Markdown:"""

        response = await llm_provider.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.7
        )
        
        usage = {
            "prompt_tokens": response.prompt_tokens,
            "completion_tokens": response.completion_tokens,
            "total_tokens": response.total_tokens
        }
        
        return response.content, usage
    
    def _markdown_to_html(self, markdown: str) -> str:
        """Konwertuje Markdown na HTML"""
        try:
            import markdown as md
            return md.markdown(
                markdown,
                extensions=['extra', 'sane_lists', 'nl2br']
            )
        except ImportError:
            # Fallback - podstawowa konwersja
            import re
            html = markdown
            
            # Nagłówki
            html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
            html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
            html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
            
            # Bold i italic
            html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
            html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
            
            # Listy
            html = re.sub(r'^- (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
            
            # Akapity
            paragraphs = html.split('\n\n')
            html = '\n'.join([f'<p>{p}</p>' if not p.startswith('<') else p for p in paragraphs])
            
            return html
    
    def _extract_title(self, content: str) -> str:
        """Wyciąga tytuł z treści Markdown"""
        import re
        
        # Szukaj pierwszego H1
        match = re.search(r'^# (.+)$', content, re.MULTILINE)
        if match:
            return match.group(1)
        
        # Fallback - pierwsza linia
        lines = content.strip().split('\n')
        if lines:
            return lines[0].strip('#').strip()
        
        return "Artykuł bez tytułu"
    
    def _extract_description(self, content: str, max_length: int = 160) -> str:
        """Wyciąga opis (meta description) z treści"""
        import re
        
        # Usuń nagłówki
        text = re.sub(r'^#+\s+.+$', '', content, flags=re.MULTILINE)
        # Weź pierwszy niepusty akapit
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        if paragraphs:
            desc = paragraphs[0][:max_length]
            if len(paragraphs[0]) > max_length:
                desc = desc.rsplit(' ', 1)[0] + '...'
            return desc
        return ""
    
    async def improve(
        self,
        article_id: str,
        instructions: str,
        llm_provider = None
    ) -> ArticleResult:
        """
        Ulepsza istniejący artykuł
        
        Args:
            article_id: ID artykułu do ulepszenia
            instructions: Instrukcje jak ulepszyć
            llm_provider: Provider LLM
            
        Returns:
            ArticleResult z ulepszonym artykułem
        """
        result = ArticleResult(success=False)
        
        # Pobierz istniejący artykuł
        article = await self.article_storage.get(article_id)
        if not article:
            result.error = "Artykuł nie znaleziony"
            return result
        
        if llm_provider is None:
            from src.llm_providers import OpenAIProvider
            llm_provider = OpenAIProvider(model="gpt-4o")
        
        # Ulepsz artykuł
        prompt = f"""Ulepsz poniższy artykuł zgodnie z instrukcjami.

INSTRUKCJE: {instructions}

ORYGINALNY ARTYKUŁ:
{article.content}

Napisz ulepszoną wersję artykułu w formacie Markdown:"""

        response = await llm_provider.generate(
            system_prompt="Jesteś ekspertem SEO i edytorem. Ulepszasz artykuły zachowując ich strukturę.",
            user_prompt=prompt,
            temperature=0.5
        )
        
        # Aktualizuj artykuł
        article.content = response.content
        article.content_html = self._markdown_to_html(response.content)
        article.word_count = len(response.content.split())
        
        await self.article_storage.store(article)
        
        result.success = True
        result.article = article
        result.article_html = article.content_html
        result.article_markdown = article.content
        result.usage = {
            "total_tokens": response.total_tokens
        }
        
        return result


if __name__ == "__main__":
    import asyncio
    from src.llm_providers import OpenAIProvider
    
    async def test():
        generator = ArticleGenerator()
        
        result = await generator.generate(
            topic="Jak wybrać hosting WordPress w 2025",
            keywords=["hosting wordpress", "najlepszy hosting", "porównanie hostingów"],
            min_words=500,
            analyze_serp=False,  # Skip SERP for test
            include_brand_info=False,
            perplexity_model=None,  # Skip Perplexity for test
            main_llm_provider=OpenAIProvider(model="gpt-4o-mini")
        )
        
        if result.success:
            print(f"✓ Wygenerowano artykuł: {result.article.title}")
            print(f"  Słów: {result.article.word_count}")
            print(f"  ID: {result.article.id}")
        else:
            print(f"✗ Błąd: {result.error}")
    
    asyncio.run(test())
