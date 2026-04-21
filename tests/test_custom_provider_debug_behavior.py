"""Tests for CustomAPIProvider debug behavior."""

from pathlib import Path

from src import custom_api_provider


class _DummyAsyncOpenAI:
    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs


def test_custom_provider_does_not_write_debug_file_by_default(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(custom_api_provider, "AsyncOpenAI", _DummyAsyncOpenAI)
    monkeypatch.delenv("AI_COUNCIL_DEBUG_CUSTOM_PROVIDER", raising=False)
    monkeypatch.chdir(tmp_path)

    custom_api_provider.CustomAPIProvider(
        model="local-model",
        base_url="http://localhost:1234/v1",
        api_key="super-secret-key",
    )

    assert not (tmp_path / "debug_api_keys.txt").exists()
