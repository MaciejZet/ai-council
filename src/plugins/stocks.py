"""
Stock Prices Plugin
====================
Kursy akcji przez yfinance (darmowe)
"""

import httpx
from typing import Dict, Any, List
from datetime import datetime, timedelta

from src.plugins import BasePlugin, PluginResult


class StockPricesPlugin(BasePlugin):
    """Kursy akcji i kryptowalut"""
    
    name = "Stock Prices"
    description = "Kursy akcji, ETF, kryptowalut (Yahoo Finance)"
    icon = "📈"
    category = "data"
    requires_api_key = False
    
    # Yahoo Finance API (nieoficjalne, ale działa)
    QUOTE_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    SEARCH_URL = "https://query1.finance.yahoo.com/v1/finance/search"
    
    async def execute(
        self,
        symbol: str,
        period: str = "1d"  # 1d, 5d, 1mo, 3mo, 6mo, 1y
    ) -> PluginResult:
        """
        Pobiera dane o akcji
        
        Args:
            symbol: Symbol akcji (np. AAPL, MSFT, BTC-USD)
            period: Okres (1d, 5d, 1mo, 3mo, 6mo, 1y)
        """
        try:
            data = await self._get_quote(symbol, period)
            
            if not data:
                return PluginResult(
                    success=False,
                    error=f"Nie znaleziono symbolu: {symbol}",
                    source="stocks"
                )
            
            return PluginResult(
                success=True,
                data=data,
                source="stocks"
            )
            
        except Exception as e:
            return PluginResult(
                success=False,
                error=f"Stock error: {str(e)}",
                source="stocks"
            )
    
    async def _get_quote(self, symbol: str, period: str) -> Dict[str, Any]:
        """Pobiera dane z Yahoo Finance"""
        # Mapowanie okresów
        period_map = {
            "1d": ("1d", "5m"),
            "5d": ("5d", "15m"),
            "1mo": ("1mo", "1d"),
            "3mo": ("3mo", "1d"),
            "6mo": ("6mo", "1d"),
            "1y": ("1y", "1wk")
        }
        
        range_val, interval = period_map.get(period, ("1d", "5m"))
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                self.QUOTE_URL.format(symbol=symbol.upper()),
                params={
                    "range": range_val,
                    "interval": interval,
                    "includePrePost": False
                },
                headers={
                    "User-Agent": "Mozilla/5.0"
                }
            )
            response.raise_for_status()
            data = response.json()
            
            result = data.get("chart", {}).get("result", [])
            if not result:
                return None
            
            quote = result[0]
            meta = quote.get("meta", {})
            indicators = quote.get("indicators", {}).get("quote", [{}])[0]
            
            # Ostatnia cena
            def _to_float(value, default: float = 0.0) -> float:
                try:
                    if value is None:
                        return default
                    return float(value)
                except (TypeError, ValueError):
                    return default

            raw_current = meta.get("regularMarketPrice")
            raw_prev_close = meta.get("previousClose")

            current_price = _to_float(
                raw_current,
                default=_to_float(raw_prev_close, 0.0),
            )
            prev_close = _to_float(raw_prev_close, current_price)
            change = current_price - prev_close
            change_pct = (change / prev_close * 100) if prev_close else 0
            
            return {
                "symbol": meta.get("symbol", symbol),
                "name": meta.get("shortName", symbol),
                "currency": meta.get("currency", "USD"),
                "exchange": meta.get("exchangeName", ""),
                "current_price": round(current_price, 2),
                "previous_close": round(prev_close, 2),
                "change": round(change, 2),
                "change_percent": round(change_pct, 2),
                "day_high": meta.get("regularMarketDayHigh"),
                "day_low": meta.get("regularMarketDayLow"),
                "volume": meta.get("regularMarketVolume"),
                "market_cap": meta.get("marketCap"),
                "trend": "📈" if change >= 0 else "📉"
            }
    
    async def search(self, query: str) -> PluginResult:
        """Wyszukuje symbole"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    self.SEARCH_URL,
                    params={"q": query, "quotesCount": 5},
                    headers={"User-Agent": "Mozilla/5.0"}
                )
                response.raise_for_status()
                data = response.json()
                
                quotes = data.get("quotes", [])
                results = [
                    {
                        "symbol": q.get("symbol"),
                        "name": q.get("shortname") or q.get("longname"),
                        "type": q.get("quoteType"),
                        "exchange": q.get("exchange")
                    }
                    for q in quotes
                ]
                
                return PluginResult(
                    success=True,
                    data={"query": query, "results": results},
                    source="stocks"
                )
                
        except Exception as e:
            return PluginResult(
                success=False,
                error=str(e),
                source="stocks"
            )
