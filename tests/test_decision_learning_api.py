import sqlite3

from src.api.decision_memory import build_learning_context_provider
from src.council.council_os_models import ExpertMemo, ProblemProfile
from src.storage.decision_memory import DecisionMemoryStore


def seed_history(path) -> None:
    DecisionMemoryStore(path)
    with sqlite3.connect(path) as conn:
        for user_id, decision_id, vote in [
            ("user-a", "a1", "GO"),
            ("user-b", "b1", "NO-GO"),
        ]:
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
                    decision_id, user_id, "2026-01-01", "2026-01-02", f"PRIVATE-{user_id}",
                    "growth", "[]", "pricing", "reversible", "medium", '["growth"]', vote,
                    0.7, "PRIVATE REC", "c", "d", "m", "[]", "[]", "[]", None, "{}", "[]", None,
                ),
            )
            conn.execute(
                """
                INSERT INTO decision_expert_votes (
                    decision_id,expert_id,blind_vote,blind_confidence,
                    revised_vote,revised_confidence,knowledge_status
                ) VALUES (?,?,?,?,?,?,?)
                """,
                (decision_id, "growth", vote, 0.7, None, None, "ok"),
            )
            conn.execute(
                """
                INSERT INTO decision_outcomes (
                    decision_id,user_id,updated_at,status,resolved_vote,
                    experiment_result,postmortem,notes
                ) VALUES (?,?,?,?,?,?,?,?)
                """,
                (
                    decision_id, user_id, "2026-01-03", "success", vote, None,
                    f"POST-{user_id}", f"NOTES-{user_id}",
                ),
            )


def test_provider_factory_is_session_scoped_and_invalid_session_disables_learning(tmp_path):
    db = tmp_path / "decisions.db"
    seed_history(db)
    store = DecisionMemoryStore(db)

    def validate(token):
        return {"token-a": "user-a", "token-b": "user-b"}.get(token)

    provider_a = build_learning_context_provider(store, validate, "token-a")
    provider_invalid = build_learning_context_provider(store, validate, "bad")
    assert provider_a is not None
    assert provider_invalid is None

    profile = ProblemProfile(
        primary_domain="growth",
        decision_kind="pricing",
        reversibility="reversible",
        risk_level="medium",
    )
    memos = [
        ExpertMemo(expert_id="growth", vote="GO", recommendation="x", confidence=0.7)
    ]
    context = provider_a(profile, ["growth"], memos)
    dumped = context.model_dump_json()
    assert "a1" in dumped
    assert "b1" not in dumped
    assert "POST-user-b" not in dumped
    assert "PRIVATE-user-b" not in dumped
