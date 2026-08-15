"""Regression tests for council mode API contracts."""

from fastapi.testclient import TestClient

import main as api_main
import src.council.modes as modes_module


class FakeCouncilOS:
    def __init__(self, llm):
        self.llm = llm

    async def deliberate(self, query):
        from src.council.council_os_models import CouncilOSResult, ProblemProfile, defer_verdict

        return CouncilOSResult(
            profile=ProblemProfile(
                primary_domain="strategy",
                secondary_domains=[],
                decision_kind="strategy",
                reversibility="reversible",
                risk_level="medium",
            ),
            routed_experts=["strategy", "marketing", "sales", "operator"],
            memos=[],
            rebuttals=[],
            red_team=None,
            evidence=None,
            verdict=defer_verdict("synthetic_api_test"),
            knowledge_status_by_expert={},
            errors=[],
        )


def test_council_mode_stream_returns_404_for_unknown_mode():
    client = TestClient(api_main.app)
    response = client.get(
        "/api/council/mode/stream",
        params={"mode": "totally-unknown-mode", "query": "test"},
    )

    assert response.status_code == 404
    assert "Unknown mode" in response.json()["detail"]


def test_council_modes_api_lists_council_os():
    client = TestClient(api_main.app)
    response = client.get("/api/council/modes")

    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["modes"]}
    assert "council_os" in ids


def test_council_mode_stream_accepts_council_os(monkeypatch):
    monkeypatch.setattr(modes_module, "CouncilOS", FakeCouncilOS, raising=False)
    monkeypatch.setattr(api_main, "create_llm_provider", lambda provider, model: object())
    client = TestClient(api_main.app)

    response = client.get(
        "/api/council/mode/stream",
        params={"mode": "council_os", "query": "synthetic question"},
    )

    assert response.status_code == 200
    assert "council_os_result" in response.text
