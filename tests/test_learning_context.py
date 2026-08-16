from src.council.council_os_models import DecisionVote, ExpertMemo, ProblemProfile
from src.council.learning_context import LearningContextBuilder, sample_strength


class FakeStore:
    def __init__(self, decisions, predictions):
        self.decisions = decisions
        self.predictions = predictions

    def resolved_decisions(self, user_id, *, primary_domain=None):
        assert user_id == "u1"
        return list(self.decisions)

    def expert_predictions(self, user_id, expert_ids, primary_domain):
        assert user_id == "u1"
        return [
            prediction
            for prediction in self.predictions
            if prediction["expert_id"] in expert_ids
            and prediction["primary_domain"] == primary_domain
        ]


def memo(expert, vote, confidence=0.7):
    return ExpertMemo(expert_id=expert, vote=vote, recommendation="x", confidence=confidence)


def test_sample_strength_thresholds():
    assert [sample_strength(n) for n in [0, 4, 5, 14, 15]] == [
        "none",
        "none",
        "weak",
        "weak",
        "normal",
    ]


def test_analogy_ranking_is_deterministic_and_capped_at_three():
    decisions = []
    rows = [
        ("growth", "pricing", "reversible", "medium", "2026-03-04"),
        ("growth", "pricing", "reversible", "high", "2026-03-05"),
        ("growth", "general", "reversible", "medium", "2026-03-06"),
        ("sales", "pricing", "reversible", "medium", "2026-03-07"),
    ]
    for index, (domain, kind, reversibility, risk, updated) in enumerate(rows):
        decisions.append(
            {
                "decision_id": f"d{index}",
                "created_at": "x",
                "primary_domain": domain,
                "secondary_domains": [],
                "secondary_domains_json": "[]",
                "decision_kind": kind,
                "reversibility": reversibility,
                "risk_level": risk,
                "verdict": "TEST",
                "verdict_confidence": 0.6,
                "outcome_status": "success",
                "resolved_vote": "GO",
                "outcome_updated_at": updated,
            }
        )
    profile = ProblemProfile(
        primary_domain="growth",
        decision_kind="pricing",
        reversibility="reversible",
        risk_level="medium",
    )

    context = LearningContextBuilder(FakeStore(decisions, [])).build(
        "u1", profile, ["growth"], [memo("growth", DecisionVote.GO)]
    )

    assert [analogy.decision_id for analogy in context.analog_decisions] == ["d0", "d1", "d2"]
    assert context.analog_decisions[0].similarity_score == 11


def test_calibration_and_normal_strength_protected_minority():
    predictions = []
    for index in range(15):
        predictions.extend(
            [
                {
                    "decision_id": f"a{index}",
                    "expert_id": "growth",
                    "predicted_vote": "NO-GO",
                    "confidence": 0.8,
                    "resolved_vote": "NO-GO",
                    "primary_domain": "growth",
                },
                {
                    "decision_id": f"b{index}",
                    "expert_id": "sales",
                    "predicted_vote": "GO",
                    "confidence": 0.9,
                    "resolved_vote": "NO-GO",
                    "primary_domain": "growth",
                },
                {
                    "decision_id": f"c{index}",
                    "expert_id": "marketing",
                    "predicted_vote": "GO",
                    "confidence": 0.9,
                    "resolved_vote": "NO-GO",
                    "primary_domain": "growth",
                },
            ]
        )

    context = LearningContextBuilder(FakeStore([], predictions)).build(
        "u1",
        ProblemProfile(primary_domain="growth"),
        ["growth", "sales", "marketing"],
        [
            memo("growth", DecisionVote.NO_GO),
            memo("sales", DecisionVote.GO),
            memo("marketing", DecisionVote.GO),
        ],
    )

    signals = {signal.expert_id: signal for signal in context.expert_signals}
    assert signals["growth"].sample_strength == "normal"
    assert signals["growth"].hit_rate == 1.0
    assert context.protected_minority_expert_ids == ["growth"]


def test_weak_minority_is_not_protected():
    predictions = [
        {
            "decision_id": str(index),
            "expert_id": "growth",
            "predicted_vote": "NO-GO",
            "confidence": 0.8,
            "resolved_vote": "NO-GO",
            "primary_domain": "growth",
        }
        for index in range(5)
    ]

    context = LearningContextBuilder(FakeStore([], predictions)).build(
        "u1",
        ProblemProfile(primary_domain="growth"),
        ["growth", "sales", "marketing"],
        [
            memo("growth", DecisionVote.NO_GO),
            memo("sales", DecisionVote.GO),
            memo("marketing", DecisionVote.GO),
        ],
    )

    assert context.protected_minority_expert_ids == []


def test_context_has_no_historical_free_text():
    decisions = [
        {
            "decision_id": "d",
            "created_at": "x",
            "primary_domain": "growth",
            "secondary_domains": [],
            "secondary_domains_json": "[]",
            "decision_kind": "general",
            "reversibility": "reversible",
            "risk_level": "medium",
            "verdict": "GO",
            "verdict_confidence": 0.8,
            "outcome_status": "success",
            "resolved_vote": "GO",
            "outcome_updated_at": "2026",
            "query": "PRIVATE_QUERY",
            "postmortem": "PRIVATE_POST",
        }
    ]

    context = LearningContextBuilder(FakeStore(decisions, [])).build(
        "u1", ProblemProfile(primary_domain="growth"), [], []
    )
    dumped = context.model_dump_json()

    assert "PRIVATE_QUERY" not in dumped
    assert "PRIVATE_POST" not in dumped


def test_bias_alerts_require_weak_or_better_history():
    weak_predictions = [
        {
            "decision_id": f"weak-{index}",
            "expert_id": "growth",
            "predicted_vote": "GO",
            "confidence": 0.9,
            "resolved_vote": "NO-GO",
            "primary_domain": "growth",
        }
        for index in range(5)
    ]
    low_sample_predictions = weak_predictions[:4]

    weak = LearningContextBuilder(FakeStore([], weak_predictions)).build(
        "u1",
        ProblemProfile(primary_domain="growth"),
        ["growth"],
        [memo("growth", DecisionVote.GO)],
    )
    low_sample = LearningContextBuilder(FakeStore([], low_sample_predictions)).build(
        "u1",
        ProblemProfile(primary_domain="growth"),
        ["growth"],
        [memo("growth", DecisionVote.GO)],
    )

    assert "overconfidence" in weak.bias_alerts
    assert "go_bias" in weak.bias_alerts
    assert low_sample.bias_alerts == []
