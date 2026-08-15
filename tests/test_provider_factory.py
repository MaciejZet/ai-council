"""Regression tests for provider factory behavior."""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import main as api_main


def test_create_llm_provider_rejects_unknown_provider():
    with pytest.raises(HTTPException):
        api_main.create_llm_provider("totally-unknown", "model-x")


def test_historical_stream_rejects_unknown_provider():
    client = TestClient(api_main.app)
    response = client.get(
        "/api/historical/deliberate/stream",
        params={
            "query": "test",
            "provider": "totally-unknown",
            "model": "model-x",
        },
    )
    assert response.status_code == 400
