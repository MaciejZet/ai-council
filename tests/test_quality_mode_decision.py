from __future__ import annotations

from src.council.quality_decision import evaluate_quality_mode


def test_quality_mode_off_disables_automatic_quality_steps():
    decision = evaluate_quality_mode(
        quality_mode="off",
        query="Simple question about marketing plan",
        full_query="Simple question about marketing plan",
        use_knowledge_base=True,
        behavior_preset="default",
        chat_mode=False,
        has_attachment=False,
        manual_critic=False,
        manual_weighted_voting=False,
    )
    assert decision.mode == "off"
    assert decision.applied_critic is False
    assert decision.applied_weighted_voting is False


def test_quality_mode_max_enables_both_steps():
    decision = evaluate_quality_mode(
        quality_mode="max",
        query="Compare three conflicting implementation strategies and tradeoffs",
        full_query="Compare three conflicting implementation strategies and tradeoffs",
        use_knowledge_base=True,
        behavior_preset="default",
        chat_mode=False,
        has_attachment=False,
        manual_critic=False,
        manual_weighted_voting=False,
    )
    assert decision.mode == "max"
    assert decision.applied_critic is True
    assert decision.applied_weighted_voting is True


def test_quality_mode_auto_applies_quality_for_higher_risk_queries():
    decision = evaluate_quality_mode(
        quality_mode="auto",
        query=(
            "Porownaj tradeoffy miedzy trzema strategiami SEO i kampanii content, "
            "uwzglednij niejednoznacznosci i ryzyka dla CTR oraz jakosc SERP?"
        ),
        full_query=(
            "Porownaj tradeoffy miedzy trzema strategiami SEO i kampanii content, "
            "uwzglednij niejednoznacznosci i ryzyka dla CTR oraz jakosc SERP?"
        ),
        use_knowledge_base=False,
        behavior_preset="with_sources",
        chat_mode=False,
        has_attachment=False,
        manual_critic=False,
        manual_weighted_voting=False,
    )
    assert decision.mode == "auto"
    assert decision.risk_score >= 0.5
    assert decision.applied_critic is True or decision.applied_weighted_voting is True
    assert decision.reason


def test_quality_mode_auto_keeps_low_risk_queries_lightweight():
    decision = evaluate_quality_mode(
        quality_mode="auto",
        query="What is RAG?",
        full_query="What is RAG?",
        use_knowledge_base=True,
        behavior_preset="default",
        chat_mode=False,
        has_attachment=False,
        manual_critic=False,
        manual_weighted_voting=False,
    )
    assert decision.mode == "auto"
    assert decision.risk_score < 0.36
    assert decision.applied_critic is False
    assert decision.applied_weighted_voting is False
