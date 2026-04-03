"""
Heuristic query routing: classify intent and select a subset of core agents
to reduce tokens when full council is unnecessary.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Type

from src.agents.core_agents import Strategist, Analyst, Practitioner, Expert


class QueryIntent(str, Enum):
    GENERAL = "general"
    STRATEGY = "strategy"
    TECHNICAL = "technical"
    OPERATIONAL = "operational"
    CREATIVE = "creative"
    ANALYTICAL = "analytical"


@dataclass
class RoutingDecision:
    intent: QueryIntent
    agent_classes: List[Type]
    reason: str


_TECH = re.compile(
    r"\b(api|code|debug|error|stack|python|typescript|sql|docker|kubernetes|"
    r"deploy|repo|git|compile|exception|async|http|json|xml)\b",
    re.I,
)
_STRATEGY = re.compile(
    r"\b(strategy|strateg|roadmap|vision|okr|goal|invest|risk|market entry|"
    r"competitive|swot|business model|priorit)\b",
    re.I,
)
_OPS = re.compile(
    r"\b(process|workflow|checklist|implement|how do i|step|operational|"
    r"day-to-day|tool|automat)\b",
    re.I,
)
_CREATIVE = re.compile(
    r"\b(write|copy|headline|brand|story|narrative|tone|voice|campaign|"
    r"social media post|content idea)\b",
    re.I,
)


def classify_query_intent(query: str) -> QueryIntent:
    q = query.strip()
    if not q:
        return QueryIntent.GENERAL
    if _TECH.search(q):
        return QueryIntent.TECHNICAL
    if _STRATEGY.search(q):
        return QueryIntent.STRATEGY
    if _CREATIVE.search(q):
        return QueryIntent.CREATIVE
    if _OPS.search(q):
        return QueryIntent.OPERATIONAL
    if len(q) < 120 and "?" in q:
        return QueryIntent.ANALYTICAL
    return QueryIntent.GENERAL


def select_agents_for_intent(intent: QueryIntent) -> List[Type]:
    """Return ordered list of agent classes (excluding Synthesizer)."""
    if intent == QueryIntent.TECHNICAL:
        return [Analyst, Expert, Practitioner]
    if intent == QueryIntent.STRATEGY:
        return [Strategist, Analyst, Expert]
    if intent == QueryIntent.CREATIVE:
        return [Practitioner, Expert, Strategist]
    if intent == QueryIntent.OPERATIONAL:
        return [Practitioner, Analyst, Strategist]
    if intent == QueryIntent.ANALYTICAL:
        return [Analyst, Expert]
    return [Strategist, Analyst, Practitioner, Expert]


def route_query(query: str, mode: str = "auto") -> RoutingDecision:
    """
    mode: 'auto' uses subset heuristics; 'full' always uses all four core agents.
    """
    if mode == "full":
        return RoutingDecision(
            intent=QueryIntent.GENERAL,
            agent_classes=[Strategist, Analyst, Practitioner, Expert],
            reason="routing_mode=full: all core agents",
        )
    intent = classify_query_intent(query)
    classes = select_agents_for_intent(intent)
    return RoutingDecision(
        intent=intent,
        agent_classes=classes,
        reason=f"intent={intent.value}: optimized subset",
    )
