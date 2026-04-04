"""
NemoClaw SQLiteStore — Unified persistence layer.

Replaces 6+ JSON files with a single SQLite DB in WAL mode.
Litestream streams WAL to S3/B2 for ~1s RPO.

Location: ~/.nemoclaw/nemoclaw.db
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("cc.sqlite_store")

SCHEMA_VERSION = 1

SCHEMA_SQL = """
-- Messages (replaces messages.json)
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    lane_id TEXT NOT NULL,
    sender_id TEXT,
    sender_name TEXT,
    sender_type TEXT,
    content TEXT,
    message_type TEXT DEFAULT 'chat',
    metadata TEXT DEFAULT '{}',
    reply_to TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_msg_lane ON messages(lane_id);
CREATE INDEX IF NOT EXISTS idx_msg_created ON messages(created_at);

-- Lanes (replaces lanes portion of messages.json)
CREATE TABLE IF NOT EXISTS lanes (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    lane_type TEXT NOT NULL DEFAULT 'dm',
    participants TEXT DEFAULT '[]',
    avatar TEXT DEFAULT '',
    created_at TEXT NOT NULL
);

-- Agent memory (replaces ~/.nemoclaw/agent-memory/*.json)
CREATE TABLE IF NOT EXISTS agent_memory (
    agent_id TEXT NOT NULL,
    lesson_key TEXT NOT NULL,
    lesson_value TEXT,
    source TEXT DEFAULT '',
    importance REAL DEFAULT 1.0,
    timestamp REAL,
    access_count INTEGER DEFAULT 0,
    PRIMARY KEY (agent_id, lesson_key)
);
CREATE INDEX IF NOT EXISTS idx_am_agent ON agent_memory(agent_id);

-- Project memory (replaces ~/.nemoclaw/project-memory/*.json)
CREATE TABLE IF NOT EXISTS project_memory (
    project_id TEXT NOT NULL,
    entry_key TEXT NOT NULL,
    entry_value TEXT,
    agent_id TEXT DEFAULT '',
    memory_type TEXT DEFAULT 'operational',
    importance REAL DEFAULT 1.0,
    timestamp REAL,
    PRIMARY KEY (project_id, entry_key)
);
CREATE INDEX IF NOT EXISTS idx_pm_project ON project_memory(project_id);

-- Global state (replaces ~/.nemoclaw/global-state.json)
CREATE TABLE IF NOT EXISTS global_state (
    collection TEXT NOT NULL,
    entry_id TEXT NOT NULL,
    data TEXT NOT NULL DEFAULT '{}',
    agent TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    created_at TEXT,
    updated_at TEXT,
    PRIMARY KEY (collection, entry_id)
);
CREATE INDEX IF NOT EXISTS idx_gs_collection ON global_state(collection);

-- Tasks (replaces backend/data/tasks.json)
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    data TEXT NOT NULL DEFAULT '{}'
);

-- Projects (replaces backend/data/projects.json)
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    data TEXT NOT NULL DEFAULT '{}'
);

-- Checkpoints (replaces ~/.nemoclaw/checkpoints/*.json)
CREATE TABLE IF NOT EXISTS checkpoints (
    agent_id TEXT PRIMARY KEY,
    state TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL
);

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


class SQLiteStore:
    """Thread-safe SQLite persistence with WAL mode for Litestream compatibility."""

    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            db_path = Path.home() / ".nemoclaw" / "nemoclaw.db"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._lock = threading.Lock()

        # Initialize schema
        conn = self._conn()
        conn.executescript(SCHEMA_SQL)
        conn.execute(
            "INSERT OR REPLACE INTO schema_meta (key, value) VALUES (?, ?)",
            ("version", str(SCHEMA_VERSION)),
        )
        conn.commit()
        logger.info("SQLiteStore initialized: %s (WAL mode)", self.db_path)

    def _conn(self) -> sqlite3.Connection:
        """Get thread-local connection with WAL mode."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")  # Safe with WAL
            conn.execute("PRAGMA busy_timeout=5000")
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return self._local.conn

    # ── Messages ─────────────────────────────────────────────────────

    def add_message(self, msg: dict[str, Any]) -> None:
        """Insert or replace a message."""
        self._conn().execute(
            """INSERT OR REPLACE INTO messages
               (id, lane_id, sender_id, sender_name, sender_type, content,
                message_type, metadata, reply_to, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                msg.get("id", ""),
                msg.get("lane_id", ""),
                msg.get("sender_id", ""),
                msg.get("sender_name", ""),
                msg.get("sender_type", ""),
                msg.get("content", ""),
                msg.get("message_type", "chat"),
                json.dumps(msg.get("metadata", {})),
                msg.get("reply_to"),
                msg.get("timestamp", datetime.now(timezone.utc).isoformat()),
            ),
        )
        self._conn().commit()

    def get_messages(self, lane_id: str, limit: int = 50) -> list[dict]:
        """Get messages for a lane, newest first."""
        rows = self._conn().execute(
            "SELECT * FROM messages WHERE lane_id = ? ORDER BY created_at DESC LIMIT ?",
            (lane_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_message_count(self) -> int:
        row = self._conn().execute("SELECT count(*) FROM messages").fetchone()
        return row[0] if row else 0

    # ── Lanes ────────────────────────────────────────────────────────

    def save_lane(self, lane: dict[str, Any]) -> None:
        self._conn().execute(
            """INSERT OR REPLACE INTO lanes (id, name, lane_type, participants, avatar, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                lane.get("id", ""),
                lane.get("name", ""),
                lane.get("lane_type", "dm"),
                json.dumps(lane.get("participants", [])),
                lane.get("avatar", ""),
                lane.get("created_at", datetime.now(timezone.utc).isoformat()),
            ),
        )
        self._conn().commit()

    def get_lanes(self) -> list[dict]:
        rows = self._conn().execute("SELECT * FROM lanes ORDER BY name").fetchall()
        return [dict(r) for r in rows]

    def get_lane_count(self) -> int:
        row = self._conn().execute("SELECT count(*) FROM lanes").fetchone()
        return row[0] if row else 0

    # ── Agent Memory ─────────────────────────────────────────────────

    def save_agent_memory(
        self, agent_id: str, key: str, value: str,
        source: str = "", importance: float = 1.0,
        timestamp: float | None = None, access_count: int = 0,
    ) -> None:
        self._conn().execute(
            """INSERT OR REPLACE INTO agent_memory
               (agent_id, lesson_key, lesson_value, source, importance, timestamp, access_count)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (agent_id, key, value, source, importance,
             timestamp or datetime.now(timezone.utc).timestamp(), access_count),
        )
        self._conn().commit()

    def get_agent_memories(self, agent_id: str) -> list[dict]:
        rows = self._conn().execute(
            "SELECT * FROM agent_memory WHERE agent_id = ? ORDER BY importance DESC",
            (agent_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_all_agent_memories(self) -> dict[str, list[dict]]:
        rows = self._conn().execute("SELECT * FROM agent_memory ORDER BY agent_id").fetchall()
        result: dict[str, list[dict]] = {}
        for r in rows:
            d = dict(r)
            result.setdefault(d["agent_id"], []).append(d)
        return result

    # ── Project Memory ───────────────────────────────────────────────

    def save_project_memory(
        self, project_id: str, key: str, value: str,
        agent_id: str = "", memory_type: str = "operational",
        importance: float = 1.0, timestamp: float | None = None,
    ) -> None:
        self._conn().execute(
            """INSERT OR REPLACE INTO project_memory
               (project_id, entry_key, entry_value, agent_id, memory_type, importance, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (project_id, key, value, agent_id, memory_type, importance,
             timestamp or datetime.now(timezone.utc).timestamp()),
        )
        self._conn().commit()

    def get_project_memories(self, project_id: str) -> list[dict]:
        rows = self._conn().execute(
            "SELECT * FROM project_memory WHERE project_id = ? ORDER BY importance DESC",
            (project_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Global State ─────────────────────────────────────────────────

    def save_global_state(
        self, collection: str, entry_id: str, data: dict,
        agent: str = "", tags: list[str] | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._conn().execute(
            """INSERT OR REPLACE INTO global_state
               (collection, entry_id, data, agent, tags, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, COALESCE(
                   (SELECT created_at FROM global_state WHERE collection=? AND entry_id=?), ?
               ), ?)""",
            (collection, entry_id, json.dumps(data), agent,
             json.dumps(tags or []), collection, entry_id, now, now),
        )
        self._conn().commit()

    def get_global_state(self, collection: str) -> list[dict]:
        rows = self._conn().execute(
            "SELECT * FROM global_state WHERE collection = ? ORDER BY updated_at DESC",
            (collection,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_all_global_state(self) -> dict[str, list[dict]]:
        rows = self._conn().execute("SELECT * FROM global_state ORDER BY collection").fetchall()
        result: dict[str, list[dict]] = {}
        for r in rows:
            d = dict(r)
            result.setdefault(d["collection"], []).append(d)
        return result

    # ── Tasks ────────────────────────────────────────────────────────

    def save_task(self, task_id: str, data: dict) -> None:
        self._conn().execute(
            "INSERT OR REPLACE INTO tasks (id, data) VALUES (?, ?)",
            (task_id, json.dumps(data)),
        )
        self._conn().commit()

    def get_tasks(self) -> list[dict]:
        rows = self._conn().execute("SELECT * FROM tasks").fetchall()
        return [{"id": r["id"], **json.loads(r["data"])} for r in rows]

    # ── Projects ─────────────────────────────────────────────────────

    def save_project(self, project_id: str, data: dict) -> None:
        self._conn().execute(
            "INSERT OR REPLACE INTO projects (id, data) VALUES (?, ?)",
            (project_id, json.dumps(data)),
        )
        self._conn().commit()

    def get_projects(self) -> list[dict]:
        rows = self._conn().execute("SELECT * FROM projects").fetchall()
        return [{"id": r["id"], **json.loads(r["data"])} for r in rows]

    # ── Checkpoints ──────────────────────────────────────────────────

    def save_checkpoint(self, agent_id: str, state: dict) -> None:
        self._conn().execute(
            "INSERT OR REPLACE INTO checkpoints (agent_id, state, updated_at) VALUES (?, ?, ?)",
            (agent_id, json.dumps(state), datetime.now(timezone.utc).isoformat()),
        )
        self._conn().commit()

    def get_checkpoint(self, agent_id: str) -> dict | None:
        row = self._conn().execute(
            "SELECT * FROM checkpoints WHERE agent_id = ?", (agent_id,)
        ).fetchone()
        return dict(row) if row else None

    # ── Stats ────────────────────────────────────────────────────────

    def get_stats(self) -> dict[str, int]:
        tables = ["messages", "lanes", "agent_memory", "project_memory",
                   "global_state", "tasks", "projects", "checkpoints"]
        stats = {}
        for t in tables:
            row = self._conn().execute(f"SELECT count(*) FROM {t}").fetchone()
            stats[t] = row[0] if row else 0
        stats["db_size_bytes"] = self.db_path.stat().st_size if self.db_path.exists() else 0
        return stats

    def close(self) -> None:
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None
