"""
MessageStore — Append-Only Event Log (CC-3)

In-memory message store with lane management. Designed as an append-only
event log — messages are never edited or deleted (full audit trail).

Optional file-backing persists state to JSON on disk.

NEW FILE: command-center/backend/app/message_store.py
"""

from __future__ import annotations

import json
import logging
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.domain.comms_models import (
    Lane,
    LaneType,
    Message,
    MessageType,
    SenderType,
)

logger = logging.getLogger("cc.message_store")

# Max messages kept in context window per lane for LLM calls
DEFAULT_CONTEXT_WINDOW = 20
# Max total messages per lane before oldest are archived from memory
MAX_MESSAGES_PER_LANE = 500


class MessageStore:
    """Append-only in-memory message store with lane indexing."""

    def __init__(self, persist_path: Optional[str] = None) -> None:
        self._messages: dict[str, Message] = {}  # id -> Message
        self._lane_index: dict[str, list[str]] = defaultdict(list)  # lane_id -> [msg ids]
        self._lanes: dict[str, Lane] = {}  # lane_id -> Lane
        self._persist_path = Path(persist_path) if persist_path else None

        if self._persist_path and self._persist_path.exists():
            self._load_from_disk()

    # ------------------------------------------------------------------
    # Lane Management
    # ------------------------------------------------------------------

    def create_lane(
        self,
        lane_id: str,
        name: str,
        lane_type: LaneType,
        participants: list[str] | None = None,
        avatar: str | None = None,
    ) -> Lane:
        """Create a new lane. Idempotent — returns existing if ID exists (updates name/avatar)."""
        if lane_id in self._lanes:
            # Update name and avatar if they changed (e.g. character names added)
            existing = self._lanes[lane_id]
            if name and name != existing.name:
                existing.name = name
            if avatar and avatar != existing.avatar:
                existing.avatar = avatar
            return existing

        lane = Lane(
            id=lane_id,
            name=name,
            lane_type=lane_type,
            participants=participants or [],
            avatar=avatar,
            created_at=datetime.now(timezone.utc),
        )
        self._lanes[lane_id] = lane
        logger.info("Lane created: %s (%s)", lane_id, lane_type.value)
        return lane

    def get_lanes(self) -> list[Lane]:
        """Return all lanes sorted by last_message timestamp (most recent first)."""
        lanes = list(self._lanes.values())
        lanes.sort(
            key=lambda l: (
                l.last_message.timestamp if l.last_message else l.created_at
            ),
            reverse=True,
        )
        return lanes

    def get_lane(self, lane_id: str) -> Lane | None:
        """Get a specific lane by ID."""
        return self._lanes.get(lane_id)

    # ------------------------------------------------------------------
    # Message Operations (Append-Only)
    # ------------------------------------------------------------------

    def add_message(
        self,
        lane_id: str,
        sender_id: str,
        sender_name: str,
        sender_type: SenderType,
        content: str,
        message_type: MessageType = MessageType.CHAT,
        reply_to: str | None = None,
        metadata: dict | None = None,
        message_id: str | None = None,
    ) -> Message | None:
        """Append a message to a lane. Returns None if lane doesn't exist."""
        if lane_id not in self._lanes:
            logger.warning("Attempted to add message to unknown lane: %s", lane_id)
            return None

        msg = Message(
            id=message_id or str(uuid.uuid4()),
            lane_id=lane_id,
            message_type=message_type,
            sender_id=sender_id,
            sender_name=sender_name,
            sender_type=sender_type,
            content=content,
            reply_to=reply_to,
            metadata=metadata or {},
            timestamp=datetime.now(timezone.utc),
        )

        self._messages[msg.id] = msg
        self._lane_index[lane_id].append(msg.id)

        # Update lane's last_message + unread count
        lane = self._lanes[lane_id]
        lane.last_message = msg
        if sender_type != SenderType.USER:
            lane.unread_count += 1

        # Trim in-memory if lane exceeds cap
        if len(self._lane_index[lane_id]) > MAX_MESSAGES_PER_LANE:
            oldest_id = self._lane_index[lane_id].pop(0)
            self._messages.pop(oldest_id, None)

        self._persist_to_disk()
        return msg

    def get_messages(
        self,
        lane_id: str,
        limit: int = 50,
        before: datetime | None = None,
    ) -> list[Message]:
        """Get messages for a lane, newest last. Supports pagination via `before`."""
        msg_ids = self._lane_index.get(lane_id, [])
        messages = [self._messages[mid] for mid in msg_ids if mid in self._messages]

        if before:
            messages = [m for m in messages if m.timestamp < before]

        # Return last N, ordered oldest-first (chat order)
        return messages[-limit:]

    def get_context_messages(
        self, lane_id: str, limit: int = DEFAULT_CONTEXT_WINDOW
    ) -> list[Message]:
        """Get recent messages for LLM context window."""
        return self.get_messages(lane_id, limit=limit)

    def mark_lane_read(self, lane_id: str) -> None:
        """Reset unread count for a lane."""
        if lane_id in self._lanes:
            self._lanes[lane_id].unread_count = 0

    def get_message(self, message_id: str) -> Message | None:
        """Get a single message by ID."""
        return self._messages.get(message_id)

    # ------------------------------------------------------------------
    # System Messages
    # ------------------------------------------------------------------

    def add_system_message(
        self, lane_id: str, content: str, metadata: dict | None = None
    ) -> Message | None:
        """Add a system-generated message to a lane."""
        return self.add_message(
            lane_id=lane_id,
            sender_id="system",
            sender_name="System",
            sender_type=SenderType.SYSTEM,
            content=content,
            message_type=MessageType.SYSTEM,
            metadata=metadata,
        )

    # ------------------------------------------------------------------
    # Persistence (Optional)
    # ------------------------------------------------------------------

    def _persist_to_disk(self) -> None:
        """Save current state to JSON file if persist_path is set."""
        if not self._persist_path:
            return
        try:
            data = {
                "lanes": {lid: l.model_dump(mode="json") for lid, l in self._lanes.items()},
                "messages": {
                    mid: m.model_dump(mode="json") for mid, m in self._messages.items()
                },
                "lane_index": dict(self._lane_index),
            }
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            self._persist_path.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.error("Failed to persist message store: %s", e)

    def _load_from_disk(self) -> None:
        """Load state from JSON file."""
        try:
            raw = json.loads(self._persist_path.read_text())
            for lid, lane_data in raw.get("lanes", {}).items():
                self._lanes[lid] = Lane.model_validate(lane_data)
            for mid, msg_data in raw.get("messages", {}).items():
                self._messages[mid] = Message.model_validate(msg_data)
            self._lane_index = defaultdict(list, raw.get("lane_index", {}))
            logger.info(
                "Loaded message store: %d lanes, %d messages",
                len(self._lanes),
                len(self._messages),
            )
        except Exception as e:
            logger.error("Failed to load message store from disk: %s", e)

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        """Return store statistics."""
        return {
            "total_lanes": len(self._lanes),
            "total_messages": len(self._messages),
            "messages_per_lane": {
                lid: len(mids) for lid, mids in self._lane_index.items()
            },
        }
