"""Regression tests for historical council API validation."""

from fastapi.testclient import TestClient

import main as api_main


def test_historical_stream_rejects_unknown_agent_ids():
    client = TestClient(api_main.app)
    response = client.get(
        "/api/historical/deliberate/stream",
        params={"query": "test", "agent_ids": "unknown_agent"},
    )

    assert response.status_code == 400
    assert "Unknown historical agent IDs" in response.json()["detail"]


def test_historical_stream_rejects_unknown_mode():
    client = TestClient(api_main.app)
    response = client.get(
        "/api/historical/deliberate/stream",
        params={"query": "test", "mode": "unknown-mode"},
    )

    assert response.status_code == 400
    assert "Unknown historical mode" in response.json()["detail"]
