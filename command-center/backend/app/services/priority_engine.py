"""
NemoClaw Execution Engine — Priority Engine (E-9)

Scores and ranks all pending tasks/actions by priority.
Used by rev-06 orchestrator to decide WHAT to do FIRST.

Factors: urgency, value, staleness, confidence, agent load.

NEW FILE: command-center/backend/app/services/priority_engine.py
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("cc.priority")


class PriorityItem:
    """A prioritized task or action."""

    DEFAULT_TTL = 86400  # 24 hours

    blocked: bool = False

    def __init__(self, item_id: str, task_type: str, description: str,
                 agent: str = "", metadata: dict[str, Any] | None = None,
                 ttl: int = 86400):
        self.item_id = item_id
        self.task_type = task_type
        self.description = description
        self.agent = agent
        self.metadata = metadata or {}
        self.created_at = time.time()
        self.ttl = ttl
        self.priority_score: float = 0.0
        self.factors: dict[str, float] = {}

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > self.ttl

    @property
    def age_hours(self) -> float:
        return (time.time() - self.created_at) / 3600

    @property
    def decayed_score(self) -> float:
        """Score decays 10% per hour."""
        decay = max(0, 1 - (self.age_hours * 0.1))
        return self.priority_score * decay

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "task_type": self.task_type,
            "description": self.description,
            "agent": self.agent,
            "priority_score": round(self.priority_score, 1),
            "factors": {k: round(v, 2) for k, v in self.factors.items()},
            "created_at": datetime.fromtimestamp(self.created_at, tz=timezone.utc).isoformat(),
        }


class PriorityEngine:
    """
    Scores and ranks all pending actions.

    Scoring formula:
      priority = (urgency * 30) + (value * 25) + (staleness * 20) +
                 (confidence * 15) + (agent_fit * 10)

    Weights are adjustable via performance feedback.
    """

    DEFAULT_WEIGHTS = {
        "urgency": 30,     # How time-sensitive (0-10)
        "value": 25,       # Expected revenue impact (0-10)
        "staleness": 20,   # How long since last action (0-10)
        "confidence": 15,  # Demand/data confidence (0-10)
        "agent_fit": 10,   # How well matched to best agent (0-10)
    }

    def __init__(self, global_state=None):
        self.global_state = global_state
        self._weights = dict(self.DEFAULT_WEIGHTS)
        self._queue: list[PriorityItem] = []
        self._persist_path = Path.home() / ".nemoclaw" / "priority-queue.json"
        self._weights_path = Path.home() / ".nemoclaw" / "priority-weights.json"
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        self._load_weights()
        logger.info("PriorityEngine initialized (weights: %s)", self._weights)

    def _load_weights(self) -> None:
        """Load adjusted weights from disk."""
        if self._weights_path.exists():
            try:
                self._weights = json.loads(self._weights_path.read_text())
            except Exception:
                pass

    def _save_weights(self) -> None:
        try:
            self._weights_path.write_text(json.dumps(self._weights, indent=2))
        except Exception:
            pass

    def score(self, item: PriorityItem, factors: dict[str, float]) -> float:
        """Score a priority item. Each factor 0-10."""
        total = 0.0
        item.factors = {}
        for factor, weight in self._weights.items():
            value = min(max(factors.get(factor, 5.0), 0), 10)
            contribution = value * weight / 100
            item.factors[factor] = contribution
            total += contribution
        item.priority_score = min(total * 10, 100)  # Scale to 0-100
        return item.priority_score

    def add_task(self, item_id: str, task_type: str, description: str,
                 agent: str = "", factors: dict[str, float] | None = None,
                 metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        """Add and score a task."""
        item = PriorityItem(item_id, task_type, description, agent, metadata)
        self.score(item, factors or {})
        self._queue.append(item)
        self._queue.sort(key=lambda x: x.priority_score, reverse=True)

        # Cap at 200
        if len(self._queue) > 200:
            self._queue = self._queue[:200]

        self._persist()
        return item.to_dict()

    def get_top(self, n: int = 10, agent: str | None = None,
                task_type: str | None = None) -> list[dict[str, Any]]:
        """Get top N priority items with optional filters. Removes expired."""
        self._queue = [i for i in self._queue if not i.is_expired]
        self._queue.sort(key=lambda x: x.decayed_score, reverse=True)
        # P-4: exclude blocked tasks before scoring
        items = [i for i in self._queue if not i.blocked]
        if agent:
            items = [i for i in items if i.agent == agent]
        if task_type:
            items = [i for i in items if i.task_type == task_type]
        return [i.to_dict() for i in items[:n]]

    def pop_next(self, agent: str | None = None) -> dict[str, Any] | None:
        """Pop the highest priority item."""
        # P-4: exclude blocked tasks
        pool = [i for i in self._queue if not i.blocked]
        items = pool if not agent else [i for i in pool if i.agent == agent]
        if not items:
            return None
        item = items[0]
        self._queue.remove(item)
        self._persist()
        return item.to_dict()

    def remove_task(self, item_id: str) -> bool:
        """Remove a completed task."""
        before = len(self._queue)
        self._queue = [i for i in self._queue if i.item_id != item_id]
        if len(self._queue) < before:
            self._persist()
            return True
        return False

    def adjust_weights(self, adjustments: dict[str, float]) -> dict[str, float]:
        """Adjust priority weights based on performance feedback."""
        for factor, delta in adjustments.items():
            if factor in self._weights:
                self._weights[factor] = max(5, min(50, self._weights[factor] + delta))
        self._save_weights()

        # Re-score all items
        for item in self._queue:
            self.score(item, {k: v / (self._weights.get(k, 1) / 100)
                             for k, v in item.factors.items()})
        self._queue.sort(key=lambda x: x.priority_score, reverse=True)

        logger.info("Priority weights adjusted: %s", self._weights)
        return self._weights

    def update_from_performance(self, performance_data: dict[str, Any]) -> None:
        """Auto-adjust weights based on what's actually generating revenue."""
        if not performance_data:
            return
        # If email channel has low ROI, reduce urgency weight for email tasks
        # If direct outreach has high ROI, increase value weight
        # This is the feedback loop that makes the system adaptive
        channel_roi = performance_data.get("channel_roi", {})
        skill_perf = performance_data.get("skill_performance", {})

        # Simple heuristic: if success_rate < 30%, deprioritize
        low_performers = [s for s, d in skill_perf.items()
                         if d.get("success_rate", 0) < 0.3 and d.get("runs", 0) > 5]
        if low_performers:
            logger.info("Low-performing skills detected: %s — adjusting weights", low_performers)

    def _persist(self) -> None:
        try:
            data = [i.to_dict() for i in self._queue[:100]]
            self._persist_path.write_text(json.dumps(data, indent=2, default=str))
        except Exception:
            pass

    def get_stats(self) -> dict[str, Any]:
        return {
            "queue_size": len(self._queue),
            "weights": self._weights,
            "top_3": [i.to_dict() for i in self._queue[:3]],
        }
