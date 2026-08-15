from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.council.council_os_models import CouncilOSResult

_DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "ai_council_decisions.db"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _json_load(value: str) -> Any:
    return json.loads(value)


def _aggregate_predictions(predictions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, float | int]] = {}
    for prediction in predictions:
        expert_id = str(prediction["expert_id"])
        predicted_vote = str(prediction["predicted_vote"])
        resolved_vote = str(prediction["resolved_vote"])
        confidence = float(prediction["confidence"])
        correctness = 1.0 if predicted_vote == resolved_vote else 0.0
        values = grouped.setdefault(
            expert_id,
            {
                "sample_size": 0,
                "correct_count": 0,
                "confidence_sum": 0.0,
                "error_sum": 0.0,
            },
        )
        values["sample_size"] += 1
        values["correct_count"] += int(correctness)
        values["confidence_sum"] += confidence
        values["error_sum"] += (confidence - correctness) ** 2

    output: list[dict[str, Any]] = []
    for expert_id in sorted(grouped):
        values = grouped[expert_id]
        sample_size = int(values["sample_size"])
        correct_count = int(values["correct_count"])
        output.append(
            {
                "expert_id": expert_id,
                "sample_size": sample_size,
                "correct_count": correct_count,
                "hit_rate": round(correct_count / sample_size, 6),
                "mean_confidence": round(float(values["confidence_sum"]) / sample_size, 6),
                "brier_like_error": round(float(values["error_sum"]) / sample_size, 6),
            }
        )
    return output


class DecisionMemoryStore:
    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path is not None else _DEFAULT_DB_PATH
        self._lock = threading.Lock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _initialize(self) -> None:
        with self._lock, self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS decisions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    query TEXT NOT NULL,
                    primary_domain TEXT NOT NULL,
                    secondary_domains_json TEXT NOT NULL,
                    decision_kind TEXT NOT NULL,
                    reversibility TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    routed_experts_json TEXT NOT NULL,
                    verdict TEXT NOT NULL,
                    verdict_confidence REAL NOT NULL,
                    recommendation TEXT NOT NULL,
                    consensus TEXT NOT NULL,
                    key_disagreement TEXT NOT NULL,
                    minority_report TEXT NOT NULL,
                    assumptions_json TEXT NOT NULL,
                    evidence_gaps_json TEXT NOT NULL,
                    what_would_change_decision_json TEXT NOT NULL,
                    next_experiment_json TEXT,
                    knowledge_status_json TEXT NOT NULL,
                    orchestration_errors_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS decision_expert_votes (
                    decision_id TEXT NOT NULL,
                    expert_id TEXT NOT NULL,
                    blind_vote TEXT NOT NULL,
                    blind_confidence REAL NOT NULL,
                    revised_vote TEXT,
                    revised_confidence REAL,
                    knowledge_status TEXT NOT NULL,
                    PRIMARY KEY (decision_id, expert_id),
                    FOREIGN KEY (decision_id) REFERENCES decisions(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS decision_outcomes (
                    decision_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    resolved_vote TEXT,
                    experiment_result TEXT,
                    postmortem TEXT,
                    notes TEXT,
                    FOREIGN KEY (decision_id) REFERENCES decisions(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_decisions_user_created
                    ON decisions(user_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_decisions_user_domain
                    ON decisions(user_id, primary_domain);
                CREATE INDEX IF NOT EXISTS idx_decisions_user_verdict
                    ON decisions(user_id, verdict);
                CREATE INDEX IF NOT EXISTS idx_outcomes_user_status
                    ON decision_outcomes(user_id, status);
                """
            )

    def capture_decision(self, user_id: str, query: str, result: CouncilOSResult) -> str:
        decision_id = str(uuid.uuid4())
        now = _now_iso()
        profile = result.profile
        verdict = result.verdict
        next_experiment = (
            verdict.next_experiment.model_dump(mode="json") if verdict.next_experiment is not None else None
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
                    orchestration_errors_json
                ) VALUES (
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
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
        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "query": row["query"],
            "primary_domain": row["primary_domain"],
            "secondary_domains": _json_load(row["secondary_domains_json"]),
            "decision_kind": row["decision_kind"],
            "reversibility": row["reversibility"],
            "risk_level": row["risk_level"],
            "routed_experts": _json_load(row["routed_experts_json"]),
            "verdict": row["verdict"],
            "verdict_confidence": row["verdict_confidence"],
            "recommendation": row["recommendation"],
            "consensus": row["consensus"],
            "key_disagreement": row["key_disagreement"],
            "minority_report": row["minority_report"],
            "assumptions": _json_load(row["assumptions_json"]),
            "evidence_gaps": _json_load(row["evidence_gaps_json"]),
            "what_would_change_decision": _json_load(row["what_would_change_decision_json"]),
            "next_experiment": (
                _json_load(row["next_experiment_json"])
                if row["next_experiment_json"] is not None
                else None
            ),
            "knowledge_status_by_expert": _json_load(row["knowledge_status_json"]),
            "orchestration_errors": _json_load(row["orchestration_errors_json"]),
        }

    @staticmethod
    def _vote_from_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "expert_id": row["expert_id"],
            "blind_vote": row["blind_vote"],
            "blind_confidence": row["blind_confidence"],
            "revised_vote": row["revised_vote"],
            "revised_confidence": row["revised_confidence"],
            "knowledge_status": row["knowledge_status"],
        }

    @staticmethod
    def _outcome_from_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        return {
            "status": row["status"],
            "resolved_vote": row["resolved_vote"],
            "experiment_result": row["experiment_result"],
            "postmortem": row["postmortem"],
            "notes": row["notes"],
            "updated_at": row["updated_at"],
        }

    def get_decision(self, user_id: str, decision_id: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM decisions WHERE id = ? AND user_id = ?",
                (decision_id, user_id),
            ).fetchone()
            if row is None:
                return None

            votes = conn.execute(
                """
                SELECT expert_id, blind_vote, blind_confidence,
                       revised_vote, revised_confidence, knowledge_status
                FROM decision_expert_votes
                WHERE decision_id = ?
                ORDER BY expert_id
                """,
                (decision_id,),
            ).fetchall()
            outcome = conn.execute(
                "SELECT * FROM decision_outcomes WHERE decision_id = ? AND user_id = ?",
                (decision_id, user_id),
            ).fetchone()

        record = self._decision_from_row(row)
        record["expert_votes"] = [self._vote_from_row(vote) for vote in votes]
        record["outcome"] = self._outcome_from_row(outcome)
        return record

    def list_decisions(
        self,
        user_id: str,
        *,
        limit: int = 50,
        primary_domain: str | None = None,
        verdict: str | None = None,
        outcome_status: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses = ["d.user_id = ?"]
        params: list[Any] = [user_id]
        if primary_domain is not None:
            clauses.append("d.primary_domain = ?")
            params.append(primary_domain)
        if verdict is not None:
            clauses.append("d.verdict = ?")
            params.append(verdict)
        if outcome_status is not None:
            clauses.append("o.status = ?")
            params.append(outcome_status)
        params.append(limit)

        query = f"""
            SELECT d.*, o.status AS outcome_status, o.resolved_vote AS outcome_resolved_vote,
                   o.updated_at AS outcome_updated_at
            FROM decisions AS d
            LEFT JOIN decision_outcomes AS o
              ON o.decision_id = d.id AND o.user_id = d.user_id
            WHERE {' AND '.join(clauses)}
            ORDER BY d.created_at DESC
            LIMIT ?
        """

        with self._lock, self._connect() as conn:
            rows = conn.execute(query, params).fetchall()

        items: list[dict[str, Any]] = []
        for row in rows:
            items.append(
                {
                    "id": row["id"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "query": row["query"],
                    "primary_domain": row["primary_domain"],
                    "decision_kind": row["decision_kind"],
                    "risk_level": row["risk_level"],
                    "verdict": row["verdict"],
                    "verdict_confidence": row["verdict_confidence"],
                    "has_outcome": row["outcome_status"] is not None,
                    "outcome": (
                        {
                            "status": row["outcome_status"],
                            "resolved_vote": row["outcome_resolved_vote"],
                            "updated_at": row["outcome_updated_at"],
                        }
                        if row["outcome_status"] is not None
                        else None
                    ),
                }
            )
        return items

    def upsert_outcome(
        self,
        user_id: str,
        decision_id: str,
        *,
        status: str,
        resolved_vote: str | None,
        experiment_result: str | None,
        postmortem: str | None,
        notes: str | None,
    ) -> dict[str, Any] | None:
        now = _now_iso()
        with self._lock, self._connect() as conn:
            owner = conn.execute(
                "SELECT 1 FROM decisions WHERE id = ? AND user_id = ?",
                (decision_id, user_id),
            ).fetchone()
            if owner is None:
                return None

            conn.execute(
                """
                INSERT INTO decision_outcomes (
                    decision_id, user_id, updated_at, status, resolved_vote,
                    experiment_result, postmortem, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(decision_id) DO UPDATE SET
                    user_id = excluded.user_id,
                    updated_at = excluded.updated_at,
                    status = excluded.status,
                    resolved_vote = excluded.resolved_vote,
                    experiment_result = excluded.experiment_result,
                    postmortem = excluded.postmortem,
                    notes = excluded.notes
                """,
                (
                    decision_id,
                    user_id,
                    now,
                    status,
                    resolved_vote,
                    experiment_result,
                    postmortem,
                    notes,
                ),
            )
            conn.execute(
                "UPDATE decisions SET updated_at = ? WHERE id = ? AND user_id = ?",
                (now, decision_id, user_id),
            )
            outcome = conn.execute(
                "SELECT * FROM decision_outcomes WHERE decision_id = ? AND user_id = ?",
                (decision_id, user_id),
            ).fetchone()

        return self._outcome_from_row(outcome)

    def calibration_report(self, user_id: str) -> dict[str, Any]:
        with self._lock, self._connect() as conn:
            decisions = conn.execute(
                """
                SELECT d.id, d.primary_domain, d.verdict, d.verdict_confidence,
                       o.resolved_vote
                FROM decisions AS d
                JOIN decision_outcomes AS o
                  ON o.decision_id = d.id AND o.user_id = d.user_id
                WHERE d.user_id = ?
                  AND o.user_id = ?
                  AND o.resolved_vote IS NOT NULL
                ORDER BY d.created_at, d.id
                """,
                (user_id, user_id),
            ).fetchall()
            vote_rows = conn.execute(
                """
                SELECT v.expert_id, v.blind_vote, v.blind_confidence,
                       d.primary_domain, o.resolved_vote
                FROM decision_expert_votes AS v
                JOIN decisions AS d ON d.id = v.decision_id
                JOIN decision_outcomes AS o
                  ON o.decision_id = d.id AND o.user_id = d.user_id
                WHERE d.user_id = ?
                  AND o.user_id = ?
                  AND o.resolved_vote IS NOT NULL
                ORDER BY d.created_at, d.id, v.expert_id
                """,
                (user_id, user_id),
            ).fetchall()

        if not decisions:
            return {"sample_size": 0, "experts": [], "domains": {}}

        predictions: list[dict[str, Any]] = [
            {
                "expert_id": row["expert_id"],
                "predicted_vote": row["blind_vote"],
                "confidence": row["blind_confidence"],
                "resolved_vote": row["resolved_vote"],
                "primary_domain": row["primary_domain"],
            }
            for row in vote_rows
        ]
        predictions.extend(
            {
                "expert_id": "chairman",
                "predicted_vote": row["verdict"],
                "confidence": row["verdict_confidence"],
                "resolved_vote": row["resolved_vote"],
                "primary_domain": row["primary_domain"],
            }
            for row in decisions
        )

        domains: dict[str, list[dict[str, Any]]] = {}
        for domain in sorted({str(row["primary_domain"]) for row in decisions}):
            domain_predictions = [
                prediction
                for prediction in predictions
                if prediction["primary_domain"] == domain
            ]
            domains[domain] = _aggregate_predictions(domain_predictions)

        return {
            "sample_size": len(decisions),
            "experts": _aggregate_predictions(predictions),
            "domains": domains,
        }
