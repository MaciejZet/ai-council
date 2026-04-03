"""
URL Analyzer Plugin
====================
Analiza i ekstrakcja treści ze stron WWW
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

import httpx
from urllib.parse import urlparse

from src.plugins import BasePlugin, PluginResult

_log = logging.getLogger(__name__)


class URLAnalyzerPlugin(BasePlugin):
    """Analizuje zawartość stron internetowych"""
    
    name = "URL Analyzer"
    description = "Pobiera i analizuje treść stron WWW, artykułów, dokumentów"
    icon = "🔗"
    category = "analysis"
    requires_api_key = False
    
    # User agent dla requestów
    USER_AGENT = "Mozilla/5.0 (compatible; AICouncilBot/1.0)"
    
    async def execute(
        self, 
        url: str, 
        extract_links: bool = False,
        max_content_length: int = 10000
    ) -> PluginResult:
        """
        Analizuje stronę pod podanym URL
        
        Args:
            url: URL strony do analizy
            extract_links: Czy wyciągać linki
            max_content_length: Maksymalna długość tekstu
        """
        # Walidacja URL
        if not self._is_valid_url(url):
            return PluginResult(
                success=False,
                error="Invalid URL format",
                source="url_analyzer"
            )
        
        try:
            async with httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                headers={"User-Agent": self.USER_AGENT}
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
                
                content_type = response.headers.get("content-type", "")
                
                # Sprawdź typ zawartości
                if "text/html" in content_type:
                    result = await self._parse_html(
                        response.text, 
                        url, 
                        extract_links,
                        max_content_length
                    )
                elif "application/json" in content_type:
                    result = self._parse_json(response.text)
                elif "text/plain" in content_type:
                    result = {
                        "type": "text",
                        "content": response.text[:max_content_length],
                        "length": len(response.text)
                    }
                else:
                    result = {
                        "type": "unsupported",
                        "content_type": content_type,
                        "message": f"Unsupported content type: {content_type}"
                    }
                
                return PluginResult(
                    success=True,
                    data={
                        "url": url,
                        "domain": urlparse(url).netloc,
                        "status_code": response.status_code,
                        **result
                    },
                    source="url_analyzer"
                )
                
        except httpx.HTTPStatusError as e:
            return PluginResult(
                success=False,
                error=f"HTTP error {e.response.status_code}: {url}",
                source="url_analyzer"
            )
        except httpx.RequestError as e:
            return PluginResult(
                success=False,
                error=f"Request failed: {str(e)}",
                source="url_analyzer"
            )
        except Exception as e:
            return PluginResult(
                success=False,
                error=f"Analysis failed: {str(e)}",
                source="url_analyzer"
            )
    
    async def _parse_html(
        self, 
        html: str, 
        url: str, 
        extract_links: bool,
        max_length: int
    ) -> Dict[str, Any]:
        """Parsuje HTML i wyciąga treść"""
        result = {"type": "html"}
        
        # Wyciągnij tytuł
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
        result["title"] = title_match.group(1).strip() if title_match else ""
        
        # Wyciągnij meta description
        desc_match = re.search(
            r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']+)["\']',
            html, re.IGNORECASE
        )
        if not desc_match:
            desc_match = re.search(
                r'<meta[^>]*content=["\']([^"\']+)["\'][^>]*name=["\']description["\']',
                html, re.IGNORECASE
            )
        result["description"] = desc_match.group(1).strip() if desc_match else ""
        
        # Wyciągnij OG image
        og_image = re.search(
            r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']',
            html, re.IGNORECASE
        )
        result["image"] = og_image.group(1) if og_image else None
        
        # Wyczyść HTML i wyciągnij tekst
        text = self._html_to_text(html)
        result["content"] = text[:max_length]
        result["content_length"] = len(text)
        result["truncated"] = len(text) > max_length
        
        # Wyciągnij linki jeśli potrzebne
        if extract_links:
            links = self._extract_links(html, url)
            result["links"] = links[:20]  # Limit do 20 linków
        
        return result
    
    def _html_to_text(self, html: str) -> str:
        """Konwertuje HTML na czysty tekst"""
        # Usuń script i style
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<nav[^>]*>.*?</nav>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<footer[^>]*>.*?</footer>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<header[^>]*>.*?</header>', '', text, flags=re.DOTALL | re.IGNORECASE)
        
        # Zamień br i p na newline
        text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'</p>', '\n\n', text, flags=re.IGNORECASE)
        text = re.sub(r'</div>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'</li>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'</h[1-6]>', '\n\n', text, flags=re.IGNORECASE)
        
        # Usuń wszystkie tagi HTML
        text = re.sub(r'<[^>]+>', '', text)
        
        # Dekoduj HTML entities
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&quot;', '"')
        
        # Wyczyść whitespace
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = re.sub(r' +', ' ', text)
        text = text.strip()
        
        return text
    
    def _extract_links(self, html: str, base_url: str) -> List[Dict[str, str]]:
        """Wyciąga linki z HTML"""
        links = []
        pattern = r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>([^<]*)</a>'
        
        for match in re.finditer(pattern, html, re.IGNORECASE):
            href = match.group(1)
            text = match.group(2).strip()
            
            # Skip puste i anchor linki
            if not href or href.startswith('#') or href.startswith('javascript:'):
                continue
            
            # Absolutne URL
            if href.startswith('/'):
                parsed = urlparse(base_url)
                href = f"{parsed.scheme}://{parsed.netloc}{href}"
            elif not href.startswith('http'):
                continue
            
            if text and len(text) > 2:
                links.append({"url": href, "text": text[:100]})
        
        return links
    
    def _parse_json(self, text: str) -> Dict[str, Any]:
        """Parsuje odpowiedź JSON"""
        try:
            data = json.loads(text)
            return {
                "type": "json",
                "content": str(data)[:5000],
                "keys": list(data.keys()) if isinstance(data, dict) else None
            }
        except json.JSONDecodeError:
            return {
                "type": "json_error",
                "content": text[:1000]
            }
    
    def _is_valid_url(self, url: str) -> bool:
        """Sprawdza czy URL jest poprawny"""
        try:
            result = urlparse(url)
            return all([result.scheme in ('http', 'https'), result.netloc])
        except Exception as e:
            _log.debug("urlparse failed for %r: %s", url, e)
            return False
    
    async def summarize(self, url: str, llm_provider=None) -> PluginResult:
        """
        Analizuje URL i tworzy podsumowanie przez LLM
        """
        # Najpierw pobierz treść
        result = await self.execute(url, max_content_length=8000)
        
        if not result.success:
            return result
        
        content = result.data.get("content", "")
        title = result.data.get("title", "")
        
        if not content:
            return PluginResult(
                success=False,
                error="No content to summarize",
                source="url_analyzer"
            )
        
        # Jeśli mamy LLM, wygeneruj podsumowanie
        if llm_provider:
            try:
                summary_prompt = f"""Podsumuj poniższy artykuł/stronę w 3-5 zdaniach po polsku:

TYTUŁ: {title}

TREŚĆ:
{content[:6000]}

PODSUMOWANIE:"""
                
                response = await llm_provider.generate(
                    system_prompt="Jesteś ekspertem od streszczeń. Pisz zwięźle i rzeczowo.",
                    user_prompt=summary_prompt,
                    temperature=0.3
                )
                
                result.data["summary"] = response.content
            except Exception as e:
                result.data["summary_error"] = str(e)
        
        return result
