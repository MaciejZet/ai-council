import json
import sqlite3

from src.council.council_os_models import (
    CouncilOSResult,
    CouncilVerdict,
    DecisionVote,
    FrameworkSelectionSummary,
    ProblemProfile,
)
from src.storage.decision_memory import DecisionMemoryStore


def _create_v2_schema_without_framework_column(db_path):
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE decisions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            query TEXT NOT NULL,
            primary_domain TEXT NOT NULL,
            secondary_domains_json TEXT NOT NULL,
            decision_kind TEXT NOT NULL,
            reversibility TEXT NOT NULL,
            risk_level TEXT NOT NULL,
            routed_experts_json TEXT NOT NULL,
            verdict TEXT NOT NULL,
            verdict_confidence REAL NOT NULL,
            recommendation TEXT NOT NULL,
            consensus TEXT NOT NULL,
            key_disagreement TEXT NOT NULL,
            minority_report TEXT NOT NULL,
            assumptions_json TEXT NOT NULL,
            evidence_gaps_json TEXT NOT NULL,
            what_would_change_decision_json TEXT NOT NULL,
            next_experiment_json TEXT,
            knowledge_status_json TEXT NOT NULL,
            orchestration_errors_json TEXT NOT NULL,
            learning_context_json TEXT
        );
        """
    )
    conn.execute(
        """
        INSERT INTO decisions VALUES (
            'old-id','u1','2026-08-01','2026-08-01','old q','strategy','[]','strategy',
            'reversible','medium','[]','TEST',0.5,'r','c','k','m','[]','[]','[]',NULL,'{}','[]',NULL
        )
        """
    )
    conn.commit()
    conn.close()


def _result_with_framework_summary():
    return CouncilOSResult(
        profile=ProblemProfile(primary_domain="marketing", decision_kind="marketing"),
        routed_experts=["marketing"],
        verdict=CouncilVerdict(
            verdict=DecisionVote.TEST,
            recommendation="PRIVATE_BOOK_SENTINEL stays outside framework summary",
            confidence=0.6,
            consensus="mixed",
            key_disagreement="x",
            minority_report="",
        ),
        framework_selection_summary=FrameworkSelectionSummary(
            policy_version="framework-selector-v1",
            selected_framework_ids=["positioning_category"],
            by_expert={"marketing": ["positioning_category"]},
            reason_labels_by_framework={"positioning_category": ["primary_domain"]},
            retrieval_status_by_expert={"marketing": "framework_match"},
            rejected_framework_ids=[],
            selector_error_labels=[],
        ),
    )


def test_v2_database_migrates_framework_selection_column_without_data_loss(tmp_path):
    db_path = tmp_path / "decisions.db"
    _create_v2_schema_without_framework_column(db_path)

    store = DecisionMemoryStore(db_path)

    with store._connect() as conn:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(decisions)")}
        old = conn.execute("SELECT id FROM decisions WHERE id = 'old-id'").fetchone()
    assert "framework_selection_json" in columns
    assert old["id"] == "old-id"


def test_capture_persists_only_sanitized_framework_summary(tmp_path):
    store = DecisionMemoryStore(tmp_path / "decisions.db")
    decision_id = store.capture_decision("u1", "DRIVE_ID_SENTINEL query", _result_with_framework_summary())

    with store._connect() as conn:
        row = conn.execute(
            "SELECT framework_selection_json FROM decisions WHERE id = ?",
            (decision_id,),
        ).fetchone()
    framework_json = row["framework_selection_json"]
    payload = json.loads(framework_json)

    assert payload["selected_framework_ids"] == ["positioning_category"]
    assert "PRIVATE_BOOK_SENTINEL" not in framework_json
    assert "DRIVE_ID_SENTINEL" not in framework_json

    loaded = store.get_decision("u1", decision_id)
    assert loaded["framework_selection_summary"]["policy_version"] == "framework-selector-v1"
