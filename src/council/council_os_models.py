from __future__ import annotations

import json
import re
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

KnowledgeStatus = Literal["ok", "no_matches", "disabled", "unavailable"]
Reversibility = Literal["reversible", "hard_to_reverse"]
RiskLevel = Literal["low", "medium", "high"]


class DecisionVote(str, Enum):
    GO = "GO"
    NO_GO = "NO-GO"
    TEST = "TEST"
    DEFER = "DEFER"


class ClaimLabel(str, Enum):
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


class EvidenceAssessment(BaseModel):
    supported_claims: list[str] = Field(default_factory=list)
    weak_or_unsupported_claims: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    evidence_gaps: list[str] = Field(default_factory=list)
    knowledge_status_by_expert: dict[str, KnowledgeStatus] = Field(default_factory=dict)
    framework_fact_confusions: list[str] = Field(default_factory=list)
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
