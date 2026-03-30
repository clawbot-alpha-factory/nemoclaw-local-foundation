"""
NemoClaw Execution Engine — DebateService (E-4b)

Structured debate protocol (#31):
  Round 1: Both present position + evidence
  Round 2: Challenge + counter-evidence
  Round 3: Compromise or escalate
  Decision logged with evidence trail.

NEW FILE: command-center/backend/app/services/debate_service.py
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("cc.debate")


class DebateStatus:
    OPEN = "open"
    ROUND_1 = "round_1_present"
    ROUND_2 = "round_2_challenge"
    ROUND_3 = "round_3_resolve"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


class Debate:
    """A structured debate between two agents."""

    def __init__(self, topic: str, agent_a: str, agent_b: str, trace_id: str = ""):
        self.debate_id = str(uuid.uuid4())
        self.topic = topic
        self.agent_a = agent_a
        self.agent_b = agent_b
        self.trace_id = trace_id
        self.status = DebateStatus.OPEN
        self.created_at = datetime.now(timezone.utc).isoformat()

        self.rounds: list[dict[str, Any]] = []
        self.resolution: dict[str, Any] | None = None

    def add_round(self, agent_id: str, position: str, evidence: str = "") -> dict[str, Any]:
        """Add a round entry."""
        entry = {
            "round": len(self.rounds) + 1,
            "agent_id": agent_id,
            "position": position,
            "evidence": evidence,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.rounds.append(entry)

        # Auto-advance status
        if len(self.rounds) <= 2:
            self.status = DebateStatus.ROUND_1
        elif len(self.rounds) <= 4:
            self.status = DebateStatus.ROUND_2
        else:
            self.status = DebateStatus.ROUND_3

        return entry

    def resolve(self, resolution: str, decided_by: str, resolution_type: str = "compromise"):
        """Resolve the debate."""
        self.resolution = {
            "resolution": resolution,
            "decided_by": decided_by,
            "type": resolution_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.status = DebateStatus.RESOLVED if resolution_type != "escalate" else DebateStatus.ESCALATED

    def to_dict(self) -> dict[str, Any]:
        return {
            "debate_id": self.debate_id,
            "topic": self.topic,
            "agent_a": self.agent_a,
            "agent_b": self.agent_b,
            "trace_id": self.trace_id,
            "status": self.status,
            "created_at": self.created_at,
            "rounds": self.rounds,
            "resolution": self.resolution,
        }


class DebateService:
    """Manages structured debates between agents."""

    def __init__(self):
        self.debates: dict[str, Debate] = {}
        logger.info("DebateService initialized")

    def start_debate(
        self, topic: str, agent_a: str, agent_b: str, trace_id: str = ""
    ) -> Debate:
        debate = Debate(topic=topic, agent_a=agent_a, agent_b=agent_b, trace_id=trace_id)
        self.debates[debate.debate_id] = debate
        logger.info("Debate started: %s vs %s on '%s'", agent_a, agent_b, topic[:50])
        return debate

    def add_position(
        self, debate_id: str, agent_id: str, position: str, evidence: str = ""
    ) -> dict[str, Any] | None:
        debate = self.debates.get(debate_id)
        if not debate:
            return None
        return debate.add_round(agent_id, position, evidence)

    def resolve_debate(
        self, debate_id: str, resolution: str, decided_by: str, resolution_type: str = "compromise"
    ) -> dict[str, Any] | None:
        debate = self.debates.get(debate_id)
        if not debate:
            return None

        # Authority check: decided_by must have authority over both debaters
        from app.services.agent_protocol_service import AGENT_LEVELS
        decider_level = AGENT_LEVELS.get(decided_by, 99)
        agent_a_level = AGENT_LEVELS.get(debate.agent_a, 99)
        agent_b_level = AGENT_LEVELS.get(debate.agent_b, 99)
        min_debater_level = min(agent_a_level, agent_b_level)

        if decider_level > min_debater_level:
            return {
                "error": f"Agent {decided_by} (L{decider_level}) lacks authority to resolve debate between "
                         f"{debate.agent_a} (L{agent_a_level}) and {debate.agent_b} (L{agent_b_level})",
            }

        debate.resolve(resolution, decided_by, resolution_type)
        logger.info("Debate %s resolved by %s: %s", debate_id[:8], decided_by, resolution_type)
        return debate.to_dict()

    def get_debate(self, debate_id: str) -> dict[str, Any] | None:
        debate = self.debates.get(debate_id)
        return debate.to_dict() if debate else None

    def list_debates(self) -> list[dict[str, Any]]:
        return [d.to_dict() for d in self.debates.values()]
