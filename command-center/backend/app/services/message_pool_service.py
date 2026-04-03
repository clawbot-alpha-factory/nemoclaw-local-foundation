"""
Shared Message Pool (MetaGPT pattern) — publish/subscribe for agent communication.

Instead of agents sending DMs to specific peers, they publish to a shared pool.
Each agent subscribes to message types relevant to their role.
"""

import hashlib
import json
import logging
import time
import uuid
from collections import defaultdict, deque
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

    # Rate limit: max 10 messages per agent per hour
    RATE_LIMIT_PER_HOUR = 10
    RATE_LIMIT_WINDOW = 3600
    # Dedup: hash last 50 messages
    DEDUP_BUFFER_SIZE = 50

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._pool: deque = deque(maxlen=max_size)
        self._subscriptions: dict[str, list[str]] = dict(DEFAULT_SUBSCRIPTIONS)
        # Rate limiting: agent_id -> list of timestamps
        self._rate_log: dict[str, list[float]] = defaultdict(list)
        # Dedup: recent content hashes
        self._recent_hashes: deque = deque(maxlen=self.DEDUP_BUFFER_SIZE)
        POOL_LOG.parent.mkdir(parents=True, exist_ok=True)
        self._restore_from_disk()
        logger.info("MessagePoolService initialized (restored=%d)", len(self._pool))

    def _restore_from_disk(self) -> None:
        """Load last 100 messages from JSONL log into the pool."""
        try:
            if not POOL_LOG.is_file():
                return
            lines = POOL_LOG.read_text().splitlines()
            for line in lines[-100:]:
                if not line.strip():
                    continue
                try:
                    msg = json.loads(line)
                    self._pool.append(msg)
                    h = hashlib.md5(msg.get("content", "").encode()).hexdigest()
                    self._recent_hashes.append(h)
                except (json.JSONDecodeError, KeyError):
                    continue
        except Exception:
            logger.warning("Failed to restore message pool from disk")

    def _is_rate_limited(self, agent_id: str) -> bool:
        """Check if agent has exceeded 10 messages/hour."""
        now = time.time()
        cutoff = now - self.RATE_LIMIT_WINDOW
        timestamps = self._rate_log[agent_id]
        self._rate_log[agent_id] = [t for t in timestamps if t > cutoff]
        return len(self._rate_log[agent_id]) >= self.RATE_LIMIT_PER_HOUR

    def _is_duplicate(self, content: str) -> bool:
        """Check if content hash is in recent buffer."""
        h = hashlib.md5(content.encode()).hexdigest()
        if h in self._recent_hashes:
            return True
        self._recent_hashes.append(h)
        return False

    def publish(self, agent_id: str, message_type: str, content: str, tags: Optional[list] = None):
        """Publish a message to the shared pool."""
        from app.services.agent_notification_service import VALID_AGENTS
        if agent_id not in VALID_AGENTS:
            logger.warning("Rejected pool message from non-employee: %s", agent_id)
            return
        if message_type not in MESSAGE_TYPES:
            logger.warning(f"Unknown message type: {message_type}")
            return
        if self._is_rate_limited(agent_id):
            logger.warning("Rate limited pool message from %s", agent_id)
            return
        if self._is_duplicate(content):
            logger.debug("Duplicate pool message suppressed from %s", agent_id)
            return

        self._rate_log[agent_id].append(time.time())

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

    def publish_to_channel(
        self,
        agent_id: str,
        message_type: str,
        content: str,
        team_lane_id: str,
        message_store=None,
        tags: Optional[list] = None,
    ):
        """Publish to the shared pool AND post to a team channel."""
        self.publish(agent_id, message_type, content, tags)
        if message_store and team_lane_id:
            try:
                from app.services.agent_notification_service import AGENT_NAMES
                from app.domain.comms_models import SenderType, MessageType as MsgType

                display = AGENT_NAMES.get(agent_id, agent_id)
                message_store.add_message(
                    lane_id=team_lane_id,
                    sender_id=agent_id,
                    sender_name=display,
                    sender_type=SenderType.AGENT,
                    content=content,
                    message_type=MsgType.SYSTEM,
                    metadata={"pool_message": True, "pool_type": message_type},
                )
            except Exception as e:
                logger.warning("publish_to_channel failed for %s: %s", team_lane_id, e)

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
