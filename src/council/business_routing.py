from __future__ import annotations

import re
from collections import Counter

from src.council.council_os_models import DecisionVote, ExpertMemo, ProblemProfile
from src.council.expert_registry import DOMAIN_EXPERT_IDS, EXPERT_REGISTRY, ExpertDefinition

_FALLBACK_ORDER = (
    "strategy",
    "product_customer",
    "marketing",
    "sales",
    "operator",
    "growth",
    "offer_pricing",
)

_HARD_TO_REVERSE_PATTERNS = (
    r"\bacquire (?:the |a )?(?:company|business|competitor)\b",
    r"\bacquisition of (?:the |a )?(?:company|business|competitor)\b",
    r"\bmerger\b",
    r"\bm&a\b",
    r"\bmulti[- ]year\b",
    r"\blong[- ]term (?:legal |capital |commercial )?commitment\b",
    r"\blegal commitment\b",
    r"\birreversible\b",
    r"\bmajor rebrand\b",
    r"\bcompany[- ]wide migration\b",
    r"\bmajor capital allocation\b",
    r"\blarge capital allocation\b",
    r"\bissue equity\b",
    r"\btake on debt\b",
    r"\bmass layoff\b",
    r"\brestructure the company\b",
    r"\bprzejąć (?:spółkę|firmę|konkurenta)\b",
    r"\bfuzj[aię]\b",
    r"\bwieloletni(?:e|ą)? zobowiązani",
    r"\bnieodwracaln",
)

_LOW_RISK_PATTERNS = (
    r"\bsmall\b",
    r"\breversible\b",
    r"\bpilot\b",
    r"\bexperiment\b",
    r"\ba/b test\b",
    r"\btest\b",
    r"\bmał[yae]\b",
    r"\bpilotaż",
    r"\beksperyment",
    r"\bodwracaln",
)

_DECISION_KIND_BY_DOMAIN = {
    "strategy": "strategy",
    "marketing": "marketing",
    "sales": "sales",
    "offer_pricing": "pricing",
    "product_customer": "product_customer",
    "growth": "growth",
    "operator": "operations",
}

_POLISH_KEYWORDS: dict[str, tuple[str, ...]] = {
    "strategy": (
        "strategia",
        "strategiczny",
        "konkurencja",
        "przewaga",
        "ekspansja",
        "przejęcie",
        "fuzja",
        "alokacja zasobów",
    ),
    "marketing": (
        "marketing",
        "pozycjonowanie",
        "marka",
        "komunikat",
        "kategoria",
        "kampania",
        "popyt",
        "segment",
    ),
    "sales": (
        "sprzedaż",
        "sprzedaży",
        "pipeline",
        "prospecting",
        "negocjacje",
        "negocjacja",
        "klient b2b",
        "transakcja",
    ),
    "offer_pricing": (
        "cena",
        "cenę",
        "ceny",
        "pricing",
        "pakiet",
        "pakiety",
        "oferta",
        "monetyzacja",
        "rabat",
        "marża",
    ),
    "product_customer": (
        "produkt",
        "klient",
        "użytkownik",
        "funkcja",
        "onboarding",
        "retencja",
        "churn",
        "badania klientów",
        "adopcja",
    ),
    "growth": (
        "wzrost",
        "akwizycja",
        "referral",
        "aktywacja",
        "kanał",
        "konwersja",
        "lejek",
        "eksperyment",
    ),
    "operator": (
        "operacje",
        "operacyjny",
        "proces",
        "wdrożyć",
        "wdrożenie",
        "egzekucja",
        "właściciel",
        "kpi",
        "rytuał",
        "zespół",
        "odpowiedzialność",
    ),
}


def _matches_keyword(text: str, keyword: str) -> bool:
    needle = keyword.casefold().strip()
    if not needle:
        return False
    if " " in needle or "-" in needle or "&" in needle:
        return needle in text
    return re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", text) is not None


def _score_domains(query: str) -> dict[str, int]:
    text = query.casefold()
    scores: dict[str, int] = {}
    for expert_id in DOMAIN_EXPERT_IDS:
        expert = EXPERT_REGISTRY[expert_id]
        keywords = expert.routing_keywords + _POLISH_KEYWORDS.get(expert_id, ())
        scores[expert_id] = sum(1 for keyword in keywords if _matches_keyword(text, keyword))
    return scores


def profile_problem(query: str) -> ProblemProfile:
    scores = _score_domains(query)
    order_index = {expert_id: index for index, expert_id in enumerate(DOMAIN_EXPERT_IDS)}
    ranked = sorted(
        DOMAIN_EXPERT_IDS,
        key=lambda expert_id: (-scores[expert_id], order_index[expert_id]),
    )
    positive = [expert_id for expert_id in ranked if scores[expert_id] > 0]
    primary = positive[0] if positive else "strategy"
    secondary = [expert_id for expert_id in positive if expert_id != primary]

    lowered = query.casefold()
    hard_to_reverse = any(re.search(pattern, lowered) for pattern in _HARD_TO_REVERSE_PATTERNS)
    explicitly_small = any(re.search(pattern, lowered) for pattern in _LOW_RISK_PATTERNS)

    if hard_to_reverse:
        reversibility = "hard_to_reverse"
        risk_level = "high"
    elif explicitly_small:
        reversibility = "reversible"
        risk_level = "low"
    else:
        reversibility = "reversible"
        risk_level = "medium"

    return ProblemProfile(
        primary_domain=primary,
        secondary_domains=secondary,
        decision_kind=_DECISION_KIND_BY_DOMAIN.get(primary, "general"),
        reversibility=reversibility,
        risk_level=risk_level,
    )


def route_experts(
    profile: ProblemProfile,
    min_experts: int = 4,
    max_experts: int = 5,
) -> list[ExpertDefinition]:
    if min_experts < 1:
        raise ValueError("min_experts must be at least 1")
    if max_experts < min_experts:
        raise ValueError("max_experts must be greater than or equal to min_experts")
    if max_experts > len(DOMAIN_EXPERT_IDS):
        raise ValueError("max_experts exceeds available domain experts")

    selected_ids: list[str] = []
    for expert_id in (profile.primary_domain, *profile.secondary_domains):
        if expert_id in DOMAIN_EXPERT_IDS and expert_id not in selected_ids:
            selected_ids.append(expert_id)
        if len(selected_ids) >= max_experts:
            break

    for expert_id in _FALLBACK_ORDER:
        if len(selected_ids) >= min_experts:
            break
        if expert_id not in selected_ids:
            selected_ids.append(expert_id)

    return [EXPERT_REGISTRY[expert_id] for expert_id in selected_ids[:max_experts]]


def early_consensus_vote(memos: list[ExpertMemo]) -> tuple[DecisionVote | None, float]:
    if not memos:
        return None, 0.0

    counts = Counter(memo.vote for memo in memos)
    vote_order = {vote: index for index, vote in enumerate(DecisionVote)}
    leading_vote, leading_count = min(
        counts.items(),
        key=lambda item: (-item[1], vote_order[item[0]]),
    )
    share = leading_count / len(memos)
    return (leading_vote if share > 0.80 else None), share
