"""
Persistent users (anonymous), sessions, saved projects, and share links.
SQLite file: data/ai_council_users.db
"""

from __future__ import annotations

import json
import secrets
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "ai_council_users.db"
_LOCK = threading.Lock()


def _connect() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS auth_sessions (
            token TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            config_json TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS shared_deliberations (
            token TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_projects_user ON projects(user_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_user ON auth_sessions(user_id);
        """
    )
    conn.commit()


def _with_conn(fn):
    def inner(*args, **kwargs):
        with _LOCK:
            conn = _connect()
            try:
                _init_schema(conn)
                return fn(conn, *args, **kwargs)
            finally:
                conn.close()

    return inner


@dataclass
class UserBootstrap:
    user_id: str
    session_token: str
    expires_at: str


@_with_conn
def bootstrap_anonymous_user(conn) -> UserBootstrap:
    uid = secrets.token_urlsafe(16)
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    exp = now + timedelta(days=90)
    conn.execute("INSERT INTO users (id, created_at) VALUES (?, ?)", (uid, now.isoformat()))
    conn.execute(
        "INSERT INTO auth_sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (token, uid, now.isoformat(), exp.isoformat()),
    )
    conn.commit()
    return UserBootstrap(user_id=uid, session_token=token, expires_at=exp.isoformat())


@_with_conn
def validate_session(conn, token: Optional[str]) -> Optional[str]:
    if not token or not token.strip():
        return None
    row = conn.execute(
        "SELECT user_id, expires_at FROM auth_sessions WHERE token = ?",
        (token.strip(),),
    ).fetchone()
    if not row:
        return None
    try:
        exp = datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00"))
    except (TypeError, ValueError):
        conn.execute("DELETE FROM auth_sessions WHERE token = ?", (token.strip(),))
        conn.commit()
        return None
    if datetime.now(timezone.utc) > exp:
        conn.execute("DELETE FROM auth_sessions WHERE token = ?", (token.strip(),))
        conn.commit()
        return None
    return str(row["user_id"])


@dataclass
class ProjectRecord:
    id: str
    user_id: str
    name: str
    config: Dict[str, Any]
    updated_at: str


@_with_conn
def create_project(conn, user_id: str, name: str, config: Dict[str, Any]) -> ProjectRecord:
    pid = secrets.token_urlsafe(12)
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO projects (id, user_id, name, config_json, updated_at) VALUES (?, ?, ?, ?, ?)",
        (pid, user_id, name[:200], json.dumps(config, ensure_ascii=False), now),
    )
    conn.commit()
    return ProjectRecord(id=pid, user_id=user_id, name=name[:200], config=config, updated_at=now)


@_with_conn
def list_projects(conn, user_id: str) -> List[ProjectRecord]:
    rows = conn.execute(
        "SELECT id, user_id, name, config_json, updated_at FROM projects WHERE user_id = ? ORDER BY updated_at DESC",
        (user_id,),
    ).fetchall()
    out: List[ProjectRecord] = []
    for r in rows:
        out.append(
            ProjectRecord(
                id=r["id"],
                user_id=r["user_id"],
                name=r["name"],
                config=json.loads(r["config_json"]),
                updated_at=r["updated_at"],
            )
        )
    return out


@_with_conn
def get_project(conn, user_id: str, project_id: str) -> Optional[ProjectRecord]:
    row = conn.execute(
        "SELECT id, user_id, name, config_json, updated_at FROM projects WHERE id = ? AND user_id = ?",
        (project_id, user_id),
    ).fetchone()
    if not row:
        return None
    return ProjectRecord(
        id=row["id"],
        user_id=row["user_id"],
        name=row["name"],
        config=json.loads(row["config_json"]),
        updated_at=row["updated_at"],
    )


@_with_conn
def update_project(conn, user_id: str, project_id: str, name: Optional[str], config: Optional[Dict[str, Any]]) -> Optional[ProjectRecord]:
    row = conn.execute(
        "SELECT id, user_id, name, config_json, updated_at FROM projects WHERE id = ? AND user_id = ?",
        (project_id, user_id),
    ).fetchone()
    if not row:
        return None
    existing_config = json.loads(row["config_json"])
    new_name = name if name is not None else row["name"]
    new_config = config if config is not None else existing_config
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE projects SET name = ?, config_json = ?, updated_at = ? WHERE id = ? AND user_id = ?",
        (new_name[:200], json.dumps(new_config, ensure_ascii=False), now, project_id, user_id),
    )
    conn.commit()
    return ProjectRecord(
        id=project_id,
        user_id=user_id,
        name=new_name[:200],
        config=new_config,
        updated_at=now,
    )


@_with_conn
def delete_project(conn, user_id: str, project_id: str) -> bool:
    cur = conn.execute("DELETE FROM projects WHERE id = ? AND user_id = ?", (project_id, user_id))
    conn.commit()
    return cur.rowcount > 0


@_with_conn
def create_share_link(conn, payload: Dict[str, Any], ttl_hours: int = 720) -> str:
    token = secrets.token_urlsafe(24)
    now = datetime.now(timezone.utc)
    exp = now + timedelta(hours=ttl_hours)
    conn.execute(
        "INSERT INTO shared_deliberations (token, payload_json, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (token, json.dumps(payload, ensure_ascii=False), now.isoformat(), exp.isoformat()),
    )
    conn.commit()
    return token


@_with_conn
def get_shared_payload(conn, token: str) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        "SELECT payload_json, expires_at FROM shared_deliberations WHERE token = ?",
        (token.strip(),),
    ).fetchone()
    if not row:
        return None
    exp_raw = row["expires_at"]
    if exp_raw:
        try:
            exp = datetime.fromisoformat(exp_raw.replace("Z", "+00:00"))
            if datetime.now(timezone.utc) > exp:
                conn.execute("DELETE FROM shared_deliberations WHERE token = ?", (token.strip(),))
                conn.commit()
                return None
        except (TypeError, ValueError):
            pass
    return json.loads(row["payload_json"])
