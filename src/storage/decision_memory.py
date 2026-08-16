from __future__ import annotations

import sqlite3
import uuid
from typing import Any

from src.storage.decision_memory_core import *  # noqa: F403
from src.storage.decision_memory_core import (
    DecisionMemoryStore as _CoreDecisionMemoryStore,
    _json_dump,
    _json_load,
    _now_iso,
)


class DecisionMemoryStore(_CoreDecisionMemoryStore):
    """Decision Memory with additive sanitized Live Evidence diagnostics."""

    def _initialize(self) -> None:
        super()._initialize()
        with self._lock, self._connect() as conn:
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(decisions)").fetchall()}
            if "live_evidence_json" not in columns:
                conn.execute("ALTER TABLE decisions ADD COLUMN live_evidence_json TEXT")

    def capture_decision(self, user_id: str, query: str, result) -> str:
        decision_id = str(uuid.uuid4())
        now = _now_iso()
        profile = result.profile
        verdict = result.verdict
        next_experiment = (
            verdict.next_experiment.model_dump(mode="json") if verdict.next_experiment is not None else None
        )
        learning_summary = (
            result.learning_context_summary.model_dump(mode="json")
            if result.learning_context_summary is not None
            else None
        )
        framework_summary = (
            result.framework_selection_summary.model_dump(mode="json")
            if result.framework_selection_summary is not None
            else None
        )
        live_evidence_summary = (
            result.live_evidence_summary.model_dump(mode="json")
            if result.live_evidence_summary is not None
            else None
        )
        rebuttals = {rebuttal.expert_id: rebuttal for rebuttal in result.rebuttals}

        decision_values = (
            decision_id,
            user_id,
            now,
            now,
            query,
            profile.primary_domain,
            _json_dump(profile.secondary_domains),
            profile.decision_kind,
            profile.reversibility,
            profile.risk_level,
            _json_dump(result.routed_experts),
            verdict.verdict.value,
            verdict.confidence,
            verdict.recommendation,
            verdict.consensus,
            verdict.key_disagreement,
            verdict.minority_report,
            _json_dump(verdict.assumptions),
            _json_dump(verdict.evidence_gaps),
            _json_dump(verdict.what_would_change_decision),
            _json_dump(next_experiment) if next_experiment is not None else None,
            _json_dump(result.knowledge_status_by_expert),
            _json_dump(result.errors),
            _json_dump(learning_summary) if learning_summary is not None else None,
            _json_dump(framework_summary) if framework_summary is not None else None,
            _json_dump(live_evidence_summary) if live_evidence_summary is not None else None,
        )

        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO decisions (
                    id, user_id, created_at, updated_at, query,
                    primary_domain, secondary_domains_json, decision_kind,
                    reversibility, risk_level, routed_experts_json,
                    verdict, verdict_confidence, recommendation, consensus,
                    key_disagreement, minority_report, assumptions_json,
                    evidence_gaps_json, what_would_change_decision_json,
                    next_experiment_json, knowledge_status_json,
                    orchestration_errors_json, learning_context_json,
                    framework_selection_json, live_evidence_json
                ) VALUES (
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                decision_values,
            )

            for memo in result.memos:
                rebuttal = rebuttals.get(memo.expert_id)
                conn.execute(
                    """
                    INSERT INTO decision_expert_votes (
                        decision_id, expert_id, blind_vote, blind_confidence,
                        revised_vote, revised_confidence, knowledge_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        decision_id,
                        memo.expert_id,
                        memo.vote.value,
                        memo.confidence,
                        rebuttal.revised_vote.value if rebuttal is not None else None,
                        rebuttal.revised_confidence if rebuttal is not None else None,
                        memo.knowledge_status,
                    ),
                )

        return decision_id

    @staticmethod
    def _decision_from_row(row: sqlite3.Row) -> dict[str, Any]:
        record = _CoreDecisionMemoryStore._decision_from_row(row)
        record["live_evidence_summary"] = (
            _json_load(row["live_evidence_json"])
            if "live_evidence_json" in row.keys() and row["live_evidence_json"] is not None
            else None
        )
        return record
