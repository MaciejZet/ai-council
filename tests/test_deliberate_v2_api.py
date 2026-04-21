from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

import main as api_main


def _sample_deliberation_result() -> api_main.DeliberationResult:
    return api_main.DeliberationResult(
        query="test query",
        timestamp="2026-04-20T10:00:00",
        agent_responses=[
            api_main.AgentResponseData(
                agent_name="🧠 Strateg",
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
            agent_name="🔮 Syntezator",
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
        session_id="sess-1",
        routing_intent="strategy",
        behavior_preset="default",
        quality_decision={
            "mode": "auto",
            "applied_critic": True,
            "applied_weighted_voting": False,
            "reason": "auto_medium_high_risk",
            "risk_score": 0.58,
        },
    )


def _sample_deliberation_result_without_quality() -> api_main.DeliberationResult:
    result = _sample_deliberation_result()
    result.quality_decision = None
    return result


@pytest.fixture()
def client() -> TestClient:
    return TestClient(api_main.app)


def test_v2_happy_path_returns_envelope(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    async def fake_run_pipeline(*_args: Any, **_kwargs: Any) -> api_main.DeliberationResult:
        return _sample_deliberation_result()

    monkeypatch.setattr(api_main, "_run_deliberation_pipeline", fake_run_pipeline, raising=False)

    response = client.post(
        "/api/deliberate/v2",
        json={
            "query": "test query",
            "provider": "openai",
            "model": "gpt-4o",
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["ok"] is True
    assert payload["data"]["query"] == "test query"
    assert payload["meta"]["version"] == "v2"
    assert payload["meta"]["trace_id"]
    assert payload["diagnostics"]["routing"]["intent"] == "strategy"
    assert payload["diagnostics"]["provider"] == "openai"
    assert payload["diagnostics"]["model"] == "gpt-4o"
    assert payload["diagnostics"]["quality_flags"]["quality_mode"] == "auto"
    assert payload["diagnostics"]["quality_decision"]["mode"] == "auto"
    assert "risk_score" in payload["diagnostics"]["quality_decision"]


def test_v2_validation_error_has_contract(client: TestClient):
    response = client.post(
        "/api/deliberate/v2",
        json={"provider": "openai", "model": "gpt-4o"},
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["ok"] is False
    assert payload["error"]["code"] == "validation_error"
    assert payload["meta"]["trace_id"]


def test_v2_quality_decision_fallback_when_pipeline_payload_missing_field(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    async def fake_run_pipeline(*_args: Any, **_kwargs: Any) -> api_main.DeliberationResult:
        return _sample_deliberation_result_without_quality()

    monkeypatch.setattr(api_main, "_run_deliberation_pipeline", fake_run_pipeline, raising=False)

    response = client.post(
        "/api/deliberate/v2",
        json={
            "query": "test query",
            "provider": "openai",
            "model": "gpt-4o",
            "quality_mode": "auto",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["diagnostics"]["quality_decision"]["mode"] == "auto"
    assert "risk_score" in payload["diagnostics"]["quality_decision"]


@pytest.mark.parametrize(
    ("status_code", "code", "message"),
    [
        (400, "provider_error", "provider unavailable"),
        (500, "orchestration_error", "orchestrator failed"),
    ],
)
def test_v2_maps_known_errors_to_envelope(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    status_code: int,
    code: str,
    message: str,
):
    api_exc_cls = getattr(api_main, "DeliberationApiException", None)

    async def fake_run_pipeline(*_args: Any, **_kwargs: Any):
        if api_exc_cls is not None:
            raise api_exc_cls(status_code=status_code, code=code, message=message)
        raise RuntimeError(message)

    monkeypatch.setattr(api_main, "_run_deliberation_pipeline", fake_run_pipeline, raising=False)

    response = client.post(
        "/api/deliberate/v2",
        json={
            "query": "test query",
            "provider": "openai",
            "model": "gpt-4o",
        },
    )

    assert response.status_code == status_code
    payload = response.json()
    assert payload["ok"] is False
    assert payload["error"]["code"] == code
    assert payload["error"]["message"] == message
    assert payload["meta"]["trace_id"]


def test_v1_regression_response_shape_is_preserved(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    async def fake_run_pipeline(*_args: Any, **_kwargs: Any) -> api_main.DeliberationResult:
        return _sample_deliberation_result()

    monkeypatch.setattr(api_main, "_run_deliberation_pipeline", fake_run_pipeline, raising=False)

    response = client.post(
        "/api/deliberate",
        json={
            "query": "test query",
            "provider": "openai",
            "model": "gpt-4o",
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert "ok" not in payload
    assert payload["query"] == "test query"
    assert "agent_responses" in payload
    assert "usage" in payload
    assert response.headers.get("X-Trace-Id")
