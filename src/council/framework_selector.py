from __future__ import annotations

import re

from src.council.council_os_models import FrameworkMatch, FrameworkSelection, ProblemProfile
from src.council.framework_registry import (
    FRAMEWORK_POLICY_VERSION,
    FRAMEWORK_REGISTRY,
    FrameworkDefinition,
)

FRAMEWORK_MIN_SCORE = 5
MAX_SELECTED_FRAMEWORKS = 3
MAX_FRAMEWORKS_PER_EXPERT = 2

_TEST_LANGUAGE = (
    "experiment", "test", "pilot", "validate", "hypothesis",
    "eksperyment", "pilotaż", "hipoteza",
)


def _matches_keyword(text: str, keyword: str) -> bool:
    needle = keyword.casefold().strip()
    if not needle:
        return False
    if " " in needle or "-" in needle or "&" in needle:
        return needle in text
    return re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", text) is not None


def _profile_domain_matches(framework: FrameworkDefinition, domain_id: str) -> bool:
    return domain_id in framework.expert_ids or domain_id in framework.domains


def score_framework(
    framework: FrameworkDefinition,
    query: str,
    profile: ProblemProfile,
    routed_expert_ids: list[str],
) -> tuple[int, list[str]]:
    text = query.casefold()
    score = 0
    reasons: list[str] = []

    if _profile_domain_matches(framework, profile.primary_domain):
        score += 4
        reasons.append("primary_domain")

    secondary_matches = sum(
        1 for domain_id in profile.secondary_domains
        if _profile_domain_matches(framework, domain_id)
    )
    if secondary_matches:
        score += min(secondary_matches * 2, 4)
        reasons.append("secondary_domain")

    if profile.decision_kind in framework.decision_kinds:
        score += 3
        reasons.append("decision_kind")

    routed_matches = sum(1 for expert_id in routed_expert_ids if expert_id in framework.expert_ids)
    if routed_matches:
        score += min(routed_matches * 2, 4)
        reasons.append("routed_expert")

    keyword_matches = sum(1 for keyword in framework.trigger_keywords if _matches_keyword(text, keyword))
    if keyword_matches:
        score += min(keyword_matches, 3)
        reasons.append("trigger_keyword")

    if (
        framework.id == "reversibility_experiment"
        and profile.reversibility == "reversible"
        and any(_matches_keyword(text, keyword) for keyword in _TEST_LANGUAGE)
    ):
        score += 1
        reasons.append("reversibility_bonus")

    if framework.id == "strategic_choice" and (
        profile.reversibility == "hard_to_reverse" or profile.risk_level == "high"
    ):
        score += 1
        reasons.append("high_risk_bonus")

    return score, reasons


def select_frameworks(
    query: str,
    profile: ProblemProfile,
    routed_expert_ids: list[str],
) -> FrameworkSelection:
    order = {framework_id: index for index, framework_id in enumerate(FRAMEWORK_REGISTRY)}
    candidates: list[tuple[FrameworkDefinition, int, list[str]]] = []
    for framework in FRAMEWORK_REGISTRY.values():
        score, reasons = score_framework(framework, query, profile, routed_expert_ids)
        if score >= FRAMEWORK_MIN_SCORE:
            candidates.append((framework, score, reasons))

    candidates.sort(key=lambda item: (-item[1], order[item[0].id], item[0].id))
    selected = candidates[:MAX_SELECTED_FRAMEWORKS]

    by_expert: dict[str, list[str]] = {expert_id: [] for expert_id in routed_expert_ids}
    matches: list[FrameworkMatch] = []
    for framework, score, reasons in selected:
        assigned: list[str] = []
        for expert_id in routed_expert_ids:
            if expert_id not in framework.expert_ids:
                continue
            if len(by_expert[expert_id]) >= MAX_FRAMEWORKS_PER_EXPERT:
                continue
            by_expert[expert_id].append(framework.id)
            assigned.append(expert_id)
        matches.append(
            FrameworkMatch(
                framework_id=framework.id,
                score=score,
                reason_labels=reasons,
                assigned_expert_ids=assigned,
            )
        )

    return FrameworkSelection(
        policy_version=FRAMEWORK_POLICY_VERSION,
        matches=matches,
        by_expert=by_expert,
    )
