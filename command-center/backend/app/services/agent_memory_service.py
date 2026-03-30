"""
NemoClaw Execution Engine — AgentMemoryService (E-4a)

Persistent learning that survives reboot (#2).
Each agent stores lessons (key-value) with time-weighting.
Recent lessons rank higher in decision-making.

Persistence: JSON files in ~/.nemoclaw/agent-memory/

NEW FILE: command-center/backend/app/services/agent_memory_service.py
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("cc.memory")


class Lesson:
    """A single learned insight."""

    def __init__(
        self,
        key: str,
        value: str,
        source: str = "",
        importance: float = 1.0,
        timestamp: float | None = None,
    ):
        self.key = key
        self.value = value
        self.source = source
        self.importance = importance
        self.timestamp = timestamp or time.time()
        self.access_count = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "source": self.source,
            "importance": self.importance,
            "timestamp": self.timestamp,
            "access_count": self.access_count,
            "age_hours": round((time.time() - self.timestamp) / 3600, 1),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Lesson":
        lesson = cls(
            key=d["key"],
            value=d["value"],
            source=d.get("source", ""),
            importance=d.get("importance", 1.0),
            timestamp=d.get("timestamp", time.time()),
        )
        lesson.access_count = d.get("access_count", 0)
        return lesson

    def weighted_score(self) -> float:
        """Time-weighted importance: recent lessons score higher."""
        age_hours = (time.time() - self.timestamp) / 3600
        recency_factor = 1.0 / (1.0 + age_hours / 24.0)  # halves every 24h
        return self.importance * recency_factor


class AgentMemoryService:
    """
    Per-agent persistent memory.

    Each agent has an isolated memory store on disk.
    Lessons are key-value pairs with time-weighted scoring.
    """

    def __init__(self, memory_dir: Path | None = None):
        self.memory_dir = memory_dir or (Path.home() / ".nemoclaw" / "agent-memory")
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self._stores: dict[str, dict[str, Lesson]] = {}
        self._load_all()
        logger.info(
            "AgentMemoryService initialized (%d agents, dir=%s)",
            len(self._stores), self.memory_dir,
        )

    def _agent_file(self, agent_id: str) -> Path:
        return self.memory_dir / f"{agent_id}.json"

    def _load_all(self):
        """Load all agent memories from disk."""
        for path in self.memory_dir.glob("*.json"):
            agent_id = path.stem
            try:
                data = json.loads(path.read_text())
                self._stores[agent_id] = {
                    k: Lesson.from_dict(v)
                    for k, v in data.items()
                }
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("Failed to load memory for %s: %s", agent_id, e)
                self._stores[agent_id] = {}

    def _save(self, agent_id: str):
        """Persist agent memory to disk."""
        store = self._stores.get(agent_id, {})
        data = {k: v.to_dict() for k, v in store.items()}
        self._agent_file(agent_id).write_text(
            json.dumps(data, indent=2, default=str)
        )

    def learn(
        self,
        agent_id: str,
        key: str,
        value: str,
        source: str = "",
        importance: float = 1.0,
    ) -> Lesson:
        """Store a lesson for an agent."""
        if agent_id not in self._stores:
            self._stores[agent_id] = {}

        lesson = Lesson(
            key=key, value=value,
            source=source, importance=importance,
        )
        self._stores[agent_id][key] = lesson
        self._save(agent_id)

        logger.debug("Agent %s learned: %s", agent_id, key)
        return lesson

    def recall(self, agent_id: str, key: str) -> Lesson | None:
        """Recall a specific lesson."""
        store = self._stores.get(agent_id, {})
        lesson = store.get(key)
        if lesson:
            lesson.access_count += 1
        return lesson

    def get_top_lessons(self, agent_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """Get top lessons by time-weighted score."""
        store = self._stores.get(agent_id, {})
        sorted_lessons = sorted(
            store.values(),
            key=lambda l: l.weighted_score(),
            reverse=True,
        )
        return [l.to_dict() for l in sorted_lessons[:limit]]

    def get_all_lessons(self, agent_id: str) -> list[dict[str, Any]]:
        """Get all lessons for an agent."""
        store = self._stores.get(agent_id, {})
        return [l.to_dict() for l in store.values()]

    def forget(self, agent_id: str, key: str) -> bool:
        """Remove a lesson."""
        store = self._stores.get(agent_id, {})
        if key in store:
            del store[key]
            self._save(agent_id)
            return True
        return False

    def get_agents_with_memory(self) -> list[str]:
        """List agents that have memories."""
        return list(self._stores.keys())
