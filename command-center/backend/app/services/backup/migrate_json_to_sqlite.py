"""
Migrate all JSON persistence files → SQLite.

Idempotent: uses INSERT OR REPLACE, safe to re-run.
Run: python3 -m app.services.backup.migrate_json_to_sqlite
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .sqlite_store import SQLiteStore

logger = logging.getLogger("cc.migrate")

NEMOCLAW_HOME = Path.home() / ".nemoclaw"
BACKEND_DATA = Path(__file__).resolve().parents[3] / "data"


def migrate_messages(store: SQLiteStore) -> int:
    """Migrate messages.json → messages + lanes tables."""
    path = BACKEND_DATA / "messages.json"
    if not path.exists():
        logger.info("No messages.json found, skipping")
        return 0

    data = json.loads(path.read_text())
    lanes = data.get("lanes", {})
    count = 0

    # Save lanes
    for lane_id, lane_data in lanes.items():
        store.save_lane({
            "id": lane_id,
            "name": lane_data.get("name", lane_id),
            "lane_type": lane_data.get("lane_type", "dm"),
            "participants": lane_data.get("participants", []),
            "avatar": lane_data.get("avatar", ""),
            "created_at": lane_data.get("created_at", ""),
        })

    # Save messages — flat dict {msg_id: msg_data} in "messages" key
    messages = data.get("messages", {})
    if isinstance(messages, dict):
        for msg_id, msg in messages.items():
            if not isinstance(msg, dict):
                continue
            store.add_message({
                "id": msg.get("id", msg_id),
                "lane_id": msg.get("lane_id", ""),
                "sender_id": msg.get("sender_id", ""),
                "sender_name": msg.get("sender_name", ""),
                "sender_type": msg.get("sender_type", ""),
                "content": msg.get("content", ""),
                "message_type": msg.get("message_type", "chat"),
                "metadata": msg.get("metadata", {}),
                "reply_to": msg.get("reply_to"),
                "timestamp": msg.get("timestamp", ""),
            })
            count += 1

    logger.info("Migrated %d messages from %d lanes", count, len(lanes))
    return count


def migrate_agent_memory(store: SQLiteStore) -> int:
    """Migrate ~/.nemoclaw/agent-memory/*.json → agent_memory table."""
    mem_dir = NEMOCLAW_HOME / "agent-memory"
    if not mem_dir.exists():
        return 0

    count = 0
    for f in mem_dir.glob("*.json"):
        agent_id = f.stem
        try:
            data = json.loads(f.read_text())
            lessons = data.get("lessons", data)
            if isinstance(lessons, dict):
                for key, entry in lessons.items():
                    if isinstance(entry, dict):
                        store.save_agent_memory(
                            agent_id=agent_id,
                            key=key,
                            value=entry.get("value", str(entry)),
                            source=entry.get("source", ""),
                            importance=entry.get("importance", 1.0),
                            timestamp=entry.get("timestamp"),
                            access_count=entry.get("access_count", 0),
                        )
                        count += 1
        except Exception as e:
            logger.warning("Failed to migrate agent memory %s: %s", f.name, e)

    logger.info("Migrated %d agent memory entries", count)
    return count


def migrate_project_memory(store: SQLiteStore) -> int:
    """Migrate ~/.nemoclaw/project-memory/*.json → project_memory table."""
    mem_dir = NEMOCLAW_HOME / "project-memory"
    if not mem_dir.exists():
        return 0

    count = 0
    for f in mem_dir.glob("*.json"):
        project_id = f.stem
        try:
            data = json.loads(f.read_text())
            entries = data.get("entries", data)
            if isinstance(entries, dict):
                for key, entry in entries.items():
                    if isinstance(entry, dict):
                        store.save_project_memory(
                            project_id=project_id,
                            key=key,
                            value=entry.get("value", str(entry)),
                            agent_id=entry.get("agent_id", ""),
                            memory_type=entry.get("type", "operational"),
                            importance=entry.get("importance", 1.0),
                            timestamp=entry.get("timestamp"),
                        )
                        count += 1
        except Exception as e:
            logger.warning("Failed to migrate project memory %s: %s", f.name, e)

    logger.info("Migrated %d project memory entries", count)
    return count


def migrate_global_state(store: SQLiteStore) -> int:
    """Migrate ~/.nemoclaw/global-state.json → global_state table."""
    path = NEMOCLAW_HOME / "global-state.json"
    if not path.exists():
        return 0

    count = 0
    data = json.loads(path.read_text())
    for collection, entries in data.items():
        if isinstance(entries, list):
            for i, entry in enumerate(entries):
                entry_id = entry.get("id", str(i))
                store.save_global_state(
                    collection=collection,
                    entry_id=entry_id,
                    data=entry,
                    agent=entry.get("agent", ""),
                    tags=entry.get("tags", []),
                )
                count += 1

    logger.info("Migrated %d global state entries", count)
    return count


def migrate_tasks(store: SQLiteStore) -> int:
    """Migrate backend/data/tasks.json → tasks table."""
    path = BACKEND_DATA / "tasks.json"
    if not path.exists():
        return 0

    data = json.loads(path.read_text())
    tasks_raw = data.get("tasks", data)
    count = 0
    if isinstance(tasks_raw, dict):
        for tid, task in tasks_raw.items():
            if isinstance(task, dict):
                store.save_task(tid, task)
                count += 1
    elif isinstance(tasks_raw, list):
        for task in tasks_raw:
            if isinstance(task, dict):
                tid = task.get("id", task.get("task_id", ""))
                if tid:
                    store.save_task(tid, task)
                    count += 1

    logger.info("Migrated %d tasks", count)
    return count


def migrate_projects(store: SQLiteStore) -> int:
    """Migrate backend/data/projects.json → projects table."""
    path = BACKEND_DATA / "projects.json"
    if not path.exists():
        return 0

    data = json.loads(path.read_text())
    projects_raw = data.get("projects", data)
    count = 0
    if isinstance(projects_raw, dict):
        for pid, proj in projects_raw.items():
            if isinstance(proj, dict):
                store.save_project(pid, proj)
                count += 1
    elif isinstance(projects_raw, list):
        for proj in projects_raw:
            if isinstance(proj, dict):
                pid = proj.get("id", proj.get("project_id", ""))
                if pid:
                    store.save_project(pid, proj)
                    count += 1

    logger.info("Migrated %d projects", count)
    return count


def run_migration(db_path: str | Path | None = None) -> dict[str, int]:
    """Run full migration. Returns counts per table."""
    store = SQLiteStore(db_path)

    results = {
        "messages": migrate_messages(store),
        "agent_memory": migrate_agent_memory(store),
        "project_memory": migrate_project_memory(store),
        "global_state": migrate_global_state(store),
        "tasks": migrate_tasks(store),
        "projects": migrate_projects(store),
    }

    stats = store.get_stats()
    logger.info("Migration complete. DB stats: %s", stats)
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    results = run_migration()
    print(f"Migration results: {results}")
