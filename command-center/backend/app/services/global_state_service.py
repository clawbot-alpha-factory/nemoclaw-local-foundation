"""
NemoClaw Execution Engine — Global State Service (E-9)

Persistent memory layer across all agent runs.
Stores: leads, deals, content performance, experiments, channel ROI.
This is what makes agents stateful instead of stateless scripts.

Persists to: ~/.nemoclaw/global-state.json

NEW FILE: command-center/backend/app/services/global_state_service.py
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("cc.global_state")


class GlobalStateService:
    """
    Persistent global memory for the entire agent system.

    Collections: leads, deals, content, experiments, channels, learnings
    Each entry has: id, data, created_at, updated_at, agent, tags
    """

    COLLECTIONS = ["leads", "deals", "content", "experiments", "channels", "learnings", "offers"]

    def __init__(self):
        self._persist_path = Path.home() / ".nemoclaw" / "global-state.json"
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        self._state: dict[str, list[dict[str, Any]]] = {}
        self._load()
        logger.info(
            "GlobalStateService initialized (%s)",
            ", ".join(f"{k}={len(v)}" for k, v in self._state.items() if v),
        )

    def _load(self) -> None:
        """Load state from disk."""
        if self._persist_path.exists():
            try:
                self._state = json.loads(self._persist_path.read_text())
            except Exception as e:
                logger.warning("Failed to load global state: %s", e)
                self._state = {}
        for col in self.COLLECTIONS:
            if col not in self._state:
                self._state[col] = []

    def _save(self) -> None:
        """Persist state to disk."""
        try:
            self._persist_path.write_text(json.dumps(self._state, indent=2, default=str))
        except Exception as e:
            logger.warning("Failed to save global state: %s", e)

    def add(self, collection: str, entry_id: str, data: dict[str, Any],
            agent: str = "", tags: list[str] | None = None) -> dict[str, Any]:
        """Add or update an entry in a collection."""
        if collection not in self.COLLECTIONS:
            return {"error": f"Unknown collection: {collection}. Available: {self.COLLECTIONS}"}

        now = datetime.now(timezone.utc).isoformat()
        entries = self._state[collection]

        # Update if exists
        for entry in entries:
            if entry.get("id") == entry_id:
                entry["data"].update(data)
                entry["updated_at"] = now
                entry["agent"] = agent or entry.get("agent", "")
                if tags:
                    entry["tags"] = list(set(entry.get("tags", []) + tags))
                self._save()
                return {"status": "updated", "id": entry_id, "collection": collection}

        # Create new
        entry = {
            "id": entry_id,
            "data": data,
            "created_at": now,
            "updated_at": now,
            "agent": agent,
            "tags": tags or [],
        }
        entries.append(entry)

        # Cap collections at 5000 entries
        if len(entries) > 5000:
            self._state[collection] = entries[-5000:]

        self._save()
        return {"status": "created", "id": entry_id, "collection": collection}

    def get(self, collection: str, entry_id: str) -> dict[str, Any] | None:
        """Get a specific entry."""
        if collection not in self._state:
            return None
        for entry in self._state[collection]:
            if entry.get("id") == entry_id:
                return entry
        return None

    def query(self, collection: str, tags: list[str] | None = None,
              agent: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        """Query entries with optional filters."""
        if collection not in self._state:
            return []
        entries = self._state[collection]
        if tags:
            entries = [e for e in entries if set(tags).intersection(set(e.get("tags", [])))]
        if agent:
            entries = [e for e in entries if e.get("agent") == agent]
        return entries[-limit:]

    def delete(self, collection: str, entry_id: str) -> bool:
        """Delete an entry."""
        if collection not in self._state:
            return False
        before = len(self._state[collection])
        self._state[collection] = [e for e in self._state[collection] if e.get("id") != entry_id]
        if len(self._state[collection]) < before:
            self._save()
            return True
        return False

    def get_stats(self) -> dict[str, Any]:
        """Get state statistics."""
        return {
            "collections": {col: len(entries) for col, entries in self._state.items()},
            "total_entries": sum(len(v) for v in self._state.values()),
            "persist_path": str(self._persist_path),
            "file_size_kb": round(self._persist_path.stat().st_size / 1024, 1)
            if self._persist_path.exists() else 0,
        }

    def get_context_for_agent(self, agent_id: str, limit: int = 20) -> dict[str, Any]:
        """Get relevant state context for an agent's decision-making."""
        context: dict[str, Any] = {}
        for col in self.COLLECTIONS:
            entries = self.query(col, agent=agent_id, limit=limit)
            if not entries:
                entries = self.query(col, limit=5)  # fallback: recent entries
            if entries:
                context[col] = entries
        return context

    def record_performance(self, skill_id: str, success: bool, revenue: float = 0,
                           channel: str = "", agent: str = "") -> None:
        """Record skill execution performance for feedback loops."""
        perf_id = f"perf-{skill_id}-{int(time.time())}"
        self.add("learnings", perf_id, {
            "skill_id": skill_id,
            "success": success,
            "revenue": revenue,
            "channel": channel,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }, agent=agent, tags=["performance", skill_id, channel] if channel else ["performance", skill_id])

    def get_channel_roi(self) -> dict[str, Any]:
        """Calculate ROI per channel from performance data."""
        perfs = self.query("learnings", tags=["performance"], limit=500)
        channels: dict[str, dict[str, float]] = {}
        for p in perfs:
            ch = p["data"].get("channel", "unknown")
            if ch not in channels:
                channels[ch] = {"revenue": 0, "successes": 0, "failures": 0}
            if p["data"].get("success"):
                channels[ch]["successes"] += 1
                channels[ch]["revenue"] += p["data"].get("revenue", 0)
            else:
                channels[ch]["failures"] += 1
        return channels

    def get_skill_performance(self) -> dict[str, dict[str, Any]]:
        """Get performance per skill."""
        perfs = self.query("learnings", tags=["performance"], limit=500)
        skills: dict[str, dict[str, Any]] = {}
        for p in perfs:
            sid = p["data"].get("skill_id", "unknown")
            if sid not in skills:
                skills[sid] = {"runs": 0, "successes": 0, "revenue": 0}
            skills[sid]["runs"] += 1
            if p["data"].get("success"):
                skills[sid]["successes"] += 1
                skills[sid]["revenue"] += p["data"].get("revenue", 0)
        for sid in skills:
            skills[sid]["success_rate"] = round(
                skills[sid]["successes"] / max(skills[sid]["runs"], 1), 2
            )
        return skills
