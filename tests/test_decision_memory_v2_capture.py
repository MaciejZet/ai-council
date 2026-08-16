import json
import sqlite3

from src.council.council_os_models import (
    CouncilOSResult,
    CouncilVerdict,
    ExpertMemo,
    HistoricalAnalogyRejection,
    LearningContextSummary,
    ProblemProfile,
)
from src.storage.decision_memory import DecisionMemoryStore


def result_with_learning_summary():
    return CouncilOSResult(
        profile=ProblemProfile(primary_domain="growth", decision_kind="pricing"),
        routed_experts=["growth"],
        memos=[
            ExpertMemo(
                expert_id="growth",
                vote="TEST",
                recommendation="PRIVATE_MEMO_SENTINEL",
                confidence=0.8,
            )
        ],
        verdict=CouncilVerdict(
            verdict="TEST",
            recommendation="Current recommendation",
            confidence=0.7,
            consensus="mixed",
            key_disagreement="x",
            minority_report="",
        ),
        learning_context_summary=LearningContextSummary(
            status="ok",
            scored_history_count=15,
            analogy_count=2,
            active_sample_strengths={"growth": "normal"},
            bias_alerts=["overconfidence"],
            protected_minority_expert_ids=["growth"],
            rejected_analogies=[
                HistoricalAnalogyRejection(
                    decision_id="prior-2",
                    reason="current_evidence_conflict",
                )
            ],
            influenced_final_stage=True,
        ),
    )


def test_capture_persists_only_sanitized_learning_summary(tmp_path):
    db = tmp_path / "d.db"
    store = DecisionMemoryStore(db)
    decision_id = store.capture_decision(
        "u1",
        "Current question",
        result_with_learning_summary(),
    )
    record = store.get_decision("u1", decision_id)

    assert record["learning_context_summary"]["active_sample_strengths"] == {"growth": "normal"}
    assert record["learning_context_summary"]["rejected_analogies"][0]["decision_id"] == "prior-2"
    raw = sqlite3.connect(db).execute(
        "SELECT learning_context_json FROM decisions WHERE id=?",
        (decision_id,),
    ).fetchone()[0]
    assert "PRIVATE_MEMO_SENTINEL" not in raw
    assert "Current question" not in raw
    assert "postmortem" not in raw.lower()
    assert json.loads(raw)["influenced_final_stage"] is True
