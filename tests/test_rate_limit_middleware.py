"""Regression tests for rate-limit middleware behavior."""

from fastapi.testclient import TestClient

import main as api_main
from src.utils.rate_limit import RateLimiter


def test_rate_limit_middleware_returns_429_response(monkeypatch):
    limiter = RateLimiter(requests_per_minute=10, requests_per_hour=100, burst_size=1)
    monkeypatch.setattr(api_main, "get_rate_limiter", lambda: limiter)

    client = TestClient(api_main.app, raise_server_exceptions=False)
    headers = {"X-Forwarded-For": "rate-limit-regression-test"}

    ok_response = client.get("/api/agents", headers=headers)
    limited_response = client.get("/api/agents", headers=headers)

    assert ok_response.status_code == 200
    assert limited_response.status_code == 429
    assert "detail" in limited_response.json()
