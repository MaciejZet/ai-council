from src.council.council_os_models import (
    CouncilOSResult,
    CouncilVerdict,
    DecisionVote,
    FrameworkAssessment,
    FrameworkFactMisclassification,
    FrameworkMatch,
    FrameworkSelection,
    FrameworkSelectionSummary,
    ProblemProfile,
)


def test_framework_models_are_sanitized_and_serializable():
    selection = FrameworkSelection(
        policy_version="framework-selector-v1",
        matches=[
            FrameworkMatch(
                framework_id="value_equation",
                score=8,
                reason_labels=["primary_domain", "routed_expert"],
                assigned_expert_ids=["offer_pricing"],
            )
        ],
        by_expert={"offer_pricing": ["value_equation"]},
    )
    summary = FrameworkSelectionSummary(
        policy_version=selection.policy_version,
        selected_framework_ids=["value_equation"],
        by_expert=selection.by_expert,
        reason_labels_by_framework={"value_equation": ["primary_domain"]},
        retrieval_status_by_expert={"offer_pricing": "framework_match"},
        rejected_framework_ids=[],
        selector_error_labels=[],
    )

    payload = summary.model_dump(mode="json")
    assert "book_text" not in payload
    assert payload["selected_framework_ids"] == ["value_equation"]


def test_framework_fact_misclassification_uses_stable_claim_ref():
    item = FrameworkFactMisclassification(
        claim_ref="marketing:2",
        framework_id="positioning_category",
        reason="framework_rule_presented_as_fact",
    )
    assessment = FrameworkAssessment(misclassified_fact_claims=[item])

    assert assessment.misclassified_fact_claims[0].claim_ref == "marketing:2"


def test_council_result_keeps_framework_summary_backward_compatible():
    result = CouncilOSResult(
        profile=ProblemProfile(primary_domain="strategy"),
        routed_experts=["strategy"],
        verdict=CouncilVerdict(
            verdict=DecisionVote.DEFER,
            recommendation="Need evidence",
            confidence=0.2,
            consensus="low",
            key_disagreement="unknown",
            minority_report="",
        ),
    )

    assert result.framework_selection_summary is None


def _profile(primary, *, secondary=None, decision_kind="general", reversibility="reversible", risk="medium"):
    return ProblemProfile(
        primary_domain=primary,
        secondary_domains=secondary or [],
        decision_kind=decision_kind,
        reversibility=reversibility,
        risk_level=risk,
    )


def test_pricing_query_prefers_value_equation_and_respects_caps():
    from src.council.framework_selector import select_frameworks

    selection = select_frameworks(
        "Should we raise price and change packaging for our B2B offer?",
        _profile("offer_pricing", secondary=["sales"], decision_kind="pricing"),
        ["offer_pricing", "sales", "strategy", "marketing"],
    )

    assert selection.matches[0].framework_id == "value_equation"
    assert len(selection.matches) <= 3
    assert all(len(items) <= 2 for items in selection.by_expert.values())


def test_selector_routes_representative_frameworks_deterministically():
    from src.council.framework_selector import select_frameworks

    cases = [
        ("Should we enter this market and build a moat?", _profile("strategy", decision_kind="strategy"), ["strategy", "operator", "marketing", "product_customer"], "strategic_choice"),
        ("How should we position this category for a new segment?", _profile("marketing", decision_kind="marketing"), ["marketing", "sales", "strategy", "growth"], "positioning_category"),
        ("Do customers really have this job to be done?", _profile("product_customer", decision_kind="product_customer"), ["product_customer", "growth", "strategy", "marketing"], "customer_job_evidence"),
        ("Can referrals create a compounding growth loop?", _profile("growth", decision_kind="growth"), ["growth", "marketing", "product_customer", "strategy"], "growth_loop"),
        ("What is the operational bottleneck and owner?", _profile("operator", decision_kind="operations"), ["operator", "strategy", "product_customer", "marketing"], "operating_constraint"),
    ]

    for query, profile, experts, expected in cases:
        first = select_frameworks(query, profile, experts)
        second = select_frameworks(query, profile, experts)
        assert first == second
        assert first.matches[0].framework_id == expected


def test_reversible_experiment_lens_is_selected_for_explicit_test_language():
    from src.council.framework_selector import select_frameworks

    selection = select_frameworks(
        "Run a small reversible experiment before committing budget",
        _profile("growth", decision_kind="growth", reversibility="reversible", risk="low"),
        ["growth", "product_customer", "operator", "strategy"],
    )

    assert "reversibility_experiment" in [item.framework_id for item in selection.matches]


def test_selector_can_return_empty_selection():
    from src.council.framework_selector import select_frameworks

    selection = select_frameworks(
        "Decide an unrelated administrative matter",
        _profile("legal", decision_kind="legal"),
        ["legal"],
    )

    assert selection.matches == []
    assert selection.by_expert == {"legal": []}


def test_score_threshold_includes_five_and_excludes_four():
    from src.council.framework_registry import FRAMEWORK_REGISTRY
    from src.council.framework_selector import FRAMEWORK_MIN_SCORE, score_framework

    framework = FRAMEWORK_REGISTRY["growth_loop"]
    five_score, _ = score_framework(
        framework,
        "referral",
        _profile("legal", decision_kind="legal"),
        ["growth", "marketing"],
    )
    four_score, _ = score_framework(
        framework,
        "unrelated",
        _profile("legal", decision_kind="legal"),
        ["growth", "marketing"],
    )

    assert FRAMEWORK_MIN_SCORE == 5
    assert five_score == 5
    assert four_score == 4
