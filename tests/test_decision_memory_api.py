from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.decision_memory import install_decision_memory
from src.council.council_os_models import (
    CouncilOSResult,
    CouncilVerdict,
    DecisionVote,
    ExpertMemo,
    ProblemProfile,
)
from src.storage.decision_memory import DecisionMemoryStore


def synthetic_result(*, verdict=DecisionVote.TEST, expert_vote=DecisionVote.TEST):
    return CouncilOSResult(
        profile=ProblemProfile(
            primary_domain="strategy",
            secondary_domains=[],
            decision_kind="strategy",
            reversibility="reversible",
            risk_level="medium",
        ),
        routed_experts=["strategy"],
        memos=[
            ExpertMemo(
                expert_id="strategy",
                vote=expert_vote,
                recommendation="synthetic",
                confidence=0.8,
                claims=[],
                assumptions=[],
                risks=[],
                what_changes_my_mind=[],
                knowledge_status="ok",
            )
        ],
        rebuttals=[],
        red_team=None,
        evidence=None,
        verdict=CouncilVerdict(
            verdict=verdict,
            recommendation="synthetic",
            confidence=0.9,
            consensus="synthetic",
            key_disagreement="synthetic",
            minority_report="",
            assumptions=[],
            evidence_gaps=[],
            what_would_change_decision=[],
            next_experiment=None,
        ),
        knowledge_status_by_expert={"strategy": "ok"},
        errors=[],
    )


def make_client(tmp_path):
    store = DecisionMemoryStore(tmp_path / "decision-memory.db")
    app = FastAPI()
    install_decision_memory(
        app,
        store=store,
        validate_session=lambda token: {"token-a": "user-a", "token-b": "user-b"}.get(token),
    )
    return TestClient(app), store


def test_decision_memory_endpoints_require_authentication(tmp_path):
    client, _ = make_client(tmp_path)

    assert client.get("/api/decision-memory").status_code == 401
    assert client.get("/api/decision-memory/calibration").status_code == 401
    assert client.get("/api/decision-memory/missing").status_code == 401
    assert (
        client.put(
            "/api/decision-memory/missing/outcome",
            json={"status": "inconclusive"},
        ).status_code
        == 401
    )


def test_list_get_and_outcome_are_scoped_to_owner(tmp_path):
    client, store = make_client(tmp_path)
    decision_a = store.capture_decision("user-a", "Decision A", synthetic_result())
    decision_b = store.capture_decision("user-b", "Decision B", synthetic_result())

    listed = client.get(
        "/api/decision-memory",
        headers={"X-User-Session": "token-a"},
    )
    assert listed.status_code == 200
    assert {item["id"] for item in listed.json()} == {decision_a}
    assert decision_b not in {item["id"] for item in listed.json()}

    own = client.get(
        f"/api/decision-memory/{decision_a}",
        headers={"X-User-Session": "token-a"},
    )
    assert own.status_code == 200
    assert own.json()["id"] == decision_a

    cross_user_get = client.get(
        f"/api/decision-memory/{decision_a}",
        headers={"X-User-Session": "token-b"},
    )
    assert cross_user_get.status_code == 404

    cross_user_put = client.put(
        f"/api/decision-memory/{decision_a}/outcome",
        headers={"X-User-Session": "token-b"},
        json={"status": "success", "resolved_vote": "TEST"},
    )
    assert cross_user_put.status_code == 404


def test_outcome_can_be_written_revised_and_filtered(tmp_path):
    client, store = make_client(tmp_path)
    decision_id = store.capture_decision("user-a", "Decision A", synthetic_result())

    first = client.put(
        f"/api/decision-memory/{decision_id}/outcome",
        headers={"X-User-Session": "token-a"},
        json={
            "status": "success",
            "resolved_vote": "TEST",
            "experiment_result": "Synthetic result",
            "postmortem": "First read",
        },
    )
    assert first.status_code == 200
    assert first.json()["resolved_vote"] == "TEST"

    revised = client.put(
        f"/api/decision-memory/{decision_id}/outcome",
        headers={"X-User-Session": "token-a"},
        json={
            "status": "mixed",
            "resolved_vote": "GO",
            "postmortem": "Revised read",
        },
    )
    assert revised.status_code == 200
    assert revised.json()["status"] == "mixed"
    assert revised.json()["resolved_vote"] == "GO"

    filtered = client.get(
        "/api/decision-memory",
        params={"outcome_status": "mixed", "verdict": "TEST"},
        headers={"X-User-Session": "token-a"},
    )
    assert filtered.status_code == 200
    assert [item["id"] for item in filtered.json()] == [decision_id]


def test_outcome_request_and_list_filters_are_validated(tmp_path):
    client, store = make_client(tmp_path)
    decision_id = store.capture_decision("user-a", "Decision A", synthetic_result())
    headers = {"X-User-Session": "token-a"}

    assert (
        client.put(
            f"/api/decision-memory/{decision_id}/outcome",
            headers=headers,
            json={"status": "unknown"},
        ).status_code
        == 422
    )
    assert (
        client.put(
            f"/api/decision-memory/{decision_id}/outcome",
            headers=headers,
            json={"status": "success", "resolved_vote": "MAYBE"},
        ).status_code
        == 422
    )
    assert (
        client.put(
            f"/api/decision-memory/{decision_id}/outcome",
            headers=headers,
            json={"status": "success", "postmortem": "x" * 8001},
        ).status_code
        == 422
    )
    assert client.get("/api/decision-memory", params={"limit": 0}, headers=headers).status_code == 422
    assert (
        client.get(
            "/api/decision-memory",
            params={"outcome_status": "unknown"},
            headers=headers,
        ).status_code
        == 422
    )


def test_calibration_endpoint_uses_resolved_outcomes(tmp_path):
    client, store = make_client(tmp_path)
    decision_id = store.capture_decision(
        "user-a",
        "Decision A",
        synthetic_result(verdict=DecisionVote.TEST, expert_vote=DecisionVote.TEST),
    )
    headers = {"X-User-Session": "token-a"}

    before = client.get("/api/decision-memory/calibration", headers=headers)
    assert before.status_code == 200
    assert before.json()["sample_size"] == 0

    outcome = client.put(
        f"/api/decision-memory/{decision_id}/outcome",
        headers=headers,
        json={"status": "success", "resolved_vote": "TEST"},
    )
    assert outcome.status_code == 200

    after = client.get("/api/decision-memory/calibration", headers=headers)
    assert after.status_code == 200
    assert after.json()["sample_size"] == 1
    experts = {item["expert_id"]: item for item in after.json()["experts"]}
    assert experts["strategy"]["hit_rate"] == 1.0
    assert experts["chairman"]["hit_rate"] == 1.0
