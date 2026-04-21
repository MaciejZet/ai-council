from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

import main as api_main
import src.utils.rate_limit as rate_limit_module


def _sample_deliberation_result() -> api_main.DeliberationResult:
    return api_main.DeliberationResult(
        query="test query",
        timestamp="2026-04-20T10:00:00",
        agent_responses=[
            api_main.AgentResponseData(
                agent_name="Strateg",
                role="Strateg",
                content="Plan",
                provider_used="openai",
                prompt_tokens=10,
                completion_tokens=15,
                total_tokens=25,
                model="gpt-4o",
            )
        ],
        synthesis=api_main.AgentResponseData(
            agent_name="Syntezator",
            role="Synthesizer",
            content="Synteza",
            provider_used="openai",
            prompt_tokens=5,
            completion_tokens=6,
            total_tokens=11,
            model="gpt-4o",
        ),
        sources=[
            api_main.SourceData(
                title="Doc",
                category="marketing",
                max_score=0.9,
                emoji="📄",
            )
        ],
        total_agents=2,
        usage=api_main.UsageData(
            prompt_tokens=15,
            completion_tokens=21,
            total_tokens=36,
            total_cost=0.0012,
        ),
    )


@pytest.fixture()
def client() -> TestClient:
    return TestClient(api_main.app)


def _assert_error_contract(payload: dict[str, Any], code: str):
    assert payload["ok"] is False
    assert payload["error"]["code"] == code
    assert payload["error"]["message"]
    assert payload["meta"]["trace_id"]
    assert payload["meta"]["timestamp"]


def test_deliberate_v1_error_returns_contract_and_legacy_detail(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    async def fake_run_pipeline(*_args: Any, **_kwargs: Any):
        raise api_main.DeliberationApiException(
            status_code=400,
            code="provider_error",
            message="provider unavailable",
            details={"provider": "openai"},
        )

    monkeypatch.setattr(api_main, "_run_deliberation_pipeline", fake_run_pipeline, raising=False)

    response = client.post(
        "/api/deliberate",
        json={"query": "test query", "provider": "openai", "model": "gpt-4o"},
    )

    assert response.status_code == 400
    assert response.headers.get("X-Trace-Id")
    payload = response.json()
    _assert_error_contract(payload, "provider_error")
    assert payload["detail"] == "provider unavailable"


def test_deliberate_v1_success_shape_stays_compatible(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    async def fake_run_pipeline(*_args: Any, **_kwargs: Any) -> api_main.DeliberationResult:
        return _sample_deliberation_result()

    monkeypatch.setattr(api_main, "_run_deliberation_pipeline", fake_run_pipeline, raising=False)

    response = client.post(
        "/api/deliberate",
        json={"query": "test query", "provider": "openai", "model": "gpt-4o"},
    )

    assert response.status_code == 200
    assert response.headers.get("X-Trace-Id")
    payload = response.json()
    assert "ok" not in payload
    assert payload["query"] == "test query"
    assert "agent_responses" in payload


def test_sessions_not_found_returns_contract(client: TestClient):
    response = client.get("/api/sessions/not-found-session")
    assert response.status_code == 404
    assert response.headers.get("X-Trace-Id")
    _assert_error_contract(response.json(), "not_found")


def test_sessions_validation_error_returns_contract(client: TestClient):
    response = client.get("/api/sessions", params={"limit": "oops"})
    assert response.status_code == 422
    assert response.headers.get("X-Trace-Id")
    _assert_error_contract(response.json(), "validation_error")


def test_share_bad_request_returns_contract(client: TestClient):
    response = client.post("/api/share", json={})
    assert response.status_code == 400
    assert response.headers.get("X-Trace-Id")
    _assert_error_contract(response.json(), "bad_request")


def test_shared_missing_token_returns_contract(client: TestClient):
    response = client.get("/api/shared/missing-token")
    assert response.status_code == 404
    assert response.headers.get("X-Trace-Id")
    _assert_error_contract(response.json(), "not_found")


def test_export_invalid_format_returns_contract(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    fake_session = SimpleNamespace(metadata=SimpleNamespace(timestamp="2026-04-20T12:00:00"))
    monkeypatch.setattr(api_main.session_history, "load_session", lambda _sid: fake_session)

    response = client.get("/api/sessions/sess-1/export", params={"format": "zip"})
    assert response.status_code == 400
    assert response.headers.get("X-Trace-Id")
    _assert_error_contract(response.json(), "bad_request")


def test_rate_limit_error_for_core_path_uses_contract(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        rate_limit_module,
        "_rate_limiter",
        rate_limit_module.RateLimiter(requests_per_minute=1, requests_per_hour=1, burst_size=0),
        raising=False,
    )

    response = client.get("/api/sessions")
    assert response.status_code == 429
    assert response.headers.get("X-Trace-Id")
    _assert_error_contract(response.json(), "rate_limit")
