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
