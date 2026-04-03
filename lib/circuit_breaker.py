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
from datetime import datetime, timezone
from pathlib import Path
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

    def record_success(self) -> None:
        if self.state == self.HALF_OPEN:
            self.state = self.CLOSED
            self.failures = 0
            logger.info(f"Circuit {self.name}: HALF_OPEN → CLOSED (recovered)")
        self.last_success_time = time.time()
        self.failures = max(0, self.failures - 1)

    def record_failure(self) -> None:
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

    def record_skill_result(self, skill_id: str, success: bool) -> None:
        breaker = self._get(skill_id)
        if success:
            breaker.record_success()
        else:
            breaker.record_failure()

    def get_all_states(self) -> dict[str, dict]:
        return {sid: b.get_state() for sid, b in self._breakers.items()}

    def get_tripped_skills(self) -> list[str]:
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

    def reset(self, execution_id: str) -> None:
        self._counters.pop(execution_id, None)

    def get_state(self) -> dict:
        return {"active_executions": dict(self._counters)}


class CostCeilingBreaker:
    """Trips when cumulative cost for an execution exceeds the ceiling."""

    def __init__(self, max_cost: float = 5.0):
        self.max_cost = max_cost
        self._costs: dict[str, float] = {}

    def add_cost(self, execution_id: str, cost: float) -> None:
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


class BackendCostBreaker:
    """Per-backend cost/usage breaker for flat-rate and API backends.

    Flat-rate backends (claude_code, codex): tracks session-minutes against
    a monthly limit derived from the subscription.
    API backends: reads cumulative spend from provider-usage.jsonl and
    compares against budget-config.yaml limits.

    Usage:
        breaker = BackendCostBreaker("claude_code", monthly_limit=43200, tracking="session_minutes")
        breaker.record_session(minutes=15.5)
        allowed, reason, pct = breaker.check()
    """

    LOG_DIR = Path.home() / ".nemoclaw" / "logs"
    BACKEND_LOG = "backend-usage.jsonl"
    PROVIDER_LOG = "provider-usage.jsonl"

    def __init__(
        self,
        backend_name: str,
        monthly_limit: float,
        warn_pct: float = 0.8,
        tracking: str = "session_minutes",
        log_path: Optional[Path] = None,
    ):
        self.backend_name = backend_name
        self.monthly_limit = monthly_limit
        self.warn_pct = warn_pct
        self.tracking = tracking  # "session_minutes" | "budget_config"
        self._log_path = log_path or (self.LOG_DIR / self.BACKEND_LOG)
        self._log_path.parent.mkdir(parents=True, exist_ok=True)

        # In-memory accumulator for the current month
        self._current_month = self._month_key()
        self._accumulated = self._load_current_month()

    # ── Public API ────────────────────────────────────────────────────

    def record_session(self, minutes: float) -> None:
        """Record session-minutes for flat-rate backends."""
        if self.tracking != "session_minutes":
            return
        # Roll over if month changed
        month = self._month_key()
        if month != self._current_month:
            self._current_month = month
            self._accumulated = 0.0
        self._accumulated += minutes
        self._persist(minutes)

    def check(self) -> tuple[bool, str, float]:
        """Check backend utilization. Returns (allowed, reason, utilization_pct).

        For flat-rate: current_minutes / monthly_limit.
        For API (budget_config): reads cumulative from provider-usage.jsonl.
        """
        # Roll over if month changed
        month = self._month_key()
        if month != self._current_month:
            self._current_month = month
            self._accumulated = 0.0 if self.tracking == "session_minutes" else self._accumulated

        if self.tracking == "session_minutes":
            used = self._accumulated
        else:
            used = self._read_api_spend()

        if self.monthly_limit <= 0:
            return True, "", 0.0

        pct = used / self.monthly_limit
        if pct >= 1.0:
            reason = (
                f"Backend {self.backend_name} exhausted: "
                f"{used:.1f}/{self.monthly_limit:.1f} "
                f"({'min' if self.tracking == 'session_minutes' else 'USD'}) "
                f"({pct:.0%})"
            )
            logger.warning("BackendCostBreaker: %s", reason)
            return False, reason, round(pct, 4)
        if pct >= self.warn_pct:
            reason = (
                f"Backend {self.backend_name} approaching limit: "
                f"{used:.1f}/{self.monthly_limit:.1f} ({pct:.0%})"
            )
            logger.info("BackendCostBreaker: %s", reason)
            return True, reason, round(pct, 4)

        return True, "", round(pct, 4)

    def get_state(self) -> dict:
        _, reason, pct = self.check()
        return {
            "backend": self.backend_name,
            "tracking": self.tracking,
            "monthly_limit": self.monthly_limit,
            "used": round(self._accumulated if self.tracking == "session_minutes" else self._read_api_spend(), 2),
            "utilization_pct": pct,
            "warn_pct": self.warn_pct,
            "month": self._current_month,
            "status": "exhausted" if pct >= 1.0 else ("warning" if pct >= self.warn_pct else "ok"),
        }

    # ── Persistence ───────────────────────────────────────────────────

    def _persist(self, minutes: float) -> None:
        """Append a usage record to backend-usage.jsonl."""
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "backend": self.backend_name,
            "minutes": round(minutes, 2),
            "month": self._current_month,
            "cumulative_minutes": round(self._accumulated, 2),
        }
        try:
            with open(self._log_path, "a") as f:
                f.write(json.dumps(record) + "\n")
        except OSError as e:
            logger.warning("Failed to persist backend usage: %s", e)

    def _load_current_month(self) -> float:
        """Sum usage for the current month from the JSONL log."""
        month = self._month_key()
        total = 0.0
        try:
            if not self._log_path.exists():
                return 0.0
            with open(self._log_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if entry.get("backend") == self.backend_name and entry.get("month") == month:
                        total += entry.get("minutes", 0.0)
        except OSError as e:
            logger.warning("Failed to read backend usage log: %s", e)
        return total

    def _read_api_spend(self) -> float:
        """Read cumulative API spend from provider-usage.jsonl for the current month."""
        month = self._month_key()
        total = 0.0
        provider_log = self.LOG_DIR / self.PROVIDER_LOG
        try:
            if not provider_log.exists():
                return 0.0
            with open(provider_log) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    ts = entry.get("timestamp", "")
                    if ts[:7] == month:
                        total += entry.get("estimated_cost_usd", 0.0)
        except OSError as e:
            logger.warning("Failed to read provider usage log: %s", e)
        return total

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _month_key() -> str:
        """Return current month as 'YYYY-MM'."""
        return datetime.now(timezone.utc).strftime("%Y-%m")
