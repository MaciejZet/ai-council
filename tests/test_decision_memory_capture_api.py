import importlib
import json

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

from src.council.council_os_models import (
    CouncilOSResult,
    CouncilVerdict,
    DecisionVote,
    ProblemProfile,
)

api_module = importlib.import_module("src.api.decision_memory")


def synthetic_result() -> CouncilOSResult:
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
        verdict=CouncilVerdict(
            verdict=DecisionVote.TEST,
            recommendation="Run a synthetic test.",
            confidence=0.7,
            consensus="Synthetic consensus.",
            key_disagreement="Synthetic disagreement.",
            minority_report="",
            assumptions=[],
            evidence_gaps=[],
            what_would_change_decision=[],
            next_experiment=None,
        ),
        knowledge_status_by_expert={},
        errors=[],
    )


def make_app(store, validate_session):
    app = FastAPI()

    @app.get("/api/council/mode/stream")
    async def synthetic_council_stream(mode: str, query: str):
        async def events():
            yield "data: " + json.dumps({"event": "mode_start", "mode": mode}) + "\n\n"
            yield "data: " + json.dumps(
                {
                    "event": "council_os_result",
                    "result": synthetic_result().model_dump(mode="json"),
                }
            ) + "\n\n"
            yield "data: " + json.dumps({"event": "complete"}) + "\n\n"

        return StreamingResponse(events(), media_type="text/event-stream")

    api_module.install_decision_memory(
        app,
        store=store,
        validate_session=validate_session,
    )
    return app


class RecordingStore:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.calls = []

    def capture_decision(self, user_id, query, result):
        self.calls.append((user_id, query, result))
        if self.fail:
            raise RuntimeError("SENSITIVE_PRIVATE_SENTINEL")
        return "decision-123"

    def list_decisions(self, *args, **kwargs):
        return []

    def get_decision(self, *args, **kwargs):
        return None

    def upsert_outcome(self, *args, **kwargs):
        return None

    def calibration_report(self, *args, **kwargs):
        return {"sample_size": 0, "experts": [], "domains": {}}


def test_authenticated_council_os_stream_persists_once_and_emits_decision_id():
    store = RecordingStore()
    client = TestClient(make_app(store, lambda token: "user-a" if token == "valid" else None))

    response = client.get(
        "/api/council/mode/stream",
        params={"mode": "council_os", "query": "synthetic question"},
        headers={"X-User-Session": "valid"},
    )

    assert response.status_code == 200
    assert len(store.calls) == 1
    assert store.calls[0][0:2] == ("user-a", "synthetic question")
    assert '"decision_id": "decision-123"' in response.text


def test_anonymous_and_invalid_session_streams_do_not_persist():
    store = RecordingStore()
    client = TestClient(make_app(store, lambda token: "user-a" if token == "valid" else None))

    anonymous = client.get(
        "/api/council/mode/stream",
        params={"mode": "council_os", "query": "anonymous"},
    )
    invalid = client.get(
        "/api/council/mode/stream",
        params={"mode": "council_os", "query": "invalid"},
        headers={"X-User-Session": "bad"},
    )

    assert anonymous.status_code == 200
    assert invalid.status_code == 200
    assert store.calls == []
    assert "decision_id" not in anonymous.text
    assert "decision_id" not in invalid.text


def test_storage_failure_does_not_break_or_leak_council_os_stream():
    store = RecordingStore(fail=True)
    client = TestClient(make_app(store, lambda token: "user-a" if token == "valid" else None))

    response = client.get(
        "/api/council/mode/stream",
        params={"mode": "council_os", "query": "synthetic question"},
        headers={"X-User-Session": "valid"},
    )

    assert response.status_code == 200
    assert len(store.calls) == 1
    assert "council_os_result" in response.text
    assert "complete" in response.text
    assert "decision_id" not in response.text
    assert "SENSITIVE_PRIVATE_SENTINEL" not in response.text


def test_non_council_os_stream_is_never_captured():
    store = RecordingStore()
    client = TestClient(make_app(store, lambda token: "user-a" if token == "valid" else None))

    response = client.get(
        "/api/council/mode/stream",
        params={"mode": "swot", "query": "synthetic question"},
        headers={"X-User-Session": "valid"},
    )

    assert response.status_code == 200
    assert store.calls == []
    assert "decision_id" not in response.text
