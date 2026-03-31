"""
NemoClaw Execution Engine — Failure Recovery Service (E-9)

Handles skill/bridge failures with: retry → fallback → escalate → log.
Prevents silent failures. System self-heals.

NEW FILE: command-center/backend/app/services/failure_recovery_service.py
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("cc.recovery")

# ── FALLBACK MAP ──────────────────────────────────────────────────
# If skill X fails, try skill Y instead.

FALLBACK_MAP: dict[str, str] = {
    "out-02-email-executor": "out-07-whatsapp-message-composer",  # email fails → try WhatsApp
    "cnt-09-social-posting-executor": "cnt-08-cross-channel-distributor",  # post fails → queue for later
    "rev-01-autonomous-sales-closer": "out-01-multi-touch-sequence-builder",  # closer fails → restart sequence
    "int-01-comment-signal-scraper": "rev-17-demand-signal-miner",  # scraper fails → try miner
    "rev-09-payment-execution-engine": "biz-03-invoice-generator",  # payment fails → generate invoice manually
}

# ── ESCALATION MAP ──────────────────────────────────────────────
# If all retries + fallback fail, escalate to this agent.

ESCALATION_MAP: dict[str, str] = {
    "sales_outreach_lead": "growth_revenue_lead",
    "marketing_campaigns_lead": "narrative_content_lead",
    "client_success_lead": "executive_operator",
    "growth_revenue_lead": "executive_operator",
    "operations_lead": "executive_operator",
}


class FailureRecord:
    """Record of a failure event."""

    def __init__(self, skill_id: str, error: str, agent: str = ""):
        self.skill_id = skill_id
        self.error = error
        self.agent = agent
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.retries: int = 0
        self.fallback_tried: str | None = None
        self.escalated_to: str | None = None
        self.resolved: bool = False
        self.resolution: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "error": self.error,
            "agent": self.agent,
            "timestamp": self.timestamp,
            "retries": self.retries,
            "fallback_tried": self.fallback_tried,
            "escalated_to": self.escalated_to,
            "resolved": self.resolved,
            "resolution": self.resolution,
        }


class FailureRecoveryService:
    """
    Handles failures with a 4-step recovery process:
    1. Retry (up to 2 times with backoff)
    2. Fallback to alternative skill
    3. Escalate to different agent
    4. Log pattern for learning

    Integrates with GlobalState for pattern detection.
    """

    MAX_RETRIES = 2
    BACKOFF_SECONDS = [2, 5]  # seconds between retries

    def __init__(self, global_state=None):
        self.global_state = global_state
        self._failures: list[FailureRecord] = []
        self._failure_patterns: dict[str, int] = {}  # skill_id → failure count
        self._persist_path = Path.home() / ".nemoclaw" / "failure-log.json"
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        self._load()
        logger.info("FailureRecoveryService initialized (%d records)", len(self._failures))

    def _load(self) -> None:
        if self._persist_path.exists():
            try:
                data = json.loads(self._persist_path.read_text())
                self._failure_patterns = data.get("patterns", {})
            except Exception:
                pass

    def _save(self) -> None:
        try:
            data = {
                "failures": [f.to_dict() for f in self._failures[-200:]],
                "patterns": self._failure_patterns,
            }
            self._persist_path.write_text(json.dumps(data, indent=2, default=str))
        except Exception:
            pass

    async def handle_failure(
        self,
        skill_id: str,
        error: str,
        agent: str = "",
        execute_fn=None,
        inputs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Full recovery flow: retry → fallback → escalate → log.

        Args:
            skill_id: Failed skill
            error: Error message
            agent: Agent that was running the skill
            execute_fn: async function(skill_id, inputs) → result (for retry/fallback)
            inputs: Original inputs for retry
        """
        record = FailureRecord(skill_id, error, agent)
        self._failure_patterns[skill_id] = self._failure_patterns.get(skill_id, 0) + 1

        # Step 1: Retry
        if execute_fn and inputs:
            for attempt in range(self.MAX_RETRIES):
                record.retries = attempt + 1
                logger.info("Retry %d/%d for %s", attempt + 1, self.MAX_RETRIES, skill_id)
                import asyncio
                await asyncio.sleep(self.BACKOFF_SECONDS[min(attempt, len(self.BACKOFF_SECONDS) - 1)])
                try:
                    result = await execute_fn(skill_id, inputs)
                    if result.get("success"):
                        record.resolved = True
                        record.resolution = f"Retry {attempt + 1} succeeded"
                        self._record(record)
                        return {"action": "retry_success", "attempt": attempt + 1, "result": result}
                except Exception as e:
                    logger.warning("Retry %d failed: %s", attempt + 1, e)

        # Step 2: Fallback
        fallback = FALLBACK_MAP.get(skill_id)
        if fallback and execute_fn and inputs:
            logger.info("Trying fallback: %s → %s", skill_id, fallback)
            record.fallback_tried = fallback
            try:
                result = await execute_fn(fallback, inputs)
                if result.get("success"):
                    record.resolved = True
                    record.resolution = f"Fallback to {fallback} succeeded"
                    self._record(record)
                    return {"action": "fallback_success", "fallback_skill": fallback, "result": result}
            except Exception as e:
                logger.warning("Fallback %s failed: %s", fallback, e)

        # Step 3: Escalate
        escalate_to = ESCALATION_MAP.get(agent, "executive_operator")
        record.escalated_to = escalate_to
        logger.warning("Escalating %s failure to %s", skill_id, escalate_to)

        # Step 4: Log pattern
        self._record(record)

        # Record in global state if available
        if self.global_state:
            self.global_state.add("learnings", f"failure-{skill_id}-{int(time.time())}", {
                "skill_id": skill_id,
                "error": error[:500],
                "retries": record.retries,
                "fallback": fallback,
                "escalated_to": escalate_to,
                "pattern_count": self._failure_patterns.get(skill_id, 0),
            }, agent=agent, tags=["failure", skill_id])

        return {
            "action": "escalated",
            "escalated_to": escalate_to,
            "retries_attempted": record.retries,
            "fallback_tried": record.fallback_tried,
            "pattern_count": self._failure_patterns.get(skill_id, 0),
        }

    def get_failure_patterns(self) -> dict[str, int]:
        """Get skills with repeated failures (potential systemic issues)."""
        return dict(sorted(self._failure_patterns.items(), key=lambda x: x[1], reverse=True))

    def get_chronic_failures(self, threshold: int = 3) -> list[str]:
        """Get skills that fail chronically (> threshold times)."""
        return [s for s, c in self._failure_patterns.items() if c >= threshold]

    def _record(self, record: FailureRecord) -> None:
        self._failures.append(record)
        if len(self._failures) > 500:
            self._failures = self._failures[-500:]
        self._save()

    def get_stats(self) -> dict[str, Any]:
        return {
            "total_failures": len(self._failures),
            "patterns": self._failure_patterns,
            "chronic_failures": self.get_chronic_failures(),
            "fallback_map_size": len(FALLBACK_MAP),
            "escalation_map_size": len(ESCALATION_MAP),
        }
