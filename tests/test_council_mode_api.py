"""Regression tests for council mode API contracts."""

from fastapi.testclient import TestClient

import main as api_main


def test_council_mode_stream_returns_404_for_unknown_mode():
    client = TestClient(api_main.app)
    response = client.get(
        "/api/council/mode/stream",
        params={"mode": "totally-unknown-mode", "query": "test"},
    )

    assert response.status_code == 404
    assert "Unknown mode" in response.json()["detail"]
