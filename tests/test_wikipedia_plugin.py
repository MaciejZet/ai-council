"""Regression tests for Wikipedia plugin input handling."""

import pytest

from src.plugins.wikipedia import WikipediaPlugin


@pytest.mark.asyncio
async def test_wikipedia_plugin_rejects_blank_query_without_network(monkeypatch):
    plugin = WikipediaPlugin()

    called = {"search": 0}

    async def _fake_search(*args, **kwargs):
        called["search"] += 1
        return ["Should not be used"]

    monkeypatch.setattr(plugin, "_search", _fake_search)

    result = await plugin.execute("   ", lang="pl", summary_only=True)

    assert result.success is False
    assert "query" in (result.error or "").lower()
    assert called["search"] == 0
