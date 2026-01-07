"""
Web Search Plugin
==================
Wyszukiwanie w internecie przez Tavily API
"""

import os
import httpx
from typing import List, Dict, Any, Optional

from src.plugins import BasePlugin, PluginResult


class TavilySearchPlugin(BasePlugin):
    """Web search via Tavily API"""
    
    name = "Tavily Web Search"
    description = "Wyszukiwanie w internecie z AI-powered snippetami"
    icon = "🔍"
    category = "search"
    requires_api_key = True
    api_key_env = "TAVILY_API_KEY"
    
    TAVILY_API_URL = "https://api.tavily.com/search"
    
    async def execute(
        self, 
        query: str, 
        max_results: int = 5,
        search_depth: str = "basic",  # "basic" or "advanced"
        include_domains: List[str] = None,
        exclude_domains: List[str] = None
    ) -> PluginResult:
        """
        Wykonuje wyszukiwanie
        
        Args:
            query: Zapytanie do wyszukania
            max_results: Maksymalna liczba wyników
            search_depth: "basic" (szybsze) lub "advanced" (dokładniejsze)
        """
        if not self._api_key:
            return PluginResult(
                success=False,
                error="Tavily API key not configured. Set TAVILY_API_KEY env variable.",
                source="tavily"
            )
        
        try:
            payload = {
                "api_key": self._api_key,
                "query": query,
                "max_results": max_results,
                "search_depth": search_depth,
                "include_answer": True
            }
            
            if include_domains:
                payload["include_domains"] = include_domains
            if exclude_domains:
                payload["exclude_domains"] = exclude_domains
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(self.TAVILY_API_URL, json=payload)
                response.raise_for_status()
                data = response.json()
            
            # Format results
            results = []
            for item in data.get("results", []):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("content", "")[:300],
                    "score": item.get("score", 0)
                })
            
            return PluginResult(
                success=True,
                data={
                    "query": query,
                    "answer": data.get("answer"),  # AI-generated answer
                    "results": results,
                    "total": len(results)
                },
                source="tavily"
            )
            
        except httpx.HTTPStatusError as e:
            return PluginResult(
                success=False,
                error=f"Tavily API error: {e.response.status_code}",
                source="tavily"
            )
        except Exception as e:
            return PluginResult(
                success=False,
                error=f"Search failed: {str(e)}",
                source="tavily"
            )
    
    async def quick_search(self, query: str) -> Optional[str]:
        """Szybkie wyszukiwanie - zwraca tylko AI answer"""
        result = await self.execute(query, max_results=3)
        if result.success and result.data:
            return result.data.get("answer")
        return None


# Alternatywny plugin dla DuckDuckGo (bez API key)
class DuckDuckGoSearchPlugin(BasePlugin):
    """Free web search via DuckDuckGo (no API key required)"""
    
    name = "DuckDuckGo Search"
    description = "Darmowe wyszukiwanie przez DuckDuckGo (bez API key)"
    icon = "🦆"
    category = "search"
    requires_api_key = False
    
    async def execute(self, query: str, max_results: int = 5) -> PluginResult:
        """
        Wyszukiwanie przez DuckDuckGo instant answers
        Uwaga: Ograniczone możliwości bez API
        """
        try:
            # DuckDuckGo instant answer API
            url = "https://api.duckduckgo.com/"
            params = {
                "q": query,
                "format": "json",
                "no_html": 1,
                "skip_disambig": 1
            }
            
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
            
            results = []
            
            # Abstract (główna odpowiedź)
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
                        "title": topic.get("Text", "")[:50],
                        "url": topic.get("FirstURL", ""),
                        "snippet": topic.get("Text", "")
                    })
            
            return PluginResult(
                success=True,
                data={
                    "query": query,
                    "answer": data.get("Abstract") or None,
                    "results": results[:max_results],
                    "total": len(results)
                },
                source="duckduckgo"
            )
            
        except Exception as e:
            return PluginResult(
                success=False,
                error=f"DuckDuckGo search failed: {str(e)}",
                source="duckduckgo"
            )
