"""
NemoClaw MCP Gateway — Policy enforcement layer for skill invocation.

Wraps skill calls with:
  - Permission checks (agent → skill mapping from capability-registry.yaml)
  - Rate limiting (configurable per-agent call cap)
  - Audit logging (append to ~/.nemoclaw/logs/mcp-audit.jsonl)
  - I/O sanitization (via content_safety if available)

Usage:
    gateway = MCPGateway()
    if not gateway.check_permission("strategy_lead", "e12-market-research-analyst"):
        raise PermissionError("Agent not authorized")
    if not gateway.rate_limit("strategy_lead"):
        raise RateLimitError("Rate limit exceeded")
    # ... invoke skill ...
    gateway.audit_log("strategy_lead", "e12-market-research-analyst", inputs, result)
"""

from __future__ import annotations

import json
import logging
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

import yaml

logger = logging.getLogger("nemoclaw.mcp_gateway")

REPO = Path(__file__).resolve().parent.parent
CAPABILITY_REGISTRY = REPO / "config" / "agents" / "capability-registry.yaml"
AUDIT_LOG = Path.home() / ".nemoclaw" / "logs" / "mcp-audit.jsonl"

# Default: 10 calls/minute per agent
DEFAULT_MAX_CALLS = 10
DEFAULT_WINDOW_SECONDS = 60.0


class MCPGateway:
    """Policy enforcement gateway for MCP skill invocation."""

    def __init__(
        self,
        max_calls_per_minute: int = DEFAULT_MAX_CALLS,
        window_seconds: float = DEFAULT_WINDOW_SECONDS,
    ):
        self.max_calls = max_calls_per_minute
        self.window_seconds = window_seconds

        # Permission cache: agent_id → set of allowed skill_ids
        self._permissions: dict[str, set[str]] | None = None
        self._permissions_loaded_at: float = 0.0

        # Rate limiter: agent_id → deque of timestamps
        self._call_times: dict[str, deque[float]] = defaultdict(lambda: deque())
        self._rate_lock = Lock()

        # Ensure audit log directory exists
        AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)

    # ── Permission Check ─────────────────────────────────────────────

    def check_permission(self, agent_id: str, skill_id: str) -> bool:
        """Check if agent_id is authorized to invoke skill_id.

        Reads capability-registry.yaml and allows if:
          1. The agent owns a capability backed by this skill, OR
          2. The agent is listed as fallback_agent for a capability with this skill

        Returns True if allowed, False otherwise.
        """
        perms = self._load_permissions()
        allowed = perms.get(agent_id, set())
        return skill_id in allowed

    def _load_permissions(self) -> dict[str, set[str]]:
        """Load and cache permission map from capability registry.

        Refreshes every 60 seconds to pick up config changes.
        """
        now = time.monotonic()
        if self._permissions is not None and (now - self._permissions_loaded_at) < 60:
            return self._permissions

        perms: dict[str, set[str]] = defaultdict(set)
        try:
            with open(CAPABILITY_REGISTRY) as f:
                registry = yaml.safe_load(f)

            capabilities = registry.get("capabilities", {})
            for _cap_name, cap in capabilities.items():
                skill = cap.get("skill")
                if not skill:
                    continue

                owner = cap.get("owned_by")
                if owner:
                    perms[owner].add(skill)

                fallback = cap.get("fallback_agent")
                if fallback:
                    perms[fallback].add(skill)

        except Exception as e:
            logger.warning("Failed to load capability registry: %s", e)
            # On failure, return empty (deny all) rather than stale cache
            self._permissions = {}
            self._permissions_loaded_at = now
            return self._permissions

        self._permissions = dict(perms)
        self._permissions_loaded_at = now
        return self._permissions

    # ── Rate Limiting ────────────────────────────────────────────────

    def rate_limit(self, agent_id: str) -> bool:
        """Check if agent_id is within rate limits.

        Sliding window: max N calls within window_seconds.
        Returns True if allowed, False if rate-limited.
        """
        now = time.monotonic()
        with self._rate_lock:
            timestamps = self._call_times[agent_id]

            # Evict expired entries
            cutoff = now - self.window_seconds
            while timestamps and timestamps[0] < cutoff:
                timestamps.popleft()

            if len(timestamps) >= self.max_calls:
                logger.warning(
                    "Rate limit exceeded for %s: %d/%d in %.0fs",
                    agent_id, len(timestamps), self.max_calls, self.window_seconds,
                )
                return False

            timestamps.append(now)
            return True

    # ── Audit Logging ────────────────────────────────────────────────

    def audit_log(
        self,
        agent_id: str,
        skill_id: str,
        inputs: dict[str, Any],
        result: dict[str, Any],
    ) -> None:
        """Append an audit entry to mcp-audit.jsonl."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_id": agent_id,
            "skill_id": skill_id,
            "inputs_keys": list(inputs.keys()),
            "inputs_size": sum(len(str(v)) for v in inputs.values()),
            "success": result.get("success", False),
            "error": result.get("error"),
            "has_envelope": bool(result.get("envelope_path")),
        }
        try:
            with open(AUDIT_LOG, "a") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except Exception as e:
            logger.warning("Failed to write audit log: %s", e)

    # ── I/O Sanitization ─────────────────────────────────────────────

    def sanitize_io(
        self,
        inputs: dict[str, Any],
        outputs: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any] | None, list[str]]:
        """Sanitize inputs and outputs for safety.

        Uses content_safety.detect_pii() if available for PII scrubbing.
        Returns (sanitized_inputs, sanitized_outputs, warnings).
        """
        warnings: list[str] = []

        try:
            from lib.content_safety import detect_pii
            has_safety = True
        except ImportError:
            has_safety = False

        def _scrub(data: dict[str, Any]) -> dict[str, Any]:
            cleaned = {}
            for k, v in data.items():
                text = str(v)
                if has_safety and len(text) > 10:
                    entities, err = detect_pii(text)
                    if entities:
                        pii_types = [e.get("type", "PII") for e in entities]
                        warnings.append(f"PII detected in '{k}': {pii_types}")
                cleaned[k] = v
            return cleaned

        sanitized_inputs = _scrub(inputs)
        sanitized_outputs = _scrub(outputs) if outputs else None

        return sanitized_inputs, sanitized_outputs, warnings

    # ── Convenience: full gate check ─────────────────────────────────

    def gate(self, agent_id: str, skill_id: str) -> tuple[bool, str]:
        """Run permission + rate limit checks. Returns (allowed, reason)."""
        if not self.check_permission(agent_id, skill_id):
            return False, f"Agent '{agent_id}' not authorized for skill '{skill_id}'"
        if not self.rate_limit(agent_id):
            return False, f"Rate limit exceeded for agent '{agent_id}'"
        return True, ""
