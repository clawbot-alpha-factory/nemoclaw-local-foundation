"""
Circuit Breaker — Prevents retry storms on broken skills.

States: CLOSED (normal) → OPEN (reject all) → HALF_OPEN (testing recovery)

Usage:
    cb = SkillCircuitBreaker()
    if cb.can_execute_skill("cnt-01"):
        result = execute(...)
        cb.record_skill_result("cnt-01", result.success)
    else:
        # Skill is broken, skip execution
"""

import hashlib
import json
import logging
import time
from typing import Optional

logger = logging.getLogger("nemoclaw.circuit_breaker")


class CircuitBreaker:
    """Single circuit breaker instance."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(self, name: str, failure_threshold: int = 5,
                 recovery_timeout: int = 60, half_open_max: int = 2):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max = half_open_max

        self.state = self.CLOSED
        self.failures = 0
        self.half_open_attempts = 0
        self.last_failure_time = 0.0
        self.last_success_time = 0.0

    def can_execute(self) -> bool:
        if self.state == self.CLOSED:
            return True
        if self.state == self.OPEN:
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = self.HALF_OPEN
                self.half_open_attempts = 0
                logger.info(f"Circuit {self.name}: OPEN → HALF_OPEN (recovery timeout elapsed)")
                return True
            return False
        if self.state == self.HALF_OPEN:
            return self.half_open_attempts < self.half_open_max
        return False

    def record_success(self):
        if self.state == self.HALF_OPEN:
            self.state = self.CLOSED
            self.failures = 0
            logger.info(f"Circuit {self.name}: HALF_OPEN → CLOSED (recovered)")
        self.last_success_time = time.time()
        self.failures = max(0, self.failures - 1)

    def record_failure(self):
        self.failures += 1
        self.last_failure_time = time.time()
        if self.state == self.HALF_OPEN:
            self.half_open_attempts += 1
            if self.half_open_attempts >= self.half_open_max:
                self.state = self.OPEN
                logger.warning(f"Circuit {self.name}: HALF_OPEN → OPEN (still failing)")
        elif self.failures >= self.failure_threshold:
            self.state = self.OPEN
            logger.warning(f"Circuit {self.name}: CLOSED → OPEN ({self.failures} failures)")

    def get_state(self) -> dict:
        return {
            "name": self.name, "state": self.state,
            "failures": self.failures,
            "last_failure": self.last_failure_time,
            "last_success": self.last_success_time,
        }


class SkillCircuitBreaker:
    """Manages circuit breakers per skill_id."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._breakers: dict[str, CircuitBreaker] = {}

    def _get(self, skill_id: str) -> CircuitBreaker:
        if skill_id not in self._breakers:
            self._breakers[skill_id] = CircuitBreaker(
                name=skill_id,
                failure_threshold=self.failure_threshold,
                recovery_timeout=self.recovery_timeout,
            )
        return self._breakers[skill_id]

    def can_execute_skill(self, skill_id: str) -> bool:
        return self._get(skill_id).can_execute()

    def record_skill_result(self, skill_id: str, success: bool):
        breaker = self._get(skill_id)
        if success:
            breaker.record_success()
        else:
            breaker.record_failure()

    def get_all_states(self) -> dict:
        return {sid: b.get_state() for sid, b in self._breakers.items()}

    def get_tripped_skills(self) -> list:
        return [sid for sid, b in self._breakers.items() if b.state == CircuitBreaker.OPEN]

    def get_stats(self) -> dict:
        return {
            "total_tracked": len(self._breakers),
            "open": len(self.get_tripped_skills()),
            "closed": len([b for b in self._breakers.values() if b.state == CircuitBreaker.CLOSED]),
            "half_open": len([b for b in self._breakers.values() if b.state == CircuitBreaker.HALF_OPEN]),
        }


class StepLimitBreaker:
    """Trips when an execution exceeds its allowed step count.

    Tier limits: {1: 10, 2: 25, 3: 50, 4: 100}, default 50.
    """

    DEFAULT_TIER_LIMITS = {1: 10, 2: 25, 3: 50, 4: 100}

    def __init__(self, tier_limits: Optional[dict] = None, default_limit: int = 50):
        self.tier_limits = tier_limits or self.DEFAULT_TIER_LIMITS
        self.default_limit = default_limit
        self._counters: dict[str, int] = {}

    def check(self, execution_id: str, tier: Optional[int] = None) -> tuple[bool, str]:
        """Increment step counter and check limit. Returns (allowed, reason)."""
        self._counters[execution_id] = self._counters.get(execution_id, 0) + 1
        limit = self.tier_limits.get(tier, self.default_limit) if tier else self.default_limit
        count = self._counters[execution_id]
        if count > limit:
            reason = f"Step limit {limit} exceeded ({count} steps) for execution {execution_id[:8]}"
            logger.warning("StepLimitBreaker: %s", reason)
            return False, reason
        return True, ""

    def reset(self, execution_id: str):
        self._counters.pop(execution_id, None)

    def get_state(self) -> dict:
        return {"active_executions": dict(self._counters)}


class CostCeilingBreaker:
    """Trips when cumulative cost for an execution exceeds the ceiling."""

    def __init__(self, max_cost: float = 5.0):
        self.max_cost = max_cost
        self._costs: dict[str, float] = {}

    def add_cost(self, execution_id: str, cost: float):
        self._costs[execution_id] = self._costs.get(execution_id, 0.0) + cost

    def check(self, execution_id: str) -> tuple[bool, str]:
        """Returns (allowed, reason)."""
        current = self._costs.get(execution_id, 0.0)
        if current > self.max_cost:
            reason = f"Cost ceiling ${self.max_cost:.2f} exceeded: ${current:.2f} for execution {execution_id[:8]}"
            logger.warning("CostCeilingBreaker: %s", reason)
            return False, reason
        return True, ""

    def reset(self, execution_id: str):
        self._costs.pop(execution_id, None)

    def get_state(self) -> dict:
        return {"active_executions": {k: f"${v:.4f}" for k, v in self._costs.items()}, "max_cost": self.max_cost}


class RepetitionDetector:
    """Trips after N identical (tool_name, MD5(inputs)) calls within an execution."""

    def __init__(self, max_repeats: int = 3):
        self.max_repeats = max_repeats
        # execution_id -> {hash_key: count}
        self._calls: dict[str, dict[str, int]] = {}

    def record(self, execution_id: str, tool_name: str, inputs_dict: dict) -> tuple[bool, str]:
        """Record a call and check for repetition. Returns (allowed, reason)."""
        inputs_json = json.dumps(inputs_dict, sort_keys=True, default=str)
        inputs_hash = hashlib.md5(inputs_json.encode()).hexdigest()
        key = f"{tool_name}:{inputs_hash}"

        if execution_id not in self._calls:
            self._calls[execution_id] = {}
        self._calls[execution_id][key] = self._calls[execution_id].get(key, 0) + 1
        count = self._calls[execution_id][key]

        if count >= self.max_repeats:
            reason = f"Repetition detected: {tool_name} called {count} times with identical inputs in execution {execution_id[:8]}"
            logger.warning("RepetitionDetector: %s", reason)
            return False, reason
        return True, ""

    def reset(self, execution_id: str):
        self._calls.pop(execution_id, None)

    def get_state(self) -> dict:
        return {
            "active_executions": {
                eid: {k: v for k, v in calls.items()}
                for eid, calls in self._calls.items()
            },
            "max_repeats": self.max_repeats,
        }
