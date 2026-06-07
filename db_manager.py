"""
Database Manager for SQLite-backed state and knowledge storage.

Replaces the old JSON file + FileLock pattern with SQLite in WAL mode,
providing safe concurrent access from multiple processes without external locks.
"""

import json
import os
import sqlite3
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

DB_PATH = "agents_state.db"

# Thread-local connection: each thread/process gets its own connection.
_local = threading.local()


def _get_connection() -> sqlite3.Connection:
    """Obtain a thread-local SQLite connection with WAL mode and busy timeout."""
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(DB_PATH, timeout=30)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA busy_timeout=5000")
        _local.conn.execute("PRAGMA foreign_keys=ON")
    return _local.conn


# ── Schema Initialisation ──────────────────────────────────────────────────


def init_db():
    """Create tables if they do not yet exist."""
    conn = _get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS agents_state (
            activity_key TEXT PRIMARY KEY,
            status TEXT NOT NULL DEFAULT 'Disponible',
            activity_name TEXT DEFAULT '',
            approvals INTEGER NOT NULL DEFAULT 0,
            questions_done INTEGER NOT NULL DEFAULT 0,
            questions_total INTEGER NOT NULL DEFAULT 0,
            agents TEXT NOT NULL DEFAULT '[]',
            last_update TEXT NOT NULL,
            event TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS knowledge (
            signature TEXT PRIMARY KEY,
            answers TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)
    conn.commit()


# ── Agents State CRUD ──────────────────────────────────────────────────────


def load_agents_state(conn: Optional[sqlite3.Connection] = None) -> Dict[str, Dict]:
    """Return the full agents_state as a dict matching the old JSON structure."""
    if conn is None:
        conn = _get_connection()
    cursor = conn.execute("SELECT * FROM agents_state")
    state: Dict[str, Dict] = {}
    for row in cursor:
        key = row["activity_key"]
        entry: Dict[str, Any] = {
            "status": row["status"],
            "activity_name": row["activity_name"],
            "approvals": row["approvals"],
            "questions_done": row["questions_done"],
            "questions_total": row["questions_total"],
            "agents": json.loads(row["agents"]),
            "last_update": row["last_update"],
            "event": row["event"],
        }
        # Preserve backward-compatible agent_id for legacy consumers
        agents = entry["agents"]
        entry["agent_id"] = agents[0] if agents else "-"
        state[key] = entry
    return state


def save_agents_state(state: Dict[str, Dict],
                      conn: Optional[sqlite3.Connection] = None) -> None:
    """Persist the full agents_state dict into the database (upsert)."""
    if conn is None:
        conn = _get_connection()
    now = datetime.now().isoformat()
    for key, data in state.items():
        agents_json = json.dumps(data.get("agents", []), ensure_ascii=False)
        conn.execute("""
            INSERT INTO agents_state
                (activity_key, status, activity_name, approvals,
                 questions_done, questions_total, agents, last_update, event)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(activity_key) DO UPDATE SET
                status            = excluded.status,
                activity_name     = excluded.activity_name,
                approvals         = excluded.approvals,
                questions_done    = excluded.questions_done,
                questions_total   = excluded.questions_total,
                agents            = excluded.agents,
                last_update       = excluded.last_update,
                event             = excluded.event
        """, (
            key,
            data.get("status", "Disponible"),
            data.get("activity_name", ""),
            data.get("approvals", 0),
            data.get("questions_done", 0),
            data.get("questions_total", 0),
            agents_json,
            data.get("last_update", now),
            data.get("event", ""),
        ))


def delete_activity(activity_key: str,
                    conn: Optional[sqlite3.Connection] = None) -> None:
    """Remove a single activity row."""
    if conn is None:
        conn = _get_connection()
    conn.execute("DELETE FROM agents_state WHERE activity_key = ?",
                 (activity_key,))


# ── Knowledge CRUD ─────────────────────────────────────────────────────────


def load_all_knowledge(conn: Optional[sqlite3.Connection] = None) -> Dict[str, List[str]]:
    """Return all knowledge entries as a dict (signature → answers)."""
    if conn is None:
        conn = _get_connection()
    cursor = conn.execute("SELECT signature, answers FROM knowledge")
    knowledge: Dict[str, List[str]] = {}
    for row in cursor:
        knowledge[row["signature"]] = json.loads(row["answers"])
    return knowledge


def save_knowledge(signature: str, answers: List[str],
                   conn: Optional[sqlite3.Connection] = None) -> None:
    """Insert or update a knowledge entry."""
    should_commit = conn is None
    if conn is None:
        conn = _get_connection()
    answers_json = json.dumps(answers, ensure_ascii=False)
    conn.execute("""
        INSERT INTO knowledge (signature, answers, updated_at)
        VALUES (?, ?, datetime('now'))
        ON CONFLICT(signature) DO UPDATE SET
            answers     = excluded.answers,
            updated_at  = datetime('now')
    """, (signature, answers_json))
    if should_commit:
        conn.commit()


def get_knowledge(signature: str,
                  conn: Optional[sqlite3.Connection] = None) -> Optional[List[str]]:
    """Look up a single knowledge entry by signature."""
    if conn is None:
        conn = _get_connection()
    cursor = conn.execute("SELECT answers FROM knowledge WHERE signature = ?",
                          (signature,))
    row = cursor.fetchone()
    return json.loads(row["answers"]) if row else None


# ── Migration helpers ──────────────────────────────────────────────────────


def migrate_from_json(state_json_path: str = "agents_state.json",
                      knowledge_json_path: str = "learned_answers.json") -> None:
    """Import existing JSON data into the SQLite database (idempotent).

    Called automatically on first use if the old files exist.
    """
    init_db()

    # ── Migrate agents_state ───────────────────────────────────────────
    if os.path.exists(state_json_path):
        try:
            with open(state_json_path, "r", encoding="utf-8") as f:
                raw = f.read()
            if raw.strip():
                state = json.loads(raw)
                conn = _get_connection()
                save_agents_state(state, conn)
                conn.commit()
                print(f"[MIGRATION] Imported {len(state)} activities "
                      f"from {state_json_path}")
        except Exception as exc:
            print(f"[MIGRATION] Error migrating {state_json_path}: {exc}")

    # ── Migrate knowledge ──────────────────────────────────────────────
    if os.path.exists(knowledge_json_path):
        try:
            with open(knowledge_json_path, "r", encoding="utf-8") as f:
                raw = f.read()
            if raw.strip():
                knowledge = json.loads(raw)
                conn = _get_connection()
                for sig, answers in knowledge.items():
                    save_knowledge(sig, answers, conn)
                conn.commit()
                print(f"[MIGRATION] Imported {len(knowledge)} knowledge entries "
                      f"from {knowledge_json_path}")
        except Exception as exc:
            print(f"[MIGRATION] Error migrating {knowledge_json_path}: {exc}")
