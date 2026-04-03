"""Unit tests for heuristic agent routing."""

from src.agents.core_agents import Analyst, Strategist
from src.council.routing import QueryIntent, classify_query_intent, route_query, select_agents_for_intent


def test_classify_technical_query() -> None:
    assert classify_query_intent("Fix Python asyncio timeout in FastAPI handler") == QueryIntent.TECHNICAL


def test_classify_strategy_query() -> None:
    assert classify_query_intent("Business roadmap and competitive strategy for Q4") == QueryIntent.STRATEGY


def test_route_full_always_four_agents() -> None:
    decision = route_query("short", "full")
    assert len(decision.agent_classes) == 4
    assert Strategist in decision.agent_classes


def test_route_auto_technical_uses_subset() -> None:
    decision = route_query("debug stack trace in docker deploy", "auto")
    assert decision.intent == QueryIntent.TECHNICAL
    assert len(decision.agent_classes) < 4
    assert Analyst in decision.agent_classes


def test_select_agents_analytical_is_smaller() -> None:
    classes = select_agents_for_intent(QueryIntent.ANALYTICAL)
    assert len(classes) == 2


def test_route_auto_general_has_four() -> None:
    decision = route_query(
        "Ogólne refleksje nad życiem i sensem istnienia w kontekście społecznym",
        "auto",
    )
    assert len(decision.agent_classes) == 4
