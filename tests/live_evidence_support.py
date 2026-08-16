import json

from src.council.council_os_models import (
    LiveEvidenceContext,
    LiveEvidenceSource,
)
from src.llm_providers import LLMResponse


class FakeLiveProvider:
    def __init__(self, context=None, error=None, events=None):
        self.context = context or LiveEvidenceContext(status="disabled")
        self.error = error
        self.calls = []
        self.events = events if events is not None else []

    async def collect(self, question, profile, framework_ids):
        self.events.append("live_collect")
        self.calls.append((question, profile, framework_ids))
        if self.error:
            raise self.error
        return self.context


class StageLLM:
    def __init__(self, events=None, accepted="web_accept", rejected="web_reject"):
        self.events = events if events is not None else []
        self.calls = []
        self.accepted = accepted
        self.rejected = rejected

    async def generate(self, system_prompt, user_prompt, temperature=0.7, max_tokens=None):
        stage = next(
            item
            for item in ("BLIND", "REBUTTAL", "RED_TEAM", "EVIDENCE_JUDGE", "CHAIRMAN")
            if f"[STAGE:{item}]" in system_prompt
        )
        self.events.append(stage.lower())
        self.calls.append((stage, system_prompt, user_prompt))
        expert = "strategy"
        if "[EXPERT_ID:" in system_prompt:
            expert = system_prompt.split("[EXPERT_ID:", 1)[1].split("]", 1)[0]
        if stage == "BLIND":
            payload = {
                "expert_id": expert,
                "vote": "TEST",
                "recommendation": "test",
                "confidence": 0.6,
                "claims": [],
                "assumptions": [],
                "risks": [],
                "what_changes_my_mind": [],
            }
        elif stage == "REBUTTAL":
            payload = {
                "expert_id": expert,
                "strongest_agreement": "a",
                "strongest_disagreement": "d",
                "assumption_to_test": "x",
                "revised_vote": "TEST",
                "revised_confidence": 0.6,
            }
        elif stage == "RED_TEAM":
            payload = {
                "failure_modes": [],
                "challenged_assumptions": [],
                "double_crux_questions": [],
                "premature_consensus": False,
                "contrarian_case": "",
                "parse_error": False,
            }
        elif stage == "EVIDENCE_JUDGE":
            payload = {
                "supported_claims": [],
                "weak_or_unsupported_claims": [],
                "contradictions": [],
                "evidence_gaps": [],
                "knowledge_status_by_expert": {},
                "framework_fact_confusions": [],
                "historical_context": {
                    "accepted_analogy_ids": [],
                    "rejected_analogies": [],
                    "usable_calibration_expert_ids": [],
                    "too_weak_calibration_expert_ids": [],
                    "current_evidence_conflicts": [],
                },
                "framework_assessment": {
                    "misclassified_fact_claims": [],
                    "framework_overreach_labels": [],
                    "rejected_framework_ids": [],
                },
                "live_evidence": {
                    "accepted_evidence_ids": [self.accepted, "web_unknown"],
                    "rejected_evidence": [
                        {"evidence_id": self.rejected, "reason": "free text"},
                        {"evidence_id": "web_unknown", "reason": "weak_relevance"},
                    ],
                    "source_conflict_labels": ["free conflict"],
                },
                "parse_error": False,
            }
        else:
            payload = {
                "verdict": "TEST",
                "recommendation": "test",
                "confidence": 0.6,
                "consensus": "mixed",
                "key_disagreement": "x",
                "minority_report": "",
                "assumptions": [],
                "evidence_gaps": [],
                "what_would_change_decision": [],
                "next_experiment": None,
            }
        return LLMResponse(content=json.dumps(payload), model="fake")


def source(evidence_id, snippet, url):
    return LiveEvidenceSource(
        evidence_id=evidence_id,
        query_index=0,
        title=evidence_id,
        canonical_url=url,
        domain="example.com",
        snippet=snippet,
        relevance_score=0.8,
        fetched_at="2026-08-16T12:00:00+00:00",
    )
