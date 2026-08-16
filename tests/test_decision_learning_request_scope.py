import json
import sqlite3

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

from src.api.decision_memory import install_decision_memory
from src.council.council_os import (
    bind_learning_context_provider,
    current_learning_context_provider,
    reset_learning_context_provider,
)
from src.council.council_os_models import ExpertMemo, ProblemProfile
from src.storage.decision_memory import DecisionMemoryStore


def _seed_history(store: DecisionMemoryStore) -> None:
    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            """
            INSERT INTO decisions (
                id,user_id,created_at,updated_at,query,primary_domain,
                secondary_domains_json,decision_kind,reversibility,risk_level,
                routed_experts_json,verdict,verdict_confidence,recommendation,
                consensus,key_disagreement,minority_report,assumptions_json,
                evidence_gaps_json,what_would_change_decision_json,next_experiment_json,
                knowledge_status_json,orchestration_errors_json,learning_context_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "prior-a", "user-a", "2026-01-01", "2026-01-01", "PRIVATE_QUERY",
                "growth", "[]", "pricing", "reversible", "medium", '["growth"]',
                "GO", 0.8, "PRIVATE_REC", "c", "d", "m", "[]", "[]", "[]",
                None, "{}", "[]", None,
            ),
        )
        conn.execute(
            "INSERT INTO decision_expert_votes VALUES (?,?,?,?,?,?,?)",
            ("prior-a", "growth", "GO", 0.8, None, None, "ok"),
        )
        conn.execute(
            "INSERT INTO decision_outcomes VALUES (?,?,?,?,?,?,?,?)",
            (
                "prior-a", "user-a", "2026-01-02", "success", "GO", None,
                "PRIVATE_POST", "PRIVATE_NOTES",
            ),
        )


def test_authenticated_council_request_gets_request_scoped_provider_and_resets_afterward(tmp_path):
    store = DecisionMemoryStore(tmp_path / "decisions.db")
    _seed_history(store)
    app = FastAPI()

    @app.get("/api/council/mode/stream")
    async def stream(mode: str, query: str):
        provider = current_learning_context_provider()
        profile = ProblemProfile(primary_domain="growth", decision_kind="pricing")
        memos = [
            ExpertMemo(expert_id="growth", vote="GO", recommendation="x", confidence=0.7)
        ]
        context = provider(profile, ["growth"], memos) if provider else None

        async def events():
            yield "data: " + json.dumps(
                {
                    "event": "probe",
                    "provider": provider is not None,
                    "history": context.scored_history_count if context else 0,
                }
            ) + "\n\n"

        return StreamingResponse(events(), media_type="text/event-stream")

    install_decision_memory(
        app,
        store=store,
        validate_session=lambda token: "user-a" if token == "valid" else None,
    )
    client = TestClient(app)

    authenticated = client.get(
        "/api/council/mode/stream",
        params={"mode": "council_os", "query": "q"},
        headers={"X-User-Session": "valid"},
    )
    anonymous = client.get(
        "/api/council/mode/stream",
        params={"mode": "council_os", "query": "q"},
    )

    assert '"provider": true' in authenticated.text
    assert '"history": 1' in authenticated.text
    assert '"provider": false' in anonymous.text
    assert current_learning_context_provider() is None


def test_anonymous_request_masks_any_outer_learning_context(tmp_path):
    store = DecisionMemoryStore(tmp_path / "decisions.db")
    app = FastAPI()

    @app.get("/api/council/mode/stream")
    async def stream(mode: str, query: str):
        provider = current_learning_context_provider()

        async def events():
            yield "data: " + json.dumps(
                {"event": "probe", "provider": provider is not None}
            ) + "\n\n"

        return StreamingResponse(events(), media_type="text/event-stream")

    install_decision_memory(app, store=store, validate_session=lambda token: None)
    client = TestClient(app)

    outer_provider = lambda *_args: None
    token = bind_learning_context_provider(outer_provider)
    try:
        response = client.get(
            "/api/council/mode/stream",
            params={"mode": "council_os", "query": "q"},
        )
        assert '"provider": false' in response.text
        assert current_learning_context_provider() is outer_provider
    finally:
        reset_learning_context_provider(token)
