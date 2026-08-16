from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class DecisionLearningStore:
    """Read-only, user-scoped view over resolved Decision Memory records."""

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def resolved_decisions(
        self,
        user_id: str,
        *,
        primary_domain: str | None = None,
    ) -> list[dict[str, Any]]:
        sql = """
            SELECT d.id AS decision_id,
                   d.created_at,
                   d.primary_domain,
                   d.secondary_domains_json,
                   d.decision_kind,
                   d.reversibility,
                   d.risk_level,
                   d.verdict,
                   d.verdict_confidence,
                   o.status AS outcome_status,
                   o.resolved_vote,
                   o.updated_at AS outcome_updated_at
            FROM decisions AS d
            JOIN decision_outcomes AS o
              ON o.decision_id = d.id AND o.user_id = d.user_id
            WHERE d.user_id = ?
              AND o.user_id = ?
              AND o.resolved_vote IS NOT NULL
        """
        params: list[Any] = [user_id, user_id]
        if primary_domain is not None:
            sql += " AND d.primary_domain = ?"
            params.append(primary_domain)
        sql += " ORDER BY o.updated_at DESC, d.id ASC"

        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        return [
            {
                **dict(row),
                "secondary_domains": json.loads(row["secondary_domains_json"] or "[]"),
            }
            for row in rows
        ]

    def expert_predictions(
        self,
        user_id: str,
        expert_ids: list[str],
        primary_domain: str,
    ) -> list[dict[str, Any]]:
        if not expert_ids:
            return []

        placeholders = ",".join("?" for _ in expert_ids)
        sql = f"""
            SELECT d.id AS decision_id,
                   v.expert_id,
                   v.blind_vote AS predicted_vote,
                   v.blind_confidence AS confidence,
                   o.resolved_vote,
                   d.primary_domain
            FROM decision_expert_votes AS v
            JOIN decisions AS d ON d.id = v.decision_id
            JOIN decision_outcomes AS o
              ON o.decision_id = d.id AND o.user_id = d.user_id
            WHERE d.user_id = ?
              AND o.user_id = ?
              AND d.primary_domain = ?
              AND o.resolved_vote IS NOT NULL
              AND v.expert_id IN ({placeholders})
            ORDER BY d.created_at, d.id, v.expert_id
        """
        params = [user_id, user_id, primary_domain, *expert_ids]
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def chairman_predictions(
        self,
        user_id: str,
        primary_domain: str,
    ) -> list[dict[str, Any]]:
        sql = """
            SELECT d.id AS decision_id,
                   'chairman' AS expert_id,
                   d.verdict AS predicted_vote,
                   d.verdict_confidence AS confidence,
                   o.resolved_vote,
                   d.primary_domain
            FROM decisions AS d
            JOIN decision_outcomes AS o
              ON o.decision_id = d.id AND o.user_id = d.user_id
            WHERE d.user_id = ?
              AND o.user_id = ?
              AND d.primary_domain = ?
              AND o.resolved_vote IS NOT NULL
            ORDER BY d.created_at, d.id
        """
        with self._connect() as conn:
            rows = conn.execute(sql, (user_id, user_id, primary_domain)).fetchall()
        return [dict(row) for row in rows]
