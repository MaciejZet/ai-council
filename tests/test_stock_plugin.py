"""Regression tests for stock plugin edge cases."""

import pytest

from src.plugins.stocks import StockPricesPlugin


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, *args, **kwargs):
        return _FakeResponse(
            {
                "chart": {
                    "result": [
                        {
                            "meta": {
                                "symbol": "AAPL",
                                "shortName": "Apple Inc.",
                                "currency": "USD",
                                "exchangeName": "NMS",
                                "regularMarketPrice": None,
                                "previousClose": 123.45,
                                "regularMarketDayHigh": None,
                                "regularMarketDayLow": None,
                                "regularMarketVolume": None,
                                "marketCap": None,
                            },
                            "indicators": {"quote": [{}]},
                        }
                    ]
                }
            }
        )


@pytest.mark.asyncio
async def test_stock_plugin_handles_missing_market_price(monkeypatch):
    """Missing `regularMarketPrice` should not crash plugin execution."""
    import src.plugins.stocks as stocks_mod

    monkeypatch.setattr(stocks_mod.httpx, "AsyncClient", _FakeAsyncClient)

    plugin = StockPricesPlugin()
    result = await plugin.execute("AAPL")

    assert result.success is True
    assert result.data["symbol"] == "AAPL"
    assert result.data["current_price"] == 123.45
    assert result.data["change"] == 0
