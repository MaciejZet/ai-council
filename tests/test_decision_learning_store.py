import json
import sqlite3

from src.storage.decision_learning import DecisionLearningStore
from src.storage.decision_memory import DecisionMemoryStore


def seed_v1(path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE decisions (
            id TEXT PRIMARY KEY,user_id TEXT NOT NULL,created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,query TEXT NOT NULL,primary_domain TEXT NOT NULL,
            secondary_domains_json TEXT NOT NULL,decision_kind TEXT NOT NULL,
            reversibility TEXT NOT NULL,risk_level TEXT NOT NULL,
            routed_experts_json TEXT NOT NULL,verdict TEXT NOT NULL,
            verdict_confidence REAL NOT NULL,recommendation TEXT NOT NULL,
            consensus TEXT NOT NULL,key_disagreement TEXT NOT NULL,
            minority_report TEXT NOT NULL,assumptions_json TEXT NOT NULL,
            evidence_gaps_json TEXT NOT NULL,what_would_change_decision_json TEXT NOT NULL,
            next_experiment_json TEXT,knowledge_status_json TEXT NOT NULL,
            orchestration_errors_json TEXT NOT NULL
        );
        CREATE TABLE decision_expert_votes (
            decision_id TEXT NOT NULL,expert_id TEXT NOT NULL,blind_vote TEXT NOT NULL,
            blind_confidence REAL NOT NULL,revised_vote TEXT,revised_confidence REAL,
            knowledge_status TEXT NOT NULL,PRIMARY KEY(decision_id,expert_id)
        );
        CREATE TABLE decision_outcomes (
            decision_id TEXT PRIMARY KEY,user_id TEXT NOT NULL,updated_at TEXT NOT NULL,
            status TEXT NOT NULL,resolved_vote TEXT,experiment_result TEXT,
            postmortem TEXT,notes TEXT
        );
        """
    )
    conn.execute(
        "INSERT INTO decisions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            "d1", "u1", "2026-01-01", "2026-01-01", "PRIVATE_QUERY_SENTINEL",
            "growth", "[]", "pricing", "reversible", "medium", "[]", "TEST", 0.7,
            "PRIVATE_RECOMMENDATION", "c", "k", "m", "[]", "[]", "[]", None, "{}", "[]",
        ),
    )
    conn.execute(
        "INSERT INTO decision_expert_votes VALUES (?,?,?,?,?,?,?)",
        ("d1", "growth", "GO", 0.8, None, None, "ok"),
    )
    conn.execute(
        "INSERT INTO decision_outcomes VALUES (?,?,?,?,?,?,?,?)",
        (
            "d1", "u1", "2026-01-02", "success", "GO", None,
            "PRIVATE_POSTMORTEM_SENTINEL", "PRIVATE_NOTES_SENTINEL",
        ),
    )
    conn.execute(
        "INSERT INTO decisions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            "d2", "u2", "2026-01-03", "2026-01-03", "OTHER_USER_QUERY_SENTINEL",
            "growth", "[]", "pricing", "reversible", "medium", "[]", "GO", 0.9,
            "OTHER_REC", "c", "k", "m", "[]", "[]", "[]", None, "{}", "[]",
        ),
    )
    conn.execute(
        "INSERT INTO decision_expert_votes VALUES (?,?,?,?,?,?,?)",
        ("d2", "growth", "GO", 0.9, None, None, "ok"),
    )
    conn.execute(
        "INSERT INTO decision_outcomes VALUES (?,?,?,?,?,?,?,?)",
        ("d2", "u2", "2026-01-04", "success", "GO", None, "OTHER_POST", "OTHER_NOTES"),
    )
    conn.commit()
    conn.close()


def test_v1_database_migrates_without_data_loss(tmp_path):
    path = tmp_path / "d.db"
    seed_v1(path)

    DecisionMemoryStore(path)

    conn = sqlite3.connect(path)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(decisions)")}
    assert "learning_context_json" in columns
    assert (
        conn.execute('SELECT query FROM decisions WHERE id="d1"').fetchone()[0]
        == "PRIVATE_QUERY_SENTINEL"
    )
    conn.close()


def test_learning_store_is_user_scoped_and_metadata_only(tmp_path):
    path = tmp_path / "d.db"
    seed_v1(path)
    DecisionMemoryStore(path)

    rows = DecisionLearningStore(path).resolved_decisions("u1", primary_domain="growth")

    assert [row["decision_id"] for row in rows] == ["d1"]
    dumped = json.dumps(rows)
    for sentinel in (
        "PRIVATE_QUERY_SENTINEL",
        "PRIVATE_POSTMORTEM_SENTINEL",
        "PRIVATE_NOTES_SENTINEL",
        "OTHER_USER_QUERY_SENTINEL",
    ):
        assert sentinel not in dumped
    assert rows[0]["resolved_vote"] == "GO"


def test_expert_predictions_use_blind_vote_only(tmp_path):
    path = tmp_path / "d.db"
    seed_v1(path)
    DecisionMemoryStore(path)

    rows = DecisionLearningStore(path).expert_predictions("u1", ["growth"], "growth")

    assert rows == [
        {
            "decision_id": "d1",
            "expert_id": "growth",
            "predicted_vote": "GO",
            "confidence": 0.8,
            "resolved_vote": "GO",
            "primary_domain": "growth",
        }
    ]
