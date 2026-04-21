from __future__ import annotations

import pytest

import src.utils.cache as cache_module
import src.utils.rate_limit as rate_limit_module


@pytest.fixture(autouse=True)
def isolate_global_middleware_state(monkeypatch: pytest.MonkeyPatch):
    """Reset singleton state to keep API tests deterministic."""
    monkeypatch.setattr(
        rate_limit_module,
        "_rate_limiter",
        rate_limit_module.RateLimiter(
            requests_per_minute=1000,
            requests_per_hour=10000,
            burst_size=1000,
        ),
        raising=False,
    )
    monkeypatch.setattr(
        cache_module,
        "_cache_instance",
        cache_module.ResponseCache(enabled=False),
        raising=False,
    )
