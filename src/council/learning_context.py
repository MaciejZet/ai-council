from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from src.council.council_os_models import (
    AnalogDecision,
    DecisionVote,
    ExpertCalibrationSignal,
    ExpertMemo,
    LearningContext,
    ProblemProfile,
    SampleStrength,
)

WEAK_SAMPLE_MIN = 5
NORMAL_SAMPLE_MIN = 15
MAX_ANALOGIES = 3
_SECONDARY_MATCH_CAP = 2


def sample_strength(sample_size: int) -> SampleStrength:
    if sample_size >= NORMAL_SAMPLE_MIN:
        return "normal"
    if sample_size >= WEAK_SAMPLE_MIN:
        return "weak"
    return "none"


def _signal_sort_key(signal: ExpertCalibrationSignal) -> tuple[int, float, float, str]:
    strength_rank = {"none": 0, "weak": 1, "normal": 2}[signal.sample_strength]
    return (-strength_rank, signal.brier_like_error, -signal.hit_rate, signal.expert_id)


def _analogy_score(row: dict[str, Any], profile: ProblemProfile) -> tuple[int, list[str]]:
    score = 0
    matching: list[str] = []
    if row.get("primary_domain") == profile.primary_domain:
        score += 4
        matching.append("primary_domain")
    if row.get("decision_kind") == profile.decision_kind:
        score += 3
        matching.append("decision_kind")
    if row.get("reversibility") == profile.reversibility:
        score += 2
        matching.append("reversibility")
    if row.get("risk_level") == profile.risk_level:
        score += 2
        matching.append("risk_level")

    current_secondary = set(profile.secondary_domains)
    prior_secondary = set(row.get("secondary_domains") or [])
    secondary_matches = sorted(current_secondary & prior_secondary)[:_SECONDARY_MATCH_CAP]
    score += len(secondary_matches)
    matching.extend(f"secondary_domain:{item}" for item in secondary_matches)
    return score, matching


class LearningContextBuilder:
    def __init__(self, store: Any):
        self.store = store

    def _expert_signals(
        self,
        predictions: list[dict[str, Any]],
        expert_ids: list[str],
        primary_domain: str,
    ) -> list[ExpertCalibrationSignal]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in predictions:
            grouped[str(row["expert_id"])].append(row)

        signals: list[ExpertCalibrationSignal] = []
        for expert_id in expert_ids:
            rows = grouped.get(expert_id, [])
            sample_size = len(rows)
            if sample_size:
                correctness = [
                    1.0 if str(row["predicted_vote"]) == str(row["resolved_vote"]) else 0.0
                    for row in rows
                ]
                confidences = [float(row["confidence"]) for row in rows]
                hit_rate = sum(correctness) / sample_size
                mean_confidence = sum(confidences) / sample_size
                brier_like_error = sum(
                    (confidence - correct) ** 2
                    for confidence, correct in zip(confidences, correctness, strict=True)
                ) / sample_size
            else:
                hit_rate = 0.0
                mean_confidence = 0.0
                brier_like_error = 0.0

            strength = sample_strength(sample_size)
            flags: list[str] = []
            if strength != "none":
                vote_counts = Counter(str(row["predicted_vote"]) for row in rows)
                if mean_confidence >= 0.75 and brier_like_error >= 0.25:
                    flags.append("overconfidence")
                if hit_rate >= 0.75 and mean_confidence <= 0.60:
                    flags.append("underconfidence")
                if (
                    vote_counts[DecisionVote.GO.value] / sample_size >= 0.70
                    and hit_rate < 0.60
                ):
                    flags.append("go_bias")
                if (
                    vote_counts[DecisionVote.TEST.value] / sample_size >= 0.60
                    and hit_rate < 0.60
                ):
                    flags.append("test_bias")

            signals.append(
                ExpertCalibrationSignal(
                    expert_id=expert_id,
                    primary_domain=primary_domain,
                    sample_size=sample_size,
                    sample_strength=strength,
                    hit_rate=round(hit_rate, 6),
                    mean_confidence=round(mean_confidence, 6),
                    brier_like_error=round(brier_like_error, 6),
                    confidence_bias=round(mean_confidence - hit_rate, 6),
                    flags=flags,
                )
            )

        ordered = sorted(signals, key=_signal_sort_key)
        for rank, signal in enumerate(ordered, start=1):
            signal.reliability_rank = rank
        return ordered

    def _analogies(
        self,
        rows: list[dict[str, Any]],
        profile: ProblemProfile,
    ) -> list[AnalogDecision]:
        ranked: list[tuple[int, str, str, dict[str, Any], list[str]]] = []
        for row in rows:
            score, matching = _analogy_score(row, profile)
            ranked.append(
                (
                    score,
                    str(row.get("outcome_updated_at") or ""),
                    str(row["decision_id"]),
                    row,
                    matching,
                )
            )

        ranked.sort(key=lambda item: item[2])
        ranked.sort(key=lambda item: item[1], reverse=True)
        ranked.sort(key=lambda item: item[0], reverse=True)

        output: list[AnalogDecision] = []
        for score, _updated, _decision_id, row, matching in ranked[:MAX_ANALOGIES]:
            output.append(
                AnalogDecision(
                    decision_id=str(row["decision_id"]),
                    primary_domain=str(row["primary_domain"]),
                    decision_kind=str(row["decision_kind"]),
                    reversibility=row["reversibility"],
                    risk_level=row["risk_level"],
                    verdict=row["verdict"],
                    verdict_confidence=float(row["verdict_confidence"]),
                    resolved_vote=row["resolved_vote"],
                    outcome_status=str(row["outcome_status"]),
                    similarity_score=score,
                    matching_dimensions=matching,
                )
            )
        return output

    def _protected_minority(
        self,
        signals: list[ExpertCalibrationSignal],
        blind_memos: list[ExpertMemo],
    ) -> list[str]:
        if len(blind_memos) < 3:
            return []

        counts = Counter(memo.vote.value for memo in blind_memos)
        top = counts.most_common()
        if not top or (len(top) > 1 and top[0][1] == top[1][1]):
            return []

        majority_vote = top[0][0]
        signal_by_id = {signal.expert_id: signal for signal in signals}
        majority_signals = [
            signal_by_id[memo.expert_id]
            for memo in blind_memos
            if memo.vote.value == majority_vote and memo.expert_id in signal_by_id
        ]

        protected: list[str] = []
        for memo in blind_memos:
            signal = signal_by_id.get(memo.expert_id)
            if (
                signal is None
                or memo.vote.value == majority_vote
                or signal.sample_strength != "normal"
            ):
                continue
            if majority_signals and all(
                _signal_sort_key(signal) < _signal_sort_key(other)
                for other in majority_signals
            ):
                protected.append(memo.expert_id)
        return sorted(protected)

    def build(
        self,
        user_id: str,
        profile: ProblemProfile,
        routed_expert_ids: list[str],
        blind_memos: list[ExpertMemo],
    ) -> LearningContext:
        try:
            decisions = self.store.resolved_decisions(user_id, primary_domain=None)
            predictions = self.store.expert_predictions(
                user_id,
                routed_expert_ids,
                profile.primary_domain,
            )
        except Exception:
            return LearningContext(
                status="unavailable",
                error_labels=["learning_store_unavailable"],
            )

        unique_scored = {str(row["decision_id"]) for row in decisions}
        unique_scored.update(str(row["decision_id"]) for row in predictions)
        if not unique_scored:
            return LearningContext(status="insufficient_history")

        signals = self._expert_signals(
            predictions,
            routed_expert_ids,
            profile.primary_domain,
        )
        analogies = self._analogies(decisions, profile)
        bias_alerts = sorted({flag for signal in signals for flag in signal.flags})
        protected = self._protected_minority(signals, blind_memos)
        return LearningContext(
            status="ok",
            expert_signals=signals,
            analog_decisions=analogies,
            bias_alerts=bias_alerts,
            protected_minority_expert_ids=protected,
            scored_history_count=len(unique_scored),
        )
