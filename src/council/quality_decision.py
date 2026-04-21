"""
Deterministic quality decision engine for deliberation pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


_CONFLICT_KEYWORDS = (
    "tradeoff",
    "trade-off",
    "vs",
    "versus",
    "compare",
    "porownaj",
    "porównaj",
    "konflikt",
    "sprzeczne",
    "sprzecznosc",
    "sprzeczność",
)

_AMBIGUITY_KEYWORDS = (
    "moze",
    "może",
    "zalezy",
    "zależy",
    "it depends",
    "uncertain",
    "nie wiem",
    "niejednoznacz",
)

_SEO_KEYWORDS = (
    "seo",
    "serp",
    "keyword",
    "content",
    "headline",
    "meta description",
    "ctr",
)


@dataclass
class QualityDecision:
    mode: str
    applied_critic: bool
    applied_weighted_voting: bool
    reason: str
    risk_score: float


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def evaluate_quality_mode(
    *,
    quality_mode: str,
    query: str,
    full_query: str,
    use_knowledge_base: bool,
    behavior_preset: str,
    chat_mode: bool,
    has_attachment: bool,
    manual_critic: bool,
    manual_weighted_voting: bool,
) -> QualityDecision:
    """
    Compute deterministic risk score and decide whether to run quality steps.
    """
    mode = (quality_mode or "auto").strip().lower()
    query_text = (query or "").strip()
    query_lower = query_text.lower()
    full_text = (full_query or query_text).strip()

    words = [w for w in full_text.split() if w]
    word_count = len(words)
    risk = 0.0
    reasons: List[str] = []

    if word_count >= 35:
        risk += 0.18
        reasons.append("long_query")
    if word_count >= 80:
        risk += 0.12
        reasons.append("very_long_query")
    if _contains_any(query_lower, _CONFLICT_KEYWORDS):
        risk += 0.24
        reasons.append("conflicting_or_comparative_request")
    if _contains_any(query_lower, _AMBIGUITY_KEYWORDS):
        risk += 0.18
        reasons.append("ambiguity_markers")
    if query_text.count("?") >= 2:
        risk += 0.08
        reasons.append("multi_question_request")
    if behavior_preset in {"with_sources", "kb_only"}:
        risk += 0.22
        reasons.append("strict_evidence_preset")
    if not use_knowledge_base and not has_attachment and word_count >= 25:
        risk += 0.12
        reasons.append("limited_context_available")
    if use_knowledge_base and not has_attachment and word_count >= 50:
        risk += 0.08
        reasons.append("kb_context_may_be_insufficient")
    if chat_mode:
        risk += 0.06
        reasons.append("chat_history_context")
    if _contains_any(query_lower, _SEO_KEYWORDS):
        risk += 0.12
        reasons.append("seo_content_precision")

    risk_score = round(min(risk, 1.0), 3)

    auto_critic = False
    auto_weighted = False
    mode_reason = "mode=auto"

    if mode == "max":
        auto_critic = True
        auto_weighted = True
        mode_reason = "mode=max"
    elif mode == "off":
        mode_reason = "mode=off"
    else:
        if risk_score >= 0.72:
            auto_critic = True
            auto_weighted = True
            mode_reason = "auto_high_risk"
        elif risk_score >= 0.50:
            auto_critic = True
            mode_reason = "auto_medium_high_risk"
        elif risk_score >= 0.36:
            auto_weighted = True
            mode_reason = "auto_medium_risk"
        else:
            mode_reason = "auto_low_risk"

    applied_critic = auto_critic or manual_critic
    applied_weighted = auto_weighted or manual_weighted_voting

    if manual_critic and not auto_critic:
        reasons.append("manual_critic_override")
    if manual_weighted_voting and not auto_weighted:
        reasons.append("manual_weight_override")
    if not reasons:
        reasons.append("baseline_risk")
    reasons.append(mode_reason)

    return QualityDecision(
        mode=mode,
        applied_critic=applied_critic,
        applied_weighted_voting=applied_weighted,
        reason=", ".join(reasons)[:220],
        risk_score=risk_score,
    )
