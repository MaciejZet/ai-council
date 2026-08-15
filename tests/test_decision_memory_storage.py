import json
import sqlite3

from src.council.council_os_models import (
    Claim,
    ClaimLabel,
    CouncilOSResult,
    CouncilVerdict,
    DecisionVote,
    EvidenceAssessment,
    ExpertMemo,
    NextExperiment,
    ProblemProfile,
    Rebuttal,
    RedTeamReport,
)
from src.storage.decision_memory import DecisionMemoryStore

PRIVATE_SENTINEL = "PRIVATE_SYNTHETIC_CHUNK"


def synthetic_council_result(
    *,
    primary_domain: str = "offer_pricing",
    verdict: DecisionVote = DecisionVote.TEST,
) -> CouncilOSResult:
    return CouncilOSResult(
        profile=ProblemProfile(
            primary_domain=primary_domain,
            secondary_domains=["strategy"],
            decision_kind="pricing",
            reversibility="reversible",
            risk_level="medium",
        ),
        routed_experts=["strategy", "offer_pricing"],
        memos=[
            ExpertMemo(
                expert_id="strategy",
                vote=DecisionVote.TEST,
                recommendation=f"do not persist {PRIVATE_SENTINEL}",
                confidence=0.8,
                claims=[
                    Claim(
                        label=ClaimLabel.FACT,
                        text=f"private claim {PRIVATE_SENTINEL}",
                        source_ids=["private-source-id"],
                    )
                ],
                assumptions=["public assumption"],
                risks=[f"private risk {PRIVATE_SENTINEL}"],
                what_changes_my_mind=[f"private evidence {PRIVATE_SENTINEL}"],
                knowledge_status="ok",
            ),
            ExpertMemo(
                expert_id="offer_pricing",
                vote=DecisionVote.GO,
                recommendation="synthetic pricing recommendation",
                confidence=0.7,
                claims=[],
                assumptions=[],
                risks=[],
                what_changes_my_mind=[],
                knowledge_status="no_matches",
            ),
        ],
        rebuttals=[
            Rebuttal(
                expert_id="strategy",
                strongest_agreement=f"private rebuttal {PRIVATE_SENTINEL}",
                strongest_disagreement="private disagreement",
                assumption_to_test="private assumption",
                revised_vote=DecisionVote.GO,
                revised_confidence=0.6,
            )
        ],
        red_team=RedTeamReport(
            failure_modes=[f"private red team {PRIVATE_SENTINEL}"],
            challenged_assumptions=[],
            double_crux_questions=[],
        ),
        evidence=EvidenceAssessment(
            supported_claims=[f"private evidence judge {PRIVATE_SENTINEL}"],
            knowledge_status_by_expert={
                "strategy": "ok",
                "offer_pricing": "no_matches",
            },
        ),
        verdict=CouncilVerdict(
            verdict=verdict,
            recommendation="Run a bounded pricing pilot.",
            confidence=0.9,
            consensus="Test first.",
            key_disagreement="Expected upside.",
            minority_report="One expert would go immediately.",
            assumptions=["Customers accept the test."],
            evidence_gaps=["Need live conversion evidence."],
            what_would_change_decision=["Observed conversion below threshold."],
            next_experiment=NextExperiment(
                action="Run pricing pilot",
                metric="conversion",
                threshold="10%",
                timeline="14 days",
                kill_criteria="below 2%",
            ),
        ),
        knowledge_status_by_expert={
            "strategy": "ok",
            "offer_pricing": "no_matches",
        },
        errors=["synthetic_orchestration_label"],
    )


def test_capture_stores_sanitized_decision_and_vote_rows(tmp_path):
    db_path = tmp_path / "decisions.db"
    store = DecisionMemoryStore(db_path)

    decision_id = store.capture_decision(
        "user-a",
        "Should we test pricing?",
        synthetic_council_result(),
    )
    record = store.get_decision("user-a", decision_id)

    assert record is not None
    assert record["query"] == "Should we test pricing?"
    assert record["primary_domain"] == "offer_pricing"
    assert record["verdict"] == "TEST"
    assert record["verdict_confidence"] == 0.9
    assert record["next_experiment"]["metric"] == "conversion"
    assert record["knowledge_status_by_expert"]["offer_pricing"] == "no_matches"

    votes = {vote["expert_id"]: vote for vote in record["expert_votes"]}
    assert votes["strategy"]["blind_vote"] == "TEST"
    assert votes["strategy"]["blind_confidence"] == 0.8
    assert votes["strategy"]["revised_vote"] == "GO"
    assert votes["strategy"]["revised_confidence"] == 0.6
    assert votes["offer_pricing"]["revised_vote"] is None

    serialized = json.dumps(record, ensure_ascii=False)
    assert PRIVATE_SENTINEL not in serialized
    assert "private-source-id" not in serialized


def test_private_memo_and_rebuttal_text_never_reaches_sqlite(tmp_path):
    db_path = tmp_path / "decisions.db"
    store = DecisionMemoryStore(db_path)
    store.capture_decision("user-a", "Should we test pricing?", synthetic_council_result())

    with sqlite3.connect(db_path) as conn:
        for table in ("decisions", "decision_expert_votes", "decision_outcomes"):
            rows = conn.execute(f"SELECT * FROM {table}").fetchall()
            assert PRIVATE_SENTINEL not in json.dumps(rows, ensure_ascii=False)
            assert "private-source-id" not in json.dumps(rows, ensure_ascii=False)


def test_get_and_list_are_scoped_to_owner(tmp_path):
    store = DecisionMemoryStore(tmp_path / "decisions.db")
    decision_id = store.capture_decision(
        "user-a",
        "Should we test pricing?",
        synthetic_council_result(),
    )

    assert store.get_decision("user-b", decision_id) is None
    assert store.list_decisions("user-b") == []
    assert [item["id"] for item in store.list_decisions("user-a")] == [decision_id]


def test_list_filters_by_domain_and_verdict(tmp_path):
    store = DecisionMemoryStore(tmp_path / "decisions.db")
    pricing_id = store.capture_decision(
        "user-a",
        "Pricing decision",
        synthetic_council_result(primary_domain="offer_pricing", verdict=DecisionVote.TEST),
    )
    strategy_id = store.capture_decision(
        "user-a",
        "Strategy decision",
        synthetic_council_result(primary_domain="strategy", verdict=DecisionVote.GO),
    )

    assert [item["id"] for item in store.list_decisions("user-a", primary_domain="strategy")] == [
        strategy_id
    ]
    assert [item["id"] for item in store.list_decisions("user-a", verdict="TEST")] == [pricing_id]
