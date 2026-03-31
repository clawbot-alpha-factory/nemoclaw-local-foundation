"""
NemoClaw Execution Engine — Rate Limiter Service

Sliding-window rate limiter. In-memory (upgradeable to Redis).
Per-endpoint, per-key limiting with configurable windows.

Inspired by OpenClaw's production-grade rate limiting.

NEW FILE: command-center/backend/app/services/rate_limiter_service.py
"""
from __future__ import annotations

import logging
import time
from collections import deque
from threading import Lock
from typing import Any

logger = logging.getLogger("cc.ratelimit")

_CLEANUP_INTERVAL = 128


class SlidingWindowLimiter:
    """Single sliding-window rate limiter."""

    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: dict[str, deque[float]] = {}
        self._lock = Lock()
        self._call_count = 0
        self._blocked_count = 0

    def is_allowed(self, key: str) -> bool:
        """Return True if allowed, False if rate-limited."""
        now = time.monotonic()
        cutoff = now - self.window_seconds

        with self._lock:
            self._call_count += 1

            # Periodic cleanup of stale keys
            if self._call_count % _CLEANUP_INTERVAL == 0:
                expired = [k for k, q in self._buckets.items() if not q or q[-1] <= cutoff]
                for k in expired:
                    del self._buckets[k]

            timestamps = self._buckets.get(key)
            if timestamps is None:
                timestamps = deque()
                self._buckets[key] = timestamps

            # Prune expired
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()

            if len(timestamps) < self.max_requests:
                timestamps.append(now)
                return True

            # Rate limited — slide window (blocked attempts extend it)
            timestamps.popleft()
            timestamps.append(now)
            self._blocked_count += 1
            return False

    def get_stats(self) -> dict[str, Any]:
        return {
            "max_requests": self.max_requests,
            "window_seconds": self.window_seconds,
            "active_keys": len(self._buckets),
            "total_checks": self._call_count,
            "total_blocked": self._blocked_count,
        }


class RateLimiterService:
    """
    Manages multiple rate limiters for different endpoints/purposes.

    Pre-configured limiters:
    - api_general: 100 req/min per IP
    - bridge_calls: 30 req/min per bridge
    - skill_execution: 20 req/min per skill
    - auth_attempts: 10 req/min per IP
    - webhook_ingest: 60 req/min per source
    """

    def __init__(self):
        self._limiters: dict[str, SlidingWindowLimiter] = {
            "api_general": SlidingWindowLimiter(max_requests=100, window_seconds=60),
            "bridge_calls": SlidingWindowLimiter(max_requests=30, window_seconds=60),
            "skill_execution": SlidingWindowLimiter(max_requests=20, window_seconds=60),
            "auth_attempts": SlidingWindowLimiter(max_requests=10, window_seconds=60),
            "webhook_ingest": SlidingWindowLimiter(max_requests=60, window_seconds=60),
            "autonomous_loop": SlidingWindowLimiter(max_requests=60, window_seconds=3600),
        }
        logger.info("RateLimiterService initialized (%d limiters)", len(self._limiters))

    def check(self, limiter_name: str, key: str) -> bool:
        """Check if request is allowed. Returns True if allowed."""
        limiter = self._limiters.get(limiter_name)
        if not limiter:
            return True  # Unknown limiter = allow (fail-open)
        return limiter.is_allowed(key)

    def add_limiter(self, name: str, max_requests: int, window_seconds: float) -> None:
        """Add a custom limiter."""
        self._limiters[name] = SlidingWindowLimiter(max_requests, window_seconds)

    def get_stats(self) -> dict[str, Any]:
        return {
            "limiters": {name: lim.get_stats() for name, lim in self._limiters.items()},
            "total_limiters": len(self._limiters),
        }

    def get_limiter_stats(self, name: str) -> dict[str, Any] | None:
        limiter = self._limiters.get(name)
        return limiter.get_stats() if limiter else None
