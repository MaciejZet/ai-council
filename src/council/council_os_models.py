from __future__ import annotations

import json
import re
from enum import StrEnum
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.council.framework_registry import FRAMEWORK_POLICY_VERSION, FRAMEWORK_REGISTRY

KnowledgeStatus = Literal["ok", "no_matches", "disabled", "unavailable"]
Reversibility = Literal["reversible", "hard_to_reverse"]
RiskLevel = Literal["low", "medium", "high"]
SampleStrength = Literal["none", "weak", "normal"]
LearningStatus = Literal["ok", "insufficient_history", "disabled", "unavailable"]
LiveEvidenceStatus = Literal["ok", "no_matches", "disabled", "unavailable"]


class DecisionVote(StrEnum):
    GO = "GO"
    NO_GO = "NO-GO"
    TEST = "TEST"
    DEFER = "DEFER"


class ClaimLabel(StrEnum):
    FACT = "F"
    ASSUMPTION = "A"
    INFERENCE = "I"
    FRAMEWORK = "FMW"
    OPINION = "O"


class ProblemProfile(BaseModel):
    primary_domain: str
    secondary_domains: list[str] = Field(default_factory=list)
    decision_kind: str = "general"
    reversibility: Reversibility = "reversible"
    risk_level: RiskLevel = "medium"


class Claim(BaseModel):
    label: ClaimLabel
    text: str
    source_ids: list[str] = Field(default_factory=list)


class ExpertMemo(BaseModel):
    expert_id: str
    vote: DecisionVote
    recommendation: str
    confidence: float = Field(ge=0.0, le=1.0)
    claims: list[Claim] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    what_changes_my_mind: list[str] = Field(default_factory=list)
    knowledge_status: KnowledgeStatus = "disabled"


class Rebuttal(BaseModel):
    expert_id: str
    strongest_agreement: str
    strongest_disagreement: str
    assumption_to_test: str
    revised_vote: DecisionVote
    revised_confidence: float = Field(ge=0.0, le=1.0)


class RedTeamReport(BaseModel):
    failure_modes: list[str] = Field(default_factory=list)
    challenged_assumptions: list[str] = Field(default_factory=list)
    double_crux_questions: list[str] = Field(default_factory=list)
    premature_consensus: bool = False
    contrarian_case: str = ""
    parse_error: bool = False


class ExpertCalibrationSignal(BaseModel):
    expert_id: str
    primary_domain: str
    sample_size: int = Field(ge=0)
    sample_strength: SampleStrength = "none"
    hit_rate: float = Field(ge=0.0, le=1.0)
    mean_confidence: float = Field(ge=0.0, le=1.0)
    brier_like_error: float = Field(ge=0.0)
    confidence_bias: float
    reliability_rank: int | None = None
    flags: list[str] = Field(default_factory=list)


class AnalogDecision(BaseModel):
    decision_id: str
    primary_domain: str
    decision_kind: str
    reversibility: Reversibility
    risk_level: RiskLevel
    verdict: DecisionVote
    verdict_confidence: float = Field(ge=0.0, le=1.0)
    resolved_vote: DecisionVote
    outcome_status: str
    similarity_score: int = Field(ge=0)
    matching_dimensions: list[str] = Field(default_factory=list)


class HistoricalAnalogyRejection(BaseModel):
    decision_id: str
    reason: str


class HistoricalContextAssessment(BaseModel):
    accepted_analogy_ids: list[str] = Field(default_factory=list)
    rejected_analogies: list[HistoricalAnalogyRejection] = Field(default_factory=list)
    usable_calibration_expert_ids: list[str] = Field(default_factory=list)
    too_weak_calibration_expert_ids: list[str] = Field(default_factory=list)
    current_evidence_conflicts: list[str] = Field(default_factory=list)


class LearningContext(BaseModel):
    status: LearningStatus = "disabled"
    expert_signals: list[ExpertCalibrationSignal] = Field(default_factory=list)
    analog_decisions: list[AnalogDecision] = Field(default_factory=list)
    bias_alerts: list[str] = Field(default_factory=list)
    protected_minority_expert_ids: list[str] = Field(default_factory=list)
    scored_history_count: int = Field(default=0, ge=0)
    error_labels: list[str] = Field(default_factory=list)


class LearningContextSummary(BaseModel):
    status: LearningStatus = "disabled"
    scored_history_count: int = Field(default=0, ge=0)
    analogy_count: int = Field(default=0, ge=0)
    active_sample_strengths: dict[str, SampleStrength] = Field(default_factory=dict)
    bias_alerts: list[str] = Field(default_factory=list)
    protected_minority_expert_ids: list[str] = Field(default_factory=list)
    rejected_analogies: list[HistoricalAnalogyRejection] = Field(default_factory=list)
    influenced_final_stage: bool = False


_FRAMEWORK_REASON_LABELS = {
    "primary_domain",
    "secondary_domain",
    "decision_kind",
    "routed_expert",
    "trigger_keyword",
    "reversibility_bonus",
    "high_risk_bonus",
}
_FRAMEWORK_MISCLASSIFICATION_REASONS = {
    "framework_rule_presented_as_fact",
    "framework_without_independent_evidence",
    "framework_claim_mislabeled",
}
_FRAMEWORK_OVERREACH_LABELS = {
    "correlated_framework_reasoning",
    "framework_inapplicable",
    "framework_as_evidence",
    "framework_overreach",
}
_FRAMEWORK_RETRIEVAL_STATUSES = {
    "framework_match",
    "framework_no_match_fallback_ok",
    "framework_no_match_fallback_no_matches",
    "framework_unavailable",
    "framework_disabled",
    "base_retrieval",
}


class FrameworkMatch(BaseModel):
    framework_id: str
    score: int
    reason_labels: list[str] = Field(default_factory=list)
    assigned_expert_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def sanitize_public_metadata(self) -> "FrameworkMatch":
        framework = FRAMEWORK_REGISTRY.get(self.framework_id)
        self.reason_labels = [
            label for label in dict.fromkeys(self.reason_labels) if label in _FRAMEWORK_REASON_LABELS
        ]
        if framework is None:
            self.assigned_expert_ids = []
        else:
            self.assigned_expert_ids = [
                expert_id
                for expert_id in dict.fromkeys(self.assigned_expert_ids)
                if expert_id in framework.expert_ids
            ]
        return self


class FrameworkSelection(BaseModel):
    model_config = ConfigDict(revalidate_instances="always")

    policy_version: str
    matches: list[FrameworkMatch] = Field(default_factory=list)
    by_expert: dict[str, list[str]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def enforce_registry_contract(self) -> "FrameworkSelection":
        counts: dict[str, int] = {}
        by_expert: dict[str, list[str]] = {
            expert_id: []
            for expert_id, framework_ids in self.by_expert.items()
            if not framework_ids
        }
        matches: list[FrameworkMatch] = []
        seen_frameworks: set[str] = set()
        for match in self.matches:
            if len(matches) >= 3 or match.framework_id in seen_frameworks:
                continue
            framework = FRAMEWORK_REGISTRY.get(match.framework_id)
            if framework is None:
                continue
            assigned: list[str] = []
            for expert_id in match.assigned_expert_ids:
                if expert_id not in framework.expert_ids or counts.get(expert_id, 0) >= 2:
                    continue
                counts[expert_id] = counts.get(expert_id, 0) + 1
                by_expert.setdefault(expert_id, []).append(framework.id)
                assigned.append(expert_id)
            if not assigned:
                continue
            seen_frameworks.add(framework.id)
            matches.append(match.model_copy(update={"assigned_expert_ids": assigned}))
        self.policy_version = FRAMEWORK_POLICY_VERSION
        self.matches = matches
        self.by_expert = by_expert
        return self


class FrameworkFactMisclassification(BaseModel):
    claim_ref: str
    framework_id: str | None = None
    reason: str

    @field_validator("reason")
    @classmethod
    def sanitize_reason(cls, value: str) -> str:
        return value if value in _FRAMEWORK_MISCLASSIFICATION_REASONS else "framework_claim_mislabeled"


class FrameworkAssessment(BaseModel):
    misclassified_fact_claims: list[FrameworkFactMisclassification] = Field(default_factory=list)
    framework_overreach_labels: list[str] = Field(default_factory=list)
    rejected_framework_ids: list[str] = Field(default_factory=list)

    @field_validator("framework_overreach_labels")
    @classmethod
    def sanitize_overreach_labels(cls, values: list[str]) -> list[str]:
        return list(
            dict.fromkeys(
                value if value in _FRAMEWORK_OVERREACH_LABELS else "framework_overreach"
                for value in values
            )
        )


class FrameworkSelectionSummary(BaseModel):
    policy_version: str
    selected_framework_ids: list[str] = Field(default_factory=list)
    by_expert: dict[str, list[str]] = Field(default_factory=dict)
    reason_labels_by_framework: dict[str, list[str]] = Field(default_factory=dict)
    retrieval_status_by_expert: dict[str, str] = Field(default_factory=dict)
    rejected_framework_ids: list[str] = Field(default_factory=list)
    selector_error_labels: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def sanitize_summary(self) -> "FrameworkSelectionSummary":
        known_ids = set(FRAMEWORK_REGISTRY)
        self.policy_version = FRAMEWORK_POLICY_VERSION
        self.selected_framework_ids = [
            framework_id
            for framework_id in dict.fromkeys(self.selected_framework_ids)
            if framework_id in known_ids
        ][:3]
        self.by_expert = {
            expert_id: [
                framework_id
                for framework_id in dict.fromkeys(framework_ids)
                if framework_id in known_ids
            ][:2]
            for expert_id, framework_ids in self.by_expert.items()
            if framework_ids
        }
        self.reason_labels_by_framework = {
            framework_id: [
                label for label in dict.fromkeys(labels) if label in _FRAMEWORK_REASON_LABELS
            ]
            for framework_id, labels in self.reason_labels_by_framework.items()
            if framework_id in known_ids
        }
        self.retrieval_status_by_expert = {
            expert_id: (
                status if status in _FRAMEWORK_RETRIEVAL_STATUSES else "framework_unavailable"
            )
            for expert_id, status in self.retrieval_status_by_expert.items()
        }
        self.rejected_framework_ids = [
            framework_id
            for framework_id in dict.fromkeys(self.rejected_framework_ids)
            if framework_id in known_ids
        ]
        self.selector_error_labels = [
            label for label in dict.fromkeys(self.selector_error_labels)
            if label == "framework_selector_unavailable"
        ]
        return self


_LIVE_EVIDENCE_ERROR_LABELS = {
    "live_query_redacted",
    "partial_search_failure",
    "live_evidence_unavailable",
}
_LIVE_EVIDENCE_REJECTION_REASONS = {
    "weak_relevance",
    "low_credibility",
    "stale_or_undated",
    "unsupported_snippet",
    "contradicted",
    "not_independent",
    "unsafe_source_text",
    "other_evidence_issue",
}
_LIVE_EVIDENCE_CONFLICT_LABELS = {
    "sources_disagree",
    "syndicated_not_independent",
    "freshness_conflict",
    "live_vs_private_evidence_conflict",
    "live_vs_historical_conflict",
    "other_source_conflict",
}
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _clean_external_text(value: str, limit: int) -> str:
    return _CONTROL_CHARS_RE.sub("", str(value)).strip()[:limit]


class LiveEvidenceSource(BaseModel):
    evidence_id: str
    query_index: int = Field(ge=0, le=1)
    title: str = ""
    canonical_url: str
    domain: str
    snippet: str = ""
    relevance_score: float = 0.0
    fetched_at: str

    @field_validator("title")
    @classmethod
    def sanitize_title(cls, value: str) -> str:
        return _clean_external_text(value, 180)

    @field_validator("snippet")
    @classmethod
    def sanitize_snippet(cls, value: str) -> str:
        return _clean_external_text(value, 600)

    @field_validator("canonical_url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("live evidence URL must use http/https with a hostname")
        return value

    @field_validator("domain")
    @classmethod
    def normalize_domain(cls, value: str) -> str:
        domain = str(value).strip().casefold()
        return domain[4:] if domain.startswith("www.") else domain

    @field_validator("relevance_score")
    @classmethod
    def clamp_score(cls, value: float) -> float:
        return max(0.0, min(1.0, float(value)))


class LiveEvidenceContext(BaseModel):
    status: LiveEvidenceStatus = "disabled"
    query_count: int = Field(default=0, ge=0, le=2)
    sources: list[LiveEvidenceSource] = Field(default_factory=list)
    error_labels: list[str] = Field(default_factory=list)

    @field_validator("error_labels")
    @classmethod
    def sanitize_error_labels(cls, values: list[str]) -> list[str]:
        return [
            value for value in dict.fromkeys(values)
            if value in _LIVE_EVIDENCE_ERROR_LABELS
        ]


class LiveEvidenceRejection(BaseModel):
    evidence_id: str
    reason: str

    @field_validator("reason")
    @classmethod
    def sanitize_reason(cls, value: str) -> str:
        return value if value in _LIVE_EVIDENCE_REJECTION_REASONS else "other_evidence_issue"


class LiveEvidenceAssessment(BaseModel):
    accepted_evidence_ids: list[str] = Field(default_factory=list)
    rejected_evidence: list[LiveEvidenceRejection] = Field(default_factory=list)
    source_conflict_labels: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def sanitize_assessment(self) -> "LiveEvidenceAssessment":
        self.accepted_evidence_ids = list(dict.fromkeys(self.accepted_evidence_ids))
        accepted = set(self.accepted_evidence_ids)
        seen_rejected: set[str] = set()
        rejected: list[LiveEvidenceRejection] = []
        for item in self.rejected_evidence:
            if item.evidence_id in accepted or item.evidence_id in seen_rejected:
                continue
            seen_rejected.add(item.evidence_id)
            rejected.append(item)
        self.rejected_evidence = rejected
        self.source_conflict_labels = list(
            dict.fromkeys(
                value if value in _LIVE_EVIDENCE_CONFLICT_LABELS else "other_source_conflict"
                for value in self.source_conflict_labels
            )
        )
        return self


class LiveEvidenceSummary(BaseModel):
    status: LiveEvidenceStatus = "disabled"
    query_count: int = Field(default=0, ge=0, le=2)
    source_count: int = Field(default=0, ge=0, le=10)
    source_domains: list[str] = Field(default_factory=list)
    accepted_evidence_ids: list[str] = Field(default_factory=list)
    rejected_evidence_ids: list[str] = Field(default_factory=list)
    error_labels: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def sanitize_summary(self) -> "LiveEvidenceSummary":
        self.source_domains = list(
            dict.fromkeys(
                domain[4:] if domain.casefold().startswith("www.") else domain.casefold()
                for domain in (str(value).strip() for value in self.source_domains)
                if domain
            )
        )
        self.accepted_evidence_ids = list(dict.fromkeys(self.accepted_evidence_ids))
        accepted = set(self.accepted_evidence_ids)
        self.rejected_evidence_ids = [
            value for value in dict.fromkeys(self.rejected_evidence_ids) if value not in accepted
        ]
        self.error_labels = [
            value for value in dict.fromkeys(self.error_labels)
            if value in _LIVE_EVIDENCE_ERROR_LABELS
        ]
        return self


class EvidenceAssessment(BaseModel):
    supported_claims: list[str] = Field(default_factory=list)
    weak_or_unsupported_claims: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    evidence_gaps: list[str] = Field(default_factory=list)
    knowledge_status_by_expert: dict[str, KnowledgeStatus] = Field(default_factory=dict)
    framework_fact_confusions: list[str] = Field(default_factory=list)
    historical_context: HistoricalContextAssessment | None = None
    framework_assessment: FrameworkAssessment = Field(default_factory=FrameworkAssessment)
    live_evidence: LiveEvidenceAssessment = Field(default_factory=LiveEvidenceAssessment)
    parse_error: bool = False


class NextExperiment(BaseModel):
    action: str
    metric: str
    threshold: str
    timeline: str
    kill_criteria: str


class CouncilVerdict(BaseModel):
    verdict: DecisionVote
    recommendation: str
    confidence: float = Field(ge=0.0, le=1.0)
    consensus: str
    key_disagreement: str
    minority_report: str
    assumptions: list[str] = Field(default_factory=list)
    evidence_gaps: list[str] = Field(default_factory=list)
    what_would_change_decision: list[str] = Field(default_factory=list)
    next_experiment: NextExperiment | None = None


class CouncilOSResult(BaseModel):
    profile: ProblemProfile
    routed_experts: list[str]
    memos: list[ExpertMemo] = Field(default_factory=list)
    rebuttals: list[Rebuttal] = Field(default_factory=list)
    red_team: RedTeamReport | None = None
    evidence: EvidenceAssessment | None = None
    verdict: CouncilVerdict
    knowledge_status_by_expert: dict[str, KnowledgeStatus] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    learning_context_summary: LearningContextSummary | None = None
    framework_selection_summary: FrameworkSelectionSummary | None = None
    live_evidence_summary: LiveEvidenceSummary | None = None

    @model_validator(mode="after")
    def normalize_framework_retrieval_diagnostics(self) -> "CouncilOSResult":
        summary = self.framework_selection_summary
        if summary is None:
            return self
        for expert_id, knowledge_status in self.knowledge_status_by_expert.items():
            if not summary.by_expert.get(expert_id):
                continue
            if knowledge_status == "disabled":
                summary.retrieval_status_by_expert[expert_id] = "framework_disabled"
            elif knowledge_status == "unavailable":
                summary.retrieval_status_by_expert[expert_id] = "framework_unavailable"
        return self


def extract_json_object(text: str) -> dict:
    raw = text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*([\s\S]*?)\s*```", raw, flags=re.IGNORECASE)
    if fenced:
        raw = fenced.group(1).strip()

    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end < start:
        raise ValueError("structured output does not contain a JSON object")

    try:
        payload = json.loads(raw[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError("structured output contains malformed JSON") from exc

    if not isinstance(payload, dict):
        raise ValueError("structured output root must be a JSON object")
    return payload


def defer_verdict(reason: str) -> CouncilVerdict:
    return CouncilVerdict(
        verdict=DecisionVote.DEFER,
        recommendation="Defer the decision until the missing decision evidence is resolved.",
        confidence=0.0,
        consensus="No reliable council consensus is available.",
        key_disagreement="The decision record is incomplete or invalid.",
        minority_report="",
        assumptions=[],
        evidence_gaps=[reason],
        what_would_change_decision=["Resolve the listed evidence gap and rerun the council."],
        next_experiment=None,
    )
