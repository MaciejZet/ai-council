import sqlite3
from pathlib import Path
from src.council.council_os_models import CouncilOSResult, CouncilVerdict, LiveEvidenceSummary, ProblemProfile
from src.storage.decision_memory import DecisionMemoryStore


def result_with_live():
    return CouncilOSResult(
        profile=ProblemProfile(primary_domain="strategy",decision_kind="strategy"),
        routed_experts=["strategy"],
        verdict=CouncilVerdict(verdict="TEST",recommendation="test",confidence=.5,consensus="mixed",key_disagreement="x",minority_report=""),
        live_evidence_summary=LiveEvidenceSummary(
            status="ok",query_count=2,source_count=2,source_domains=["example.com"],
            accepted_evidence_ids=["web_a"],rejected_evidence_ids=["web_b"],error_labels=["partial_search_failure"]
        ),
    )


def test_existing_schema_migrates_and_roundtrips_sanitized_summary(tmp_path: Path):
    db=tmp_path/"dm.db"
    store=DecisionMemoryStore(db)
    with sqlite3.connect(db) as conn:
        cols={row[1] for row in conn.execute("PRAGMA table_info(decisions)")}
    assert "live_evidence_json" in cols
    did=store.capture_decision("u1","Should we launch?",result_with_live())
    record=store.get_decision("u1",did)
    assert record["live_evidence_summary"]["accepted_evidence_ids"] == ["web_a"]
    assert record["live_evidence_summary"]["source_domains"] == ["example.com"]


def test_stored_live_summary_has_no_source_content(tmp_path: Path):
    db=tmp_path/"dm.db"; store=DecisionMemoryStore(db)
    store.capture_decision("u1","Should we launch?",result_with_live())
    with sqlite3.connect(db) as conn:
        raw=conn.execute("SELECT live_evidence_json FROM decisions").fetchone()[0]
    forbidden=("https://","ACCEPTED_LIVE_SENTINEL","title","snippet","TAVILY_ANSWER","PRIVATE_EXCEPTION","Should we launch?")
    assert all(x not in raw for x in forbidden)
