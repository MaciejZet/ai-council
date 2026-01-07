"""
Wikipedia Plugin
=================
Pobieranie artykułów z Wikipedia
"""

import httpx
from typing import Optional, Dict, Any, List

from src.plugins import BasePlugin, PluginResult


class WikipediaPlugin(BasePlugin):
    """Pobiera artykuły z Wikipedia"""
    
    name = "Wikipedia"
    description = "Wyszukiwanie i pobieranie artykułów z Wikipedii"
    icon = "🌐"
    category = "knowledge"
    requires_api_key = False
    
    API_URL = "https://pl.wikipedia.org/api/rest_v1"
    SEARCH_URL = "https://pl.wikipedia.org/w/api.php"
    
    async def execute(
        self, 
        query: str, 
        lang: str = "pl",
        summary_only: bool = True
    ) -> PluginResult:
        """
        Pobiera artykuł z Wikipedia
        
        Args:
            query: Tytuł lub fraza do wyszukania
            lang: Język (pl, en, de, etc.)
            summary_only: Czy pobierać tylko streszczenie
        """
        try:
            # Najpierw wyszukaj
            search_result = await self._search(query, lang)
            if not search_result:
                return PluginResult(
                    success=False,
                    error=f"Nie znaleziono artykułu: {query}",
                    source="wikipedia"
                )
            
            title = search_result[0]
            
            # Pobierz artykuł
            if summary_only:
                content = await self._get_summary(title, lang)
            else:
                content = await self._get_full_article(title, lang)
            
            return PluginResult(
                success=True,
                data={
                    "title": title,
                    "content": content.get("extract", ""),
                    "url": f"https://{lang}.wikipedia.org/wiki/{title.replace(' ', '_')}",
                    "thumbnail": content.get("thumbnail", {}).get("source"),
                    "related": search_result[1:5] if len(search_result) > 1 else []
                },
                source="wikipedia"
            )
            
        except Exception as e:
            return PluginResult(
                success=False,
                error=f"Wikipedia error: {str(e)}",
                source="wikipedia"
            )
    
    async def _search(self, query: str, lang: str = "pl") -> List[str]:
        """Wyszukuje artykuły"""
        url = f"https://{lang}.wikipedia.org/w/api.php"
        params = {
            "action": "opensearch",
            "search": query,
            "limit": 5,
            "format": "json"
        }
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            return data[1] if len(data) > 1 else []
    
    async def _get_summary(self, title: str, lang: str = "pl") -> Dict[str, Any]:
        """Pobiera streszczenie artykułu"""
        url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title.replace(' ', '_')}"
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()
    
    async def _get_full_article(self, title: str, lang: str = "pl") -> Dict[str, Any]:
        """Pobiera pełny artykuł (tekst)"""
        url = f"https://{lang}.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "titles": title,
            "prop": "extracts",
            "explaintext": True,
            "exlimit": 1,
            "format": "json"
        }
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            pages = data.get("query", {}).get("pages", {})
            for page_id, page in pages.items():
                return {"extract": page.get("extract", "")}
            return {"extract": ""}
    
    async def random_article(self, lang: str = "pl") -> PluginResult:
        """Pobiera losowy artykuł"""
        url = f"https://{lang}.wikipedia.org/api/rest_v1/page/random/summary"
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
                
                return PluginResult(
                    success=True,
                    data={
                        "title": data.get("title", ""),
                        "content": data.get("extract", ""),
                        "url": data.get("content_urls", {}).get("desktop", {}).get("page", ""),
                        "thumbnail": data.get("thumbnail", {}).get("source")
                    },
                    source="wikipedia"
                )
        except Exception as e:
            return PluginResult(
                success=False,
                error=str(e),
                source="wikipedia"
            )
