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
