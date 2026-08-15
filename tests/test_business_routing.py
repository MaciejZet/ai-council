import importlib

from src.council.council_os_models import DecisionVote, ExpertMemo

routing = importlib.import_module("src.council.business_routing")


def routed_ids(query: str) -> list[str]:
    return [expert.id for expert in routing.route_experts(routing.profile_problem(query))]


def memo(expert_id: str, vote: DecisionVote) -> ExpertMemo:
    return ExpertMemo(
        expert_id=expert_id,
        vote=vote,
        recommendation="synthetic",
        confidence=0.7,
        knowledge_status="ok",
    )


def test_pricing_routes_offer_expert_and_stays_bounded():
    ids = routed_ids("Should we raise B2B pricing and change plan packaging?")
    assert "offer_pricing" in ids
    assert 4 <= len(ids) <= 5


def test_growth_routes_growth_expert():
    assert "growth" in routed_ids("How should we increase acquisition, referral and activation growth?")


def test_operations_routes_operator():
    assert "operator" in routed_ids("How should we implement this operating process, owners and KPI cadence?")


def test_irreversible_decision_is_high_risk():
    profile = routing.profile_problem(
        "Should we acquire the company and sign a multi-year legal commitment?"
    )
    assert profile.reversibility == "hard_to_reverse"
    assert profile.risk_level == "high"


def test_small_experiment_is_low_risk_and_reversible():
    profile = routing.profile_problem("Should we run a small reversible pilot experiment next week?")
    assert profile.reversibility == "reversible"
    assert profile.risk_level == "low"


def test_early_consensus_requires_strictly_more_than_eighty_percent():
    four_of_five = [memo(str(i), DecisionVote.GO) for i in range(4)] + [
        memo("x", DecisionVote.TEST)
    ]
    vote, share = routing.early_consensus_vote(four_of_five)
    assert share == 0.8
    assert vote is None

    unanimous = [memo(str(i), DecisionVote.GO) for i in range(5)]
    vote, share = routing.early_consensus_vote(unanimous)
    assert vote == DecisionVote.GO
    assert share == 1.0
