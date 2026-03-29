"""
Communications Models (CC-3)

Data models for the messaging system: messages, lanes, and enums.
Separate from models.py to keep CC-1 SystemState models untouched.

NEW FILE: command-center/backend/app/comms_models.py
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field


# ------------------------------------------------------------------
# Enums
# ------------------------------------------------------------------


class MessageType(str, enum.Enum):
    CHAT = "chat"
    DECISION = "decision"
    ALERT = "alert"
    TASK = "task"
    APPROVAL = "approval"
    SYSTEM = "system"


class LaneType(str, enum.Enum):
    DM = "dm"
    GROUP = "group"
    BROADCAST = "broadcast"
    SYSTEM = "system"


class SenderType(str, enum.Enum):
    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"


# ------------------------------------------------------------------
# Core Models
# ------------------------------------------------------------------


class Message(BaseModel):
    id: str = Field(..., description="UUID for the message")
    lane_id: str = Field(..., description="Lane this message belongs to")
    message_type: MessageType = Field(default=MessageType.CHAT)
    sender_id: str = Field(..., description="User ID or agent ID")
    sender_name: str = Field(..., description="Display name")
    sender_type: SenderType = Field(default=SenderType.USER)
    content: str = Field(..., description="Message body")
    reply_to: Optional[str] = Field(
        default=None, description="ID of message being replied to"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Extensible metadata for outcome linking, task refs, etc.",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def to_ws_payload(self) -> dict[str, Any]:
        """Serialize for WebSocket broadcast."""
        return self.model_dump(mode="json")


class Lane(BaseModel):
    id: str = Field(..., description="Unique lane identifier")
    name: str = Field(..., description="Display name")
    lane_type: LaneType = Field(default=LaneType.DM)
    participants: list[str] = Field(
        default_factory=list,
        description="Agent IDs participating in this lane",
    )
    avatar: Optional[str] = Field(
        default=None, description="Emoji or icon identifier"
    )
    last_message: Optional[Message] = Field(default=None)
    unread_count: int = Field(default=0)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ------------------------------------------------------------------
# Request / Response Models
# ------------------------------------------------------------------


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=4000)
    message_type: MessageType = Field(default=MessageType.CHAT)
    reply_to: Optional[str] = Field(default=None)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LaneListResponse(BaseModel):
    lanes: list[Lane]
    total: int


class MessageListResponse(BaseModel):
    messages: list[Message]
    lane_id: str
    total: int
    has_more: bool
