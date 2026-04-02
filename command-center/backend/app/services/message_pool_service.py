"""
Shared Message Pool (MetaGPT pattern) — publish/subscribe for agent communication.

Instead of agents sending DMs to specific peers, they publish to a shared pool.
Each agent subscribes to message types relevant to their role.
"""

import json
import logging
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("nemoclaw.message_pool")

MESSAGE_TYPES = [
    "completion", "blocker", "idea", "challenge", "win",
    "request_help", "discovery", "planning", "decision",
]

# Default subscriptions per agent role
DEFAULT_SUBSCRIPTIONS = {
    "executive_operator": MESSAGE_TYPES,  # sees everything
    "strategy_lead": ["idea", "discovery", "planning", "decision", "challenge"],
    "operations_lead": ["blocker", "completion", "planning"],
    "product_architect": ["idea", "planning", "decision", "blocker"],
    "growth_revenue_lead": ["win", "idea", "discovery", "decision"],
    "narrative_content_lead": ["idea", "discovery", "win"],
    "engineering_lead": ["blocker", "completion", "planning"],
    "sales_outreach_lead": ["win", "completion", "request_help"],
    "marketing_campaigns_lead": ["win", "idea", "discovery"],
    "client_success_lead": ["blocker", "completion", "request_help"],
    "social_media_lead": ["win", "idea", "discovery", "challenge"],
}

POOL_LOG = Path.home() / ".nemoclaw" / "logs" / "message-pool.jsonl"


class MessagePoolService:
    """Shared message pool with pub/sub for agent communication."""

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._pool: deque = deque(maxlen=max_size)
        self._subscriptions: dict[str, list[str]] = dict(DEFAULT_SUBSCRIPTIONS)
        POOL_LOG.parent.mkdir(parents=True, exist_ok=True)
        logger.info("MessagePoolService initialized")

    def publish(self, agent_id: str, message_type: str, content: str, tags: Optional[list] = None):
        """Publish a message to the shared pool."""
        if message_type not in MESSAGE_TYPES:
            logger.warning(f"Unknown message type: {message_type}")
            return

        msg = {
            "id": str(uuid.uuid4())[:12],
            "agent_id": agent_id,
            "type": message_type,
            "content": content,
            "tags": tags or [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "ts": time.time(),
        }
        self._pool.append(msg)

        # Persist to JSONL
        try:
            with open(POOL_LOG, "a") as f:
                f.write(json.dumps(msg) + "\n")
        except Exception:
            pass

    def subscribe(self, agent_id: str, message_types: list[str]):
        """Set custom subscriptions for an agent."""
        self._subscriptions[agent_id] = message_types

    def get_messages(self, agent_id: str, since: Optional[float] = None, limit: int = 50) -> list:
        """Get messages matching an agent's subscriptions."""
        subs = self._subscriptions.get(agent_id, MESSAGE_TYPES)
        cutoff = since or 0

        results = []
        for msg in reversed(self._pool):
            if msg["ts"] <= cutoff:
                break
            if msg["type"] in subs and msg["agent_id"] != agent_id:
                results.append(msg)
            if len(results) >= limit:
                break

        return list(reversed(results))

    def get_all_recent(self, limit: int = 100) -> list:
        """Get all recent messages (for all-hands view)."""
        return list(self._pool)[-limit:]

    def get_stats(self) -> dict:
        """Pool statistics."""
        type_counts = {}
        for msg in self._pool:
            t = msg["type"]
            type_counts[t] = type_counts.get(t, 0) + 1

        return {
            "total_messages": len(self._pool),
            "max_size": self.max_size,
            "subscribers": len(self._subscriptions),
            "by_type": type_counts,
        }
