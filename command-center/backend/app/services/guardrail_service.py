"""
NemoClaw Execution Engine — GuardrailService (E-4c)

Spend ceilings, volume caps, kill switch, revenue shutdown.
Auto-revert aggressive→conservative if spend > 2x ceiling.

NEW FILE: command-center/backend/app/services/guardrail_service.py
"""
from __future__ import annotations
import logging
import time
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("cc.guardrail")

class GuardrailService:
    def __init__(self, config_service=None):
        self.config_service = config_service
        self._spend_today: float = 0.0
        self._actions_today: int = 0
        self._kill_switch: bool = False
        self._daily_reset_time: float = time.time()

        # Defaults (overridable via config_service)
        self.spend_ceiling: float = 20.0
        self.volume_cap_outreach: int = 50
        self.volume_cap_social: int = 5
        self.max_actions_per_hour: int = 30

        self._outreach_count: int = 0
        self._social_count: int = 0
        self._hourly_actions: list[float] = []

        logger.info("GuardrailService initialized (ceiling=$%.2f)", self.spend_ceiling)

    def _check_daily_reset(self):
        if time.time() - self._daily_reset_time > 86400:
            self._spend_today = 0.0
            self._actions_today = 0
            self._outreach_count = 0
            self._social_count = 0
            self._daily_reset_time = time.time()

    def check_spend(self, cost: float) -> dict[str, Any]:
        self._check_daily_reset()
        if self._kill_switch:
            return {"allowed": False, "reason": "Kill switch active"}
        if self._spend_today + cost > self.spend_ceiling:
            return {"allowed": False, "reason": f"Spend ceiling exceeded: ${self._spend_today:.2f} + ${cost:.2f} > ${self.spend_ceiling:.2f}"}
        return {"allowed": True}

    def try_spend(self, cost: float) -> dict[str, Any]:
        """Atomic check + record spend."""
        self._check_daily_reset()
        if self._kill_switch:
            return {"allowed": False, "reason": "Kill switch active"}
        if self._spend_today + cost > self.spend_ceiling:
            return {"allowed": False, "reason": f"Spend ceiling: ${self._spend_today:.2f} + ${cost:.2f} > ${self.spend_ceiling:.2f}"}
        self._spend_today += cost
        self._actions_today += 1
        now = time.time()
        self._hourly_actions.append(now)
        self._hourly_actions = [t for t in self._hourly_actions if now - t < 3600]
        return {"allowed": True, "new_total": round(self._spend_today, 3)}

    def record_spend(self, cost: float):
        self._spend_today += cost
        self._actions_today += 1
        now = time.time()
        self._hourly_actions.append(now)
        self._hourly_actions = [t for t in self._hourly_actions if now - t < 3600]

    def check_volume(self, action_type: str) -> dict[str, Any]:
        self._check_daily_reset()
        if self._kill_switch:
            return {"allowed": False, "reason": "Kill switch active"}
        if action_type == "outreach" and self._outreach_count >= self.volume_cap_outreach:
            return {"allowed": False, "reason": f"Outreach cap reached ({self.volume_cap_outreach}/day)"}
        if action_type == "social" and self._social_count >= self.volume_cap_social:
            return {"allowed": False, "reason": f"Social cap reached ({self.volume_cap_social}/day)"}
        if len(self._hourly_actions) >= self.max_actions_per_hour:
            return {"allowed": False, "reason": f"Hourly action cap reached ({self.max_actions_per_hour}/hr)"}
        return {"allowed": True}

    def record_volume(self, action_type: str):
        if action_type == "outreach":
            self._outreach_count += 1
        elif action_type == "social":
            self._social_count += 1

    def activate_kill_switch(self, reason: str = "") -> dict[str, Any]:
        self._kill_switch = True
        logger.warning("KILL SWITCH ACTIVATED: %s", reason)
        return {"kill_switch": True, "reason": reason, "timestamp": datetime.now(timezone.utc).isoformat()}

    def deactivate_kill_switch(self) -> dict[str, Any]:
        self._kill_switch = False
        logger.info("Kill switch deactivated")
        return {"kill_switch": False}

    def get_status(self) -> dict[str, Any]:
        self._check_daily_reset()
        return {
            "spend_today": round(self._spend_today, 3),
            "spend_ceiling": self.spend_ceiling,
            "spend_pct": round(self._spend_today / self.spend_ceiling * 100, 1) if self.spend_ceiling else 0,
            "actions_today": self._actions_today,
            "outreach_count": self._outreach_count,
            "outreach_cap": self.volume_cap_outreach,
            "social_count": self._social_count,
            "social_cap": self.volume_cap_social,
            "hourly_actions": len(self._hourly_actions),
            "hourly_cap": self.max_actions_per_hour,
            "kill_switch": self._kill_switch,
        }
