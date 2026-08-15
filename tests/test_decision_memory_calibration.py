from src.council.council_os_models import (
    CouncilOSResult,
    CouncilVerdict,
    DecisionVote,
    ExpertMemo,
    ProblemProfile,
)
from src.storage.decision_memory import DecisionMemoryStore


def synthetic_result(
    *,
    primary_domain: str,
    verdict: DecisionVote,
    verdict_confidence: float,
    votes: list[tuple[str, DecisionVote, float]],
) -> CouncilOSResult:
    return CouncilOSResult(
        profile=ProblemProfile(
            primary_domain=primary_domain,
            secondary_domains=[],
            decision_kind=primary_domain,
            reversibility="reversible",
            risk_level="medium",
        ),
        routed_experts=[expert_id for expert_id, _, _ in votes],
        memos=[
            ExpertMemo(
                expert_id=expert_id,
                vote=vote,
                recommendation="synthetic",
                confidence=confidence,
                claims=[],
                assumptions=[],
                risks=[],
                what_changes_my_mind=[],
                knowledge_status="ok",
            )
            for expert_id, vote, confidence in votes
        ],
        rebuttals=[],
        red_team=None,
        evidence=None,
        verdict=CouncilVerdict(
            verdict=verdict,
            recommendation="synthetic verdict",
            confidence=verdict_confidence,
            consensus="synthetic consensus",
            key_disagreement="synthetic disagreement",
            minority_report="",
            assumptions=[],
            evidence_gaps=[],
            what_would_change_decision=[],
            next_experiment=None,
        ),
        knowledge_status_by_expert={expert_id: "ok" for expert_id, _, _ in votes},
        errors=[],
    )


def test_outcome_upsert_is_revisable_and_owner_scoped(tmp_path):
    store = DecisionMemoryStore(tmp_path / "decisions.db")
    decision_id = store.capture_decision(
        "user-a",
        "Synthetic decision",
        synthetic_result(
            primary_domain="strategy",
            verdict=DecisionVote.TEST,
            verdict_confidence=0.8,
            votes=[("strategy", DecisionVote.TEST, 0.7)],
        ),
    )

    outcome = store.upsert_outcome(
        "user-a",
        decision_id,
        status="success",
        resolved_vote="TEST",
        experiment_result="12% conversion",
        postmortem="Synthetic postmortem",
        notes=None,
    )
    assert outcome is not None
    assert outcome["status"] == "success"
    assert outcome["resolved_vote"] == "TEST"

    revised = store.upsert_outcome(
        "user-a",
        decision_id,
        status="mixed",
        resolved_vote="GO",
        experiment_result="Follow-up changed the read",
        postmortem="Revised",
        notes="Synthetic",
    )
    assert revised is not None
    assert revised["status"] == "mixed"
    assert revised["resolved_vote"] == "GO"
    assert revised["postmortem"] == "Revised"

    assert (
        store.upsert_outcome(
            "user-b",
            decision_id,
            status="success",
            resolved_vote="GO",
            experiment_result=None,
            postmortem=None,
            notes=None,
        )
        is None
    )


def test_list_filters_by_outcome_status(tmp_path):
    store = DecisionMemoryStore(tmp_path / "decisions.db")
    success_id = store.capture_decision(
        "user-a",
        "Success decision",
        synthetic_result(
            primary_domain="strategy",
            verdict=DecisionVote.TEST,
            verdict_confidence=0.8,
            votes=[("strategy", DecisionVote.TEST, 0.7)],
        ),
    )
    failure_id = store.capture_decision(
        "user-a",
        "Failure decision",
        synthetic_result(
            primary_domain="offer_pricing",
            verdict=DecisionVote.GO,
            verdict_confidence=0.6,
            votes=[("offer_pricing", DecisionVote.GO, 0.6)],
        ),
    )
    unresolved_id = store.capture_decision(
        "user-a",
        "No outcome decision",
        synthetic_result(
            primary_domain="growth",
            verdict=DecisionVote.DEFER,
            verdict_confidence=0.4,
            votes=[("growth", DecisionVote.DEFER, 0.4)],
        ),
    )

    store.upsert_outcome(
        "user-a",
        success_id,
        status="success",
        resolved_vote="TEST",
        experiment_result=None,
        postmortem=None,
        notes=None,
    )
    store.upsert_outcome(
        "user-a",
        failure_id,
        status="failure",
        resolved_vote="NO-GO",
        experiment_result=None,
        postmortem=None,
        notes=None,
    )

    success = store.list_decisions("user-a", outcome_status="success")
    assert [item["id"] for item in success] == [success_id]
    assert unresolved_id not in {item["id"] for item in success}


def test_calibration_uses_blind_votes_and_chairman_verdict(tmp_path):
    store = DecisionMemoryStore(tmp_path / "decisions.db")

    first_id = store.capture_decision(
        "user-a",
        "First decision",
        synthetic_result(
            primary_domain="offer_pricing",
            verdict=DecisionVote.TEST,
            verdict_confidence=0.9,
            votes=[
                ("strategy", DecisionVote.TEST, 0.8),
                ("offer_pricing", DecisionVote.GO, 0.7),
            ],
        ),
    )
    second_id = store.capture_decision(
        "user-a",
        "Second decision",
        synthetic_result(
            primary_domain="strategy",
            verdict=DecisionVote.GO,
            verdict_confidence=0.7,
            votes=[
                ("strategy", DecisionVote.TEST, 0.6),
                ("offer_pricing", DecisionVote.GO, 0.5),
            ],
        ),
    )
    unscored_id = store.capture_decision(
        "user-a",
        "Operationally observed but unresolved",
        synthetic_result(
            primary_domain="growth",
            verdict=DecisionVote.DEFER,
            verdict_confidence=0.3,
            votes=[("strategy", DecisionVote.GO, 0.4)],
        ),
    )

    store.upsert_outcome(
        "user-a",
        first_id,
        status="success",
        resolved_vote="TEST",
        experiment_result=None,
        postmortem=None,
        notes=None,
    )
    store.upsert_outcome(
        "user-a",
        second_id,
        status="success",
        resolved_vote="GO",
        experiment_result=None,
        postmortem=None,
        notes=None,
    )
    store.upsert_outcome(
        "user-a",
        unscored_id,
        status="mixed",
        resolved_vote=None,
        experiment_result="Useful but non-discriminating",
        postmortem=None,
        notes=None,
    )

    report = store.calibration_report("user-a")
    assert report["sample_size"] == 2

    experts = {item["expert_id"]: item for item in report["experts"]}
    strategy = experts["strategy"]
    assert strategy == {
        "expert_id": "strategy",
        "sample_size": 2,
        "correct_count": 1,
        "hit_rate": 0.5,
        "mean_confidence": 0.7,
        "brier_like_error": 0.2,
    }

    pricing = experts["offer_pricing"]
    assert pricing["sample_size"] == 2
    assert pricing["correct_count"] == 1
    assert pricing["hit_rate"] == 0.5
    assert pricing["mean_confidence"] == 0.6
    assert pricing["brier_like_error"] == 0.37

    chairman = experts["chairman"]
    assert chairman["sample_size"] == 2
    assert chairman["correct_count"] == 2
    assert chairman["hit_rate"] == 1.0
    assert chairman["mean_confidence"] == 0.8
    assert chairman["brier_like_error"] == 0.05

    strategy_domain = {
        item["expert_id"]: item for item in report["domains"]["strategy"]
    }
    assert strategy_domain["strategy"]["sample_size"] == 1
    assert strategy_domain["strategy"]["correct_count"] == 0
    assert strategy_domain["chairman"]["correct_count"] == 1


def test_calibration_is_user_scoped_and_empty_without_resolved_votes(tmp_path):
    store = DecisionMemoryStore(tmp_path / "decisions.db")
    decision_id = store.capture_decision(
        "user-a",
        "Unresolved decision",
        synthetic_result(
            primary_domain="strategy",
            verdict=DecisionVote.DEFER,
            verdict_confidence=0.4,
            votes=[("strategy", DecisionVote.DEFER, 0.4)],
        ),
    )
    store.upsert_outcome(
        "user-a",
        decision_id,
        status="inconclusive",
        resolved_vote=None,
        experiment_result=None,
        postmortem=None,
        notes=None,
    )

    assert store.calibration_report("user-a") == {
        "sample_size": 0,
        "experts": [],
        "domains": {},
    }
    assert store.calibration_report("user-b") == {
        "sample_size": 0,
        "experts": [],
        "domains": {},
    }
