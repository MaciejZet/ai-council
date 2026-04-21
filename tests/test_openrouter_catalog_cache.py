"""Tests for OpenRouter model catalog fetching and cache behavior."""

import pytest

from src import llm_providers


class _FailingAsyncClient:
    calls = 0

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url):
        _FailingAsyncClient.calls += 1
        raise RuntimeError("network down")


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _SuccessAsyncClient:
    calls = 0

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url):
        _SuccessAsyncClient.calls += 1
        return _FakeResponse(
            {
                "data": [
                    {"id": "z-model"},
                    {"id": "a-model"},
                    {"id": "z-model"},
                    {},
                ]
            }
        )


@pytest.mark.asyncio
async def test_fetch_openrouter_catalog_caches_network_errors(monkeypatch):
    """Network failures should be cached briefly to avoid repeated slow retries."""
    llm_providers._openrouter_catalog_cache.clear()
    _FailingAsyncClient.calls = 0
    monkeypatch.setattr(llm_providers.httpx, "AsyncClient", _FailingAsyncClient)

    first = await llm_providers.fetch_openrouter_model_ids("https://example.test/v1")
    second = await llm_providers.fetch_openrouter_model_ids("https://example.test/v1")

    assert first == []
    assert second == []
    assert _FailingAsyncClient.calls == 1


@pytest.mark.asyncio
async def test_fetch_openrouter_catalog_sorts_deduplicates_and_uses_cache(monkeypatch):
    llm_providers._openrouter_catalog_cache.clear()
    _SuccessAsyncClient.calls = 0
    monkeypatch.setattr(llm_providers.httpx, "AsyncClient", _SuccessAsyncClient)

    first = await llm_providers.fetch_openrouter_model_ids("https://example.test/v1")
    second = await llm_providers.fetch_openrouter_model_ids("https://example.test/v1")

    assert first == ["a-model", "z-model"]
    assert second == ["a-model", "z-model"]
    assert _SuccessAsyncClient.calls == 1


def test_openrouter_tier_for_row_free_suffix_and_pricing():
    from src.llm_providers import openrouter_tier_for_row

    assert openrouter_tier_for_row({"id": "google/gemini-2.0-flash-exp:free"}) == "free"
    assert (
        openrouter_tier_for_row(
            {"id": "paid/x", "pricing": {"prompt": "0", "completion": "0"}}
        )
        == "free"
    )
    assert openrouter_tier_for_row({"id": "unknown", "pricing": {}}) == "standard"
    assert (
        openrouter_tier_for_row(
            {"id": "cheap", "pricing": {"prompt": "0.0000001", "completion": "0.0000001"}}
        )
        == "cheap"
    )
    assert (
        openrouter_tier_for_row(
            {"id": "mid", "pricing": {"prompt": "0.000002", "completion": "0.000002"}}
        )
        == "standard"
    )
    assert (
        openrouter_tier_for_row(
            {"id": "big", "pricing": {"prompt": "0.00002", "completion": "0.00002"}}
        )
        == "premium"
    )


@pytest.mark.asyncio
async def test_fetch_openrouter_catalog_entries_matches_ids_and_cache(monkeypatch):
    llm_providers._openrouter_catalog_cache.clear()
    _SuccessAsyncClient.calls = 0
    monkeypatch.setattr(llm_providers.httpx, "AsyncClient", _SuccessAsyncClient)

    first = await llm_providers.fetch_openrouter_catalog_entries("https://example.test/v1")
    second = await llm_providers.fetch_openrouter_catalog_entries("https://example.test/v1")

    assert first == [
        {"id": "a-model", "tier": "standard"},
        {"id": "z-model", "tier": "standard"},
    ]
    assert second == first
    assert _SuccessAsyncClient.calls == 1
