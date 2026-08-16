from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Callable
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import Any

from src.council.business_routing import early_consensus_vote, profile_problem, route_experts
from src.council.council_os_models import (
    CouncilOSResult,
    CouncilVerdict,
    EvidenceAssessment,
    ExpertMemo,
    HistoricalAnalogyRejection,
    HistoricalContextAssessment,
    KnowledgeStatus,
    LearningContext,
    LearningContextSummary,
    ProblemProfile,
    Rebuttal,
    RedTeamReport,
    defer_verdict,
    extract_json_object,
)
from src.council.expert_registry import EXPERT_REGISTRY, ExpertDefinition
from src.knowledge.private_models import KnowledgeRetrievalResult
from src.knowledge.retriever import format_context_for_agent, query_knowledge_result
from src.llm_providers import LLMProvider

Retriever = Callable[..., KnowledgeRetrievalResult]
LearningContextProvider = Callable[[ProblemProfile, list[str], list[ExpertMemo]], LearningContext]

_CURRENT_LEARNING_CONTEXT_PROVIDER: ContextVar[LearningContextProvider | None] = ContextVar(
    "council_learning_context_provider",
    default=None,
)


def current_learning_context_provider() -> LearningContextProvider | None:
    return _CURRENT_LEARNING_CONTEXT_PROVIDER.get()


def bind_learning_context_provider(
    provider: LearningContextProvider | None,
) -> Token[LearningContextProvider | None]:
    return _CURRENT_LEARNING_CONTEXT_PROVIDER.set(provider)


def reset_learning_context_provider(token: Token[LearningContextProvider | None]) -> None:
    _CURRENT_LEARNING_CONTEXT_PROVIDER.reset(token)


@dataclass
class _BlindRound:
    memos: list[ExpertMemo] = field(default_factory=list)
    knowledge_status_by_expert: dict[str, KnowledgeStatus] = field(default_factory=dict)
    source_inventory: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def _safe_source_inventory(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "doc_id": str(chunk.get("doc_id", "")),
            "title": str(chunk.get("title", "Unknown")),
            "source_type": str(chunk.get("source_type", "unknown")),
            "chunk_index": int(chunk.get("chunk_index", 0) or 0),
            "score": float(chunk.get("score", 0) or 0),
        }
        for chunk in chunks
    ]


def _dump_models(items: list[Any]) -> str:
    return json.dumps(
        [item.model_dump(mode="json") for item in items],
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _dump_learning(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


class CouncilOS:
    def __init__(
        self,
        llm: LLMProvider,
        *,
        retriever: Retriever = query_knowledge_result,
        knowledge_namespace: str | None = None,
        knowledge_top_k: int = 5,
        learning_context_provider: LearningContextProvider | None = None,
    ):
        self.llm = llm
        self.retriever = retriever
        self.knowledge_namespace = (
            knowledge_namespace
            if knowledge_namespace is not None
            else os.getenv("PINECONE_PRIVATE_NAMESPACE") or None
        )
        self.knowledge_top_k = max(1, knowledge_top_k)
        self.learning_context_provider = (
            learning_context_provider
            if learning_context_provider is not None
            else current_learning_context_provider()
        )

    def _retrieve_for_expert(
        self,
        query: str,
        expert: ExpertDefinition,
    ) -> KnowledgeRetrievalResult:
        return self.retriever(
            query,
            top_k=self.knowledge_top_k,
            domains=list(expert.domains),
            experts=list(expert.retrieval_experts),
            namespace=self.knowledge_namespace,
        )

    def _blind_system_prompt(self, expert: ExpertDefinition) -> str:
        return "\n".join(
            [
                "[STAGE:BLIND]",
                f"[EXPERT_ID:{expert.id}]",
                expert.system_prompt,
                "Work independently. You have not seen any other expert's memo or vote.",
                "Return one JSON object only with this schema:",
                "{",
                f'  "expert_id": "{expert.id}",',
                '  "vote": "GO | NO-GO | TEST | DEFER",',
                '  "recommendation": "string",',
                '  "confidence": 0.0,',
                '  "claims": [{"label":"F|A|I|FMW|O","text":"string","source_ids":[]}],',
                '  "assumptions": ["string"],',
                '  "risks": ["string"],',
                '  "what_changes_my_mind": ["string"]',
                "}",
            ]
        )

    def _blind_user_prompt(
        self,
        query: str,
        expert: ExpertDefinition,
        retrieval: KnowledgeRetrievalResult,
    ) -> str:
        context = format_context_for_agent(retrieval.chunks, include_provenance=True)
        return "\n".join(
            [
                f"Decision question: {query}",
                f"Your role: {expert.role}",
                f"Knowledge status: {retrieval.status}",
                "Use the supplied knowledge only when relevant; do not treat frameworks as current facts.",
                "Private knowledge context and provenance:",
                context,
            ]
        )

    async def _generate_blind_memo(
        self,
        query: str,
        expert: ExpertDefinition,
        retrieval: KnowledgeRetrievalResult,
    ) -> ExpertMemo:
        response = await self.llm.generate(
            self._blind_system_prompt(expert),
            self._blind_user_prompt(query, expert, retrieval),
            temperature=0.35,
            max_tokens=1800,
        )
        payload = extract_json_object(response.content)
        payload["expert_id"] = expert.id
        payload["knowledge_status"] = retrieval.status
        return ExpertMemo.model_validate(payload)

    async def _run_blind_memos(
        self,
        query: str,
        experts: list[ExpertDefinition],
    ) -> _BlindRound:
        round_result = _BlindRound()
        retrieval_by_expert: dict[str, KnowledgeRetrievalResult] = {}

        for expert in experts:
            try:
                retrieval = self._retrieve_for_expert(query, expert)
            except Exception as exc:
                retrieval = KnowledgeRetrievalResult(
                    status="unavailable",
                    error_code="retriever_exception",
                )
                round_result.errors.append(f"retrieval:{expert.id}:{type(exc).__name__}")
            retrieval_by_expert[expert.id] = retrieval
            round_result.knowledge_status_by_expert[expert.id] = retrieval.status
            round_result.source_inventory[expert.id] = _safe_source_inventory(retrieval.chunks)

        tasks = [
            self._generate_blind_memo(query, expert, retrieval_by_expert[expert.id])
            for expert in experts
        ]
        generated = await asyncio.gather(*tasks, return_exceptions=True)

        for expert, outcome in zip(experts, generated, strict=True):
            if isinstance(outcome, BaseException):
                round_result.errors.append(f"blind:{expert.id}:{type(outcome).__name__}")
                continue
            round_result.memos.append(outcome)

        return round_result

    def _build_learning_context(
        self,
        profile: ProblemProfile,
        experts: list[ExpertDefinition],
        memos: list[ExpertMemo],
    ) -> tuple[LearningContext, str | None]:
        if self.learning_context_provider is None:
            return LearningContext(status="disabled"), None
        try:
            context = self.learning_context_provider(
                profile,
                [expert.id for expert in experts],
                memos,
            )
            return LearningContext.model_validate(context), None
        except Exception:
            return (
                LearningContext(
                    status="unavailable",
                    error_labels=["learning_context_unavailable"],
                ),
                "learning_context_unavailable",
            )

    @staticmethod
    def _rebuttal_learning_payload(learning: LearningContext) -> dict[str, Any]:
        return {
            "status": learning.status,
            "expert_signals": [signal.model_dump(mode="json") for signal in learning.expert_signals],
            "analog_decisions": [analogy.model_dump(mode="json") for analogy in learning.analog_decisions],
        }

    @staticmethod
    def _red_team_learning_payload(learning: LearningContext) -> dict[str, Any]:
        return {
            "status": learning.status,
            "expert_sample_strengths": {
                signal.expert_id: signal.sample_strength for signal in learning.expert_signals
            },
            "bias_alerts": learning.bias_alerts,
            "protected_minority_expert_ids": learning.protected_minority_expert_ids,
            "analog_decisions": [analogy.model_dump(mode="json") for analogy in learning.analog_decisions],
        }

    def _rebuttal_system_prompt(self, expert: ExpertDefinition) -> str:
        return "\n".join(
            [
                "[STAGE:REBUTTAL]",
                f"[EXPERT_ID:{expert.id}]",
                expert.system_prompt,
                "The blind round is complete. You may now inspect peer memos.",
                "Historical calibration is advisory. Current-case evidence has priority.",
                "Focus on the strongest disagreement and the smallest assumption that could flip the decision.",
                "Return one JSON object only with keys: expert_id, strongest_agreement, "
                "strongest_disagreement, assumption_to_test, revised_vote, revised_confidence.",
            ]
        )

    async def _generate_rebuttal(
        self,
        query: str,
        profile: ProblemProfile,
        expert: ExpertDefinition,
        own_memo: ExpertMemo,
        peer_memos: list[ExpertMemo],
        learning: LearningContext,
    ) -> Rebuttal:
        user_prompt = "\n".join(
            [
                f"Decision question: {query}",
                f"Problem profile: {profile.model_dump_json()}",
                f"Your blind memo: {own_memo.model_dump_json()}",
                f"Peer blind memos: {_dump_models(peer_memos)}",
                "Sanitized historical calibration context: "
                + _dump_learning(self._rebuttal_learning_payload(learning)),
            ]
        )
        response = await self.llm.generate(
            self._rebuttal_system_prompt(expert),
            user_prompt,
            temperature=0.3,
            max_tokens=1000,
        )
        payload = extract_json_object(response.content)
        payload["expert_id"] = expert.id
        return Rebuttal.model_validate(payload)

    async def _run_rebuttals(
        self,
        query: str,
        profile: ProblemProfile,
        experts: list[ExpertDefinition],
        memos: list[ExpertMemo],
        learning: LearningContext | None = None,
    ) -> list[Rebuttal]:
        learning = learning or LearningContext(status="disabled")
        memo_by_expert = {memo.expert_id: memo for memo in memos}
        participating = [expert for expert in experts if expert.id in memo_by_expert]
        tasks = []
        for expert in participating:
            own_memo = memo_by_expert[expert.id]
            peers = [memo for memo in memos if memo.expert_id != expert.id]
            tasks.append(
                self._generate_rebuttal(query, profile, expert, own_memo, peers, learning)
            )

        generated = await asyncio.gather(*tasks, return_exceptions=True)
        return [outcome for outcome in generated if isinstance(outcome, Rebuttal)]

    async def _run_red_team(
        self,
        query: str,
        profile: ProblemProfile,
        memos: list[ExpertMemo],
        rebuttals: list[Rebuttal],
        learning: LearningContext | None = None,
    ) -> RedTeamReport:
        learning = learning or LearningContext(status="disabled")
        consensus_vote, consensus_share = early_consensus_vote(memos)
        premature_consensus = consensus_vote is not None
        consensus_line = f"PREMATURE_CONSENSUS={'true' if premature_consensus else 'false'}"
        instructions = [
            consensus_line,
            f"EARLY_CONSENSUS_SHARE={consensus_share:.3f}",
        ]
        if premature_consensus:
            instructions.append("REQUIRED: construct the strongest credible contrarian case")
        if learning.protected_minority_expert_ids:
            instructions.append(
                "REQUIRED: test the protected minority position against current evidence: "
                + ",".join(learning.protected_minority_expert_ids)
            )

        user_prompt = "\n".join(
            [
                f"Decision question: {query}",
                f"Problem profile: {profile.model_dump_json()}",
                *instructions,
                f"Blind memos: {_dump_models(memos)}",
                f"Rebuttals: {_dump_models(rebuttals)}",
                "Sanitized historical learning context: "
                + _dump_learning(self._red_team_learning_payload(learning)),
            ]
        )
        system_prompt = "\n".join(
            [
                "[STAGE:RED_TEAM]",
                "[EXPERT_ID:red_team]",
                EXPERT_REGISTRY["red_team"].system_prompt,
                "Historical similarity is not evidence that the same outcome will recur.",
                "Return one JSON object with failure_modes, challenged_assumptions, "
                "double_crux_questions, premature_consensus, contrarian_case, parse_error.",
            ]
        )
        try:
            response = await self.llm.generate(
                system_prompt,
                user_prompt,
                temperature=0.45,
                max_tokens=1400,
            )
            payload = extract_json_object(response.content)
            payload["premature_consensus"] = premature_consensus
            report = RedTeamReport.model_validate(payload)
            if premature_consensus and not report.contrarian_case.strip():
                return report.model_copy(
                    update={
                        "contrarian_case": "red_team_missing_required_contrarian_case",
                        "parse_error": True,
                    }
                )
            return report
        except Exception:
            return RedTeamReport(
                failure_modes=["red_team_parse_error"],
                challenged_assumptions=[],
                double_crux_questions=[],
                premature_consensus=premature_consensus,
                contrarian_case="",
                parse_error=True,
            )

    @staticmethod
    def _sanitize_historical_assessment(
        raw: HistoricalContextAssessment,
        learning: LearningContext,
    ) -> HistoricalContextAssessment:
        known_analogies = {analogy.decision_id for analogy in learning.analog_decisions}
        signal_by_id = {signal.expert_id: signal for signal in learning.expert_signals}
        accepted = [item for item in raw.accepted_analogy_ids if item in known_analogies]
        accepted_set = set(accepted)
        rejected = [
            HistoricalAnalogyRejection(decision_id=item.decision_id, reason=item.reason)
            for item in raw.rejected_analogies
            if item.decision_id in known_analogies and item.decision_id not in accepted_set
        ]
        usable = [
            expert_id
            for expert_id in raw.usable_calibration_expert_ids
            if expert_id in signal_by_id
            and signal_by_id[expert_id].sample_strength in {"weak", "normal"}
        ]
        too_weak = [
            expert_id
            for expert_id in raw.too_weak_calibration_expert_ids
            if expert_id in signal_by_id
        ]
        return HistoricalContextAssessment(
            accepted_analogy_ids=list(dict.fromkeys(accepted)),
            rejected_analogies=rejected,
            usable_calibration_expert_ids=list(dict.fromkeys(usable)),
            too_weak_calibration_expert_ids=list(dict.fromkeys(too_weak)),
            current_evidence_conflicts=list(dict.fromkeys(raw.current_evidence_conflicts)),
        )

    async def _run_evidence_judge(
        self,
        query: str,
        profile: ProblemProfile,
        blind: _BlindRound,
        memos: list[ExpertMemo],
        rebuttals: list[Rebuttal],
        red_team: RedTeamReport,
        learning: LearningContext | None = None,
    ) -> EvidenceAssessment:
        learning = learning or LearningContext(status="disabled")
        source_payload = {
            expert_id: {
                "knowledge_status": blind.knowledge_status_by_expert.get(expert_id, "disabled"),
                "sources": sources,
            }
            for expert_id, sources in blind.source_inventory.items()
        }
        user_prompt = "\n".join(
            [
                f"Decision question: {query}",
                f"Problem profile: {profile.model_dump_json()}",
                f"Blind memos: {_dump_models(memos)}",
                f"Rebuttals: {_dump_models(rebuttals)}",
                f"Red Team: {red_team.model_dump_json()}",
                "Source provenance and knowledge_status by expert: "
                + json.dumps(source_payload, ensure_ascii=False, separators=(",", ":")),
                "Sanitized historical learning context: " + learning.model_dump_json(),
            ]
        )
        system_prompt = "\n".join(
            [
                "[STAGE:EVIDENCE_JUDGE]",
                "[EXPERT_ID:evidence_judge]",
                EXPERT_REGISTRY["evidence_judge"].system_prompt,
                "Judge support only relative to supplied provenance. Do not choose the business verdict.",
                "Current evidence has priority over historical precedent. Reject analogies that are weak, "
                "structurally mismatched, or contradicted by current evidence.",
                "Return one JSON object with supported_claims, weak_or_unsupported_claims, contradictions, "
                "evidence_gaps, knowledge_status_by_expert, framework_fact_confusions, historical_context, parse_error.",
                "historical_context keys: accepted_analogy_ids, rejected_analogies "
                "([{decision_id,reason}]), usable_calibration_expert_ids, "
                "too_weak_calibration_expert_ids, current_evidence_conflicts.",
            ]
        )
        try:
            response = await self.llm.generate(
                system_prompt,
                user_prompt,
                temperature=0.2,
                max_tokens=1600,
            )
            payload = extract_json_object(response.content)
            payload["knowledge_status_by_expert"] = blind.knowledge_status_by_expert
            assessment = EvidenceAssessment.model_validate(payload)
            if assessment.historical_context is not None:
                assessment.historical_context = self._sanitize_historical_assessment(
                    assessment.historical_context,
                    learning,
                )
            return assessment
        except Exception:
            return EvidenceAssessment(
                supported_claims=[],
                weak_or_unsupported_claims=[],
                contradictions=[],
                evidence_gaps=["evidence_judge_parse_error"],
                knowledge_status_by_expert=blind.knowledge_status_by_expert,
                framework_fact_confusions=[],
                historical_context=HistoricalContextAssessment(),
                parse_error=True,
            )

    @staticmethod
    def _approved_learning_payload(
        learning: LearningContext,
        evidence: EvidenceAssessment,
    ) -> dict[str, Any]:
        assessment = evidence.historical_context or HistoricalContextAssessment()
        accepted = set(assessment.accepted_analogy_ids)
        usable = set(assessment.usable_calibration_expert_ids)
        approved_signals = [
            signal for signal in learning.expert_signals if signal.expert_id in usable
        ]
        approved_bias_alerts = sorted(
            {flag for signal in approved_signals for flag in signal.flags}
        )
        approved_protected_minority = [
            expert_id
            for expert_id in learning.protected_minority_expert_ids
            if expert_id in usable
        ]
        return {
            "status": learning.status,
            "approved_analogies": [
                analogy.model_dump(mode="json")
                for analogy in learning.analog_decisions
                if analogy.decision_id in accepted
            ],
            "approved_expert_signals": [
                signal.model_dump(mode="json") for signal in approved_signals
            ],
            "bias_alerts": approved_bias_alerts,
            "protected_minority_expert_ids": approved_protected_minority,
        }

    async def _run_chairman(
        self,
        query: str,
        profile: ProblemProfile,
        routed_experts: list[ExpertDefinition],
        memos: list[ExpertMemo],
        rebuttals: list[Rebuttal],
        red_team: RedTeamReport,
        evidence: EvidenceAssessment,
        errors: list[str],
        learning: LearningContext | None = None,
    ) -> CouncilVerdict:
        learning = learning or LearningContext(status="disabled")
        approved_learning = self._approved_learning_payload(learning, evidence)
        approved_protected_minority = approved_learning["protected_minority_expert_ids"]
        protected_instruction = (
            "Protected minority: explicitly address the dissent from "
            + ", ".join(approved_protected_minority)
            + "; do not automatically adopt it."
            if approved_protected_minority
            else "No protected minority obligation is active."
        )
        system_prompt = "\n".join(
            [
                "[STAGE:CHAIRMAN]",
                "[EXPERT_ID:chairman]",
                EXPERT_REGISTRY["chairman"].system_prompt,
                "You are called only after domain experts, rebuttals, Red Team and Evidence Judge.",
                "Historical analogies are precedents, not facts about the current case.",
                "Current evidence overrides historical learning signals.",
                "Sample strength none has no decision authority. Weak history may justify scrutiny or TEST "
                "but cannot decide the verdict. Normal history may affect confidence or tie-breaking only "
                "when current evidence is otherwise comparable.",
                protected_instruction,
                "Prefer TEST when a reversible discriminating experiment can resolve the key uncertainty.",
                "Use DEFER when a critical evidence outage or unresolved dependency blocks a responsible decision.",
                "Return one JSON object only with verdict, recommendation, confidence, consensus, "
                "key_disagreement, minority_report, assumptions, evidence_gaps, "
                "what_would_change_decision and next_experiment.",
                "next_experiment must be null or contain action, metric, threshold, timeline, kill_criteria.",
            ]
        )
        evidence_without_history = evidence.model_dump(
            mode="json",
            exclude={"historical_context"},
        )
        user_prompt = "\n".join(
            [
                f"Decision question: {query}",
                f"Problem profile: {profile.model_dump_json()}",
                "Routed experts: " + json.dumps([expert.id for expert in routed_experts]),
                f"Blind memos: {_dump_models(memos)}",
                f"Rebuttals: {_dump_models(rebuttals)}",
                f"Red Team: {red_team.model_dump_json()}",
                "Evidence Judge (current-case evidence): "
                + _dump_learning(evidence_without_history),
                "Evidence-Judge-approved historical context: "
                + _dump_learning(approved_learning),
                "Orchestration errors: " + json.dumps(errors),
                "Do not imply unavailable private knowledge was consulted or verified.",
            ]
        )
        try:
            response = await self.llm.generate(
                system_prompt,
                user_prompt,
                temperature=0.2,
                max_tokens=1800,
            )
            return CouncilVerdict.model_validate(extract_json_object(response.content))
        except Exception:
            return defer_verdict("chairman_parse_error")

    @staticmethod
    def _learning_summary(
        learning: LearningContext,
        evidence: EvidenceAssessment | None,
    ) -> LearningContextSummary:
        assessment = (
            evidence.historical_context
            if evidence is not None and evidence.historical_context is not None
            else HistoricalContextAssessment()
        )
        usable_expert_ids = set(assessment.usable_calibration_expert_ids)
        active_strengths = {
            signal.expert_id: signal.sample_strength
            for signal in learning.expert_signals
            if signal.expert_id in usable_expert_ids
            and signal.sample_strength != "none"
        }
        approved_protected_minority = [
            expert_id
            for expert_id in learning.protected_minority_expert_ids
            if expert_id in usable_expert_ids
        ]
        influenced = bool(
            assessment.accepted_analogy_ids
            or assessment.usable_calibration_expert_ids
            or approved_protected_minority
        )
        return LearningContextSummary(
            status=learning.status,
            scored_history_count=learning.scored_history_count,
            analogy_count=len(assessment.accepted_analogy_ids),
            active_sample_strengths=active_strengths,
            bias_alerts=sorted(
                {
                    flag
                    for signal in learning.expert_signals
                    if signal.expert_id in usable_expert_ids
                    for flag in signal.flags
                }
            ),
            protected_minority_expert_ids=approved_protected_minority,
            rejected_analogies=assessment.rejected_analogies,
            influenced_final_stage=influenced,
        )

    async def deliberate(self, query: str) -> CouncilOSResult:
        profile = profile_problem(query)
        experts = route_experts(profile)
        blind = await self._run_blind_memos(query, experts)
        errors = list(blind.errors)

        if len(blind.memos) < 2:
            return CouncilOSResult(
                profile=profile,
                routed_experts=[expert.id for expert in experts],
                memos=blind.memos,
                rebuttals=[],
                red_team=None,
                evidence=None,
                verdict=defer_verdict("insufficient_domain_memos"),
                knowledge_status_by_expert=blind.knowledge_status_by_expert,
                errors=errors,
                learning_context_summary=LearningContextSummary(status="disabled"),
            )

        learning, learning_error = self._build_learning_context(profile, experts, blind.memos)
        if learning_error:
            errors.append(learning_error)

        rebuttals = await self._run_rebuttals(
            query,
            profile,
            experts,
            blind.memos,
            learning,
        )
        rebuttal_ids = {rebuttal.expert_id for rebuttal in rebuttals}
        errors.extend(
            f"rebuttal_missing:{memo.expert_id}"
            for memo in blind.memos
            if memo.expert_id not in rebuttal_ids
        )

        red_team = await self._run_red_team(
            query,
            profile,
            blind.memos,
            rebuttals,
            learning,
        )
        if red_team.parse_error:
            errors.append("red_team_parse_error")

        evidence = await self._run_evidence_judge(
            query,
            profile,
            blind,
            blind.memos,
            rebuttals,
            red_team,
            learning,
        )
        if evidence.parse_error:
            errors.append("evidence_judge_parse_error")

        verdict = await self._run_chairman(
            query,
            profile,
            experts,
            blind.memos,
            rebuttals,
            red_team,
            evidence,
            errors,
            learning,
        )
        if "chairman_parse_error" in verdict.evidence_gaps:
            errors.append("chairman_parse_error")

        return CouncilOSResult(
            profile=profile,
            routed_experts=[expert.id for expert in experts],
            memos=blind.memos,
            rebuttals=rebuttals,
            red_team=red_team,
            evidence=evidence,
            verdict=verdict,
            knowledge_status_by_expert=blind.knowledge_status_by_expert,
            errors=errors,
            learning_context_summary=self._learning_summary(learning, evidence),
        )
