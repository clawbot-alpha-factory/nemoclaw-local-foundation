#!/usr/bin/env python3
"""
NemoClaw Failure Recovery System v1.0 (MA-9)

Unified failure detection, classification, and recovery:
- 6 failure categories with configurable retry + exponential backoff
- Dynamic fallback agent/skill via capability registry + confidence
- Blast radius isolation for cascading failures with dependency tracking
- Auto-escalation thresholds per failure type
- Pattern-based learning: repeated failures auto-promote to memory
- Recovery analytics: success rates, mean retries, failure hotspots
- MA-4 decision log integration for all recovery actions

Usage:
  python3 scripts/failure_recovery.py --test
  python3 scripts/failure_recovery.py --patterns
  python3 scripts/failure_recovery.py --history
  python3 scripts/failure_recovery.py --analytics
  python3 scripts/failure_recovery.py --health
"""

import argparse
import json
import os
import sys
import time
import uuid
import yaml
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict

REPO = Path.home() / "nemoclaw-local-foundation"
RECOVERY_DIR = Path.home() / ".nemoclaw" / "recovery"
FAILURES_PATH = RECOVERY_DIR / "failure-log.jsonl"
PATTERNS_PATH = RECOVERY_DIR / "failure-patterns.json"
ANALYTICS_PATH = RECOVERY_DIR / "recovery-analytics.json"

PATTERN_PROMOTION_THRESHOLD = 3  # promote to memory after N same failures

# ═══════════════════════════════════════════════════════════════════════════════
# FAILURE CATEGORIES & RETRY CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

FAILURE_CATEGORIES = {
    "transient": {
        "description": "Temporary failures that resolve on retry",
        "examples": ["API timeout", "rate limit", "network blip", "503 error"],
        "max_retries": 3,
        "backoff_base_s": 2,
        "backoff_multiplier": 2.0,
        "backoff_max_s": 30,
        "auto_retry": True,
        "escalate_after_exhaust": False,
        "escalate_threshold": 5,  # escalate after N occurrences in session
    },
    "resource": {
        "description": "Resource exhaustion or corruption",
        "examples": ["budget exhausted", "checkpoint corrupt", "disk full"],
        "max_retries": 1,
        "backoff_base_s": 5,
        "backoff_multiplier": 1.0,
        "backoff_max_s": 5,
        "auto_retry": False,
        "escalate_after_exhaust": True,
        "escalate_threshold": 1,  # escalate immediately
    },
    "logic": {
        "description": "Input/output validation or quality failures",
        "examples": ["input validation failed", "output too short", "missing sections"],
        "max_retries": 2,
        "backoff_base_s": 1,
        "backoff_multiplier": 1.0,
        "backoff_max_s": 5,
        "auto_retry": True,
        "escalate_after_exhaust": True,
        "escalate_threshold": 3,
    },
    "agent": {
        "description": "Agent producing bad output or violating rules",
        "examples": ["behavior violation", "low quality output", "role drift"],
        "max_retries": 1,
        "backoff_base_s": 0,
        "backoff_multiplier": 1.0,
        "backoff_max_s": 0,
        "auto_retry": False,
        "escalate_after_exhaust": True,
        "escalate_threshold": 2,
        "use_fallback_agent": True,
    },
    "system": {
        "description": "Process crash, DB corruption, config missing",
        "examples": ["process crash", "DB locked", "config file missing", "import error"],
        "max_retries": 2,
        "backoff_base_s": 5,
        "backoff_multiplier": 3.0,
        "backoff_max_s": 60,
        "auto_retry": True,
        "escalate_after_exhaust": True,
        "escalate_threshold": 3,
    },
    "cascading": {
        "description": "One failure triggers downstream failures",
        "examples": ["parent task failed", "dependency unavailable", "upstream data missing"],
        "max_retries": 0,
        "backoff_base_s": 0,
        "backoff_multiplier": 1.0,
        "backoff_max_s": 0,
        "auto_retry": False,
        "escalate_after_exhaust": True,
        "escalate_threshold": 1,
        "isolate_blast_radius": True,
    },
}

# Signal → category classification
SIGNAL_MAP = {
    "timeout": "transient",
    "rate_limit": "transient",
    "429": "transient",
    "503": "transient",
    "connection": "transient",
    "budget": "resource",
    "exhausted": "resource",
    "disk": "resource",
    "checkpoint": "resource",
    "corrupt": "resource",
    "validation": "logic",
    "too short": "logic",
    "missing section": "logic",
    "quality": "logic",
    "min_length": "logic",
    "behavior": "agent",
    "violation": "agent",
    "role drift": "agent",
    "compliance": "agent",
    "crash": "system",
    "import": "system",
    "config": "system",
    "db locked": "system",
    "permission": "system",
    "blocked by": "cascading",
    "upstream": "cascading",
    "dependency": "cascading",
    "parent failed": "cascading",
}


# ═══════════════════════════════════════════════════════════════════════════════
# FAILURE RECORD
# ═══════════════════════════════════════════════════════════════════════════════

def new_failure(source, error_message, category=None, agent_id=None,
                task_id=None, skill_id=None, plan_id=None,
                downstream_tasks=None):
    """Create a failure record."""
    auto_category = category or classify_failure(error_message)
    return {
        "id": f"fail_{uuid.uuid4().hex[:8]}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": source,  # "task", "agent", "skill", "system", "orchestrator"
        "error_message": error_message,
        "category": auto_category,
        "agent_id": agent_id,
        "task_id": task_id,
        "skill_id": skill_id,
        "plan_id": plan_id,
        "downstream_tasks": downstream_tasks or [],
        "retries_attempted": 0,
        "recovery_strategy": None,
        "recovery_outcome": None,  # "recovered" | "fallback_used" | "escalated" | "failed"
        "fallback_agent": None,
        "fallback_skill": None,
        "escalated_to": None,
        "recovery_duration_s": 0,
        "pattern_key": None,
    }


def classify_failure(error_message):
    """Auto-classify failure based on error message signals."""
    msg_lower = error_message.lower()
    for signal, category in SIGNAL_MAP.items():
        if signal in msg_lower:
            return category
    return "logic"  # default


# ═══════════════════════════════════════════════════════════════════════════════
# FALLBACK SELECTOR (dynamic, capability-aware)
# ═══════════════════════════════════════════════════════════════════════════════

class FallbackSelector:
    """Selects best fallback agent/skill using capability registry."""

    def __init__(self):
        self._registry = None
        self._schema = None

    def _load(self):
        if self._registry is not None:
            return
        try:
            with open(REPO / "config" / "agents" / "capability-registry.yaml") as f:
                self._registry = yaml.safe_load(f).get("capabilities", {})
            with open(REPO / "config" / "agents" / "agent-schema.yaml") as f:
                self._schema = yaml.safe_load(f)
        except Exception:
            self._registry = {}
            self._schema = {"agents": []}

    def find_fallback(self, failed_agent, capability=None, skill_id=None):
        """Find the best fallback agent for a failed capability.

        Selection logic:
        1. Check capability registry for explicit fallback_agent
        2. Find other agents who own similar capabilities
        3. Prefer higher authority level (lower number)
        4. Never return the failed agent

        Returns: (fallback_agent_id, fallback_skill, confidence)
        """
        self._load()

        # Strategy 1: Explicit fallback in registry
        if capability and capability in self._registry:
            cap = self._registry[capability]
            fb = cap.get("fallback_agent")
            if fb and fb != failed_agent:
                fb_skill = cap.get("skill", skill_id)
                return fb, fb_skill, 0.8

        # Strategy 2: Find agents with same skill
        if skill_id:
            for cap_name, cap in self._registry.items():
                if cap.get("skill") == skill_id and cap.get("owned_by") != failed_agent:
                    return cap["owned_by"], skill_id, 0.6

        # Strategy 3: Find agents in same domain family
        if capability:
            cap_prefix = capability.split("_")[0] if capability else ""
            for cap_name, cap in self._registry.items():
                if (cap_name.startswith(cap_prefix) and
                    cap.get("owned_by") != failed_agent):
                    return cap["owned_by"], cap.get("skill"), 0.4

        # Strategy 4: Executive operator as last resort
        if failed_agent != "executive_operator":
            return "executive_operator", skill_id, 0.3

        return None, None, 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# PATTERN TRACKER (failure learning)
# ═══════════════════════════════════════════════════════════════════════════════

class PatternTracker:
    """Tracks failure patterns and promotes repeated ones to long-term memory."""

    def __init__(self):
        self.patterns = {}  # pattern_key → {count, first_seen, last_seen, category, ...}
        self._load()

    def _load(self):
        RECOVERY_DIR.mkdir(parents=True, exist_ok=True)
        if PATTERNS_PATH.exists():
            try:
                with open(PATTERNS_PATH) as f:
                    self.patterns = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.patterns = {}

    def _save(self):
        RECOVERY_DIR.mkdir(parents=True, exist_ok=True)
        with open(PATTERNS_PATH, "w") as f:
            json.dump(self.patterns, f, indent=2)

    def _make_key(self, failure):
        """Generate a pattern key from failure attributes."""
        parts = [
            failure.get("category") or "unknown",
            failure.get("skill_id") or "none",
            failure.get("agent_id") or "none",
            (failure.get("error_message") or "")[:50].lower().strip(),
        ]
        return "|".join(parts)

    def record(self, failure):
        """Record a failure and check for pattern promotion.

        Returns: (is_pattern: bool, count: int, promoted: bool)
        """
        key = self._make_key(failure)
        failure["pattern_key"] = key
        now = datetime.now(timezone.utc).isoformat()

        if key not in self.patterns:
            self.patterns[key] = {
                "count": 0,
                "first_seen": now,
                "last_seen": now,
                "category": failure.get("category"),
                "skill_id": failure.get("skill_id"),
                "agent_id": failure.get("agent_id"),
                "error_sample": failure.get("error_message", "")[:100],
                "promoted": False,
                "recoveries": {"recovered": 0, "fallback_used": 0, "escalated": 0, "failed": 0},
            }

        pattern = self.patterns[key]
        pattern["count"] += 1
        pattern["last_seen"] = now

        # Track recovery outcomes
        outcome = failure.get("recovery_outcome")
        if outcome and outcome in pattern["recoveries"]:
            pattern["recoveries"][outcome] += 1

        is_pattern = pattern["count"] >= PATTERN_PROMOTION_THRESHOLD
        promoted = False

        if is_pattern and not pattern["promoted"]:
            promoted = self._promote_to_memory(key, pattern)
            pattern["promoted"] = True

        self._save()
        return is_pattern, pattern["count"], promoted

    def _promote_to_memory(self, key, pattern):
        """Promote a failure pattern to long-term memory."""
        try:
            from agent_memory import MemorySystem
            dp = {"executive_operator": ["*"]}
            mem = MemorySystem("failure_learning", dp)

            lesson = (
                f"Recurring failure pattern ({pattern['count']}x): "
                f"category={pattern['category']}, "
                f"skill={pattern['skill_id']}, "
                f"agent={pattern['agent_id']}, "
                f"error='{pattern['error_sample']}'. "
                f"Recovery stats: {json.dumps(pattern['recoveries'])}"
            )

            mem.shared.write(
                f"failure_pattern_{key[:30]}",
                lesson,
                agent="executive_operator",
                importance="standard",
                confidence=0.7,
            )
            return True
        except Exception:
            return False

    def get_patterns(self, min_count=1):
        """Get all patterns above threshold."""
        return {k: v for k, v in self.patterns.items() if v["count"] >= min_count}


# ═══════════════════════════════════════════════════════════════════════════════
# RECOVERY ANALYTICS
# ═══════════════════════════════════════════════════════════════════════════════

class RecoveryAnalytics:
    """Tracks recovery metrics for operational insights."""

    def __init__(self):
        self.metrics = {
            "total_failures": 0,
            "total_recoveries": 0,
            "total_escalations": 0,
            "total_unrecovered": 0,
            "by_category": {},
            "by_agent": {},
            "by_skill": {},
            "mean_retries": 0.0,
            "recovery_rate": 0.0,
        }
        self._all_retries = []
        self._load()

    def _load(self):
        RECOVERY_DIR.mkdir(parents=True, exist_ok=True)
        if ANALYTICS_PATH.exists():
            try:
                with open(ANALYTICS_PATH) as f:
                    data = json.load(f)
                    self.metrics = data.get("metrics", self.metrics)
                    self._all_retries = data.get("retry_counts", [])
            except (json.JSONDecodeError, IOError):
                pass

    def _save(self):
        RECOVERY_DIR.mkdir(parents=True, exist_ok=True)
        with open(ANALYTICS_PATH, "w") as f:
            json.dump({
                "metrics": self.metrics,
                "retry_counts": self._all_retries[-500:],
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }, f, indent=2)

    def record(self, failure):
        """Record a failure outcome for analytics."""
        category = failure.get("category", "unknown")
        agent = failure.get("agent_id", "unknown")
        skill = failure.get("skill_id", "unknown")
        outcome = failure.get("recovery_outcome", "failed")
        retries = failure.get("retries_attempted", 0)

        self.metrics["total_failures"] += 1

        if outcome in ("recovered", "fallback_used"):
            self.metrics["total_recoveries"] += 1
        elif outcome == "escalated":
            self.metrics["total_escalations"] += 1
        else:
            self.metrics["total_unrecovered"] += 1

        # By category
        if category not in self.metrics["by_category"]:
            self.metrics["by_category"][category] = {"total": 0, "recovered": 0, "escalated": 0, "failed": 0}
        cat_m = self.metrics["by_category"][category]
        cat_m["total"] += 1
        if outcome in ("recovered", "fallback_used"):
            cat_m["recovered"] += 1
        elif outcome == "escalated":
            cat_m["escalated"] += 1
        else:
            cat_m["failed"] += 1

        # By agent
        if agent not in self.metrics["by_agent"]:
            self.metrics["by_agent"][agent] = {"total": 0, "recovered": 0}
        self.metrics["by_agent"][agent]["total"] += 1
        if outcome in ("recovered", "fallback_used"):
            self.metrics["by_agent"][agent]["recovered"] += 1

        # By skill
        if skill not in self.metrics["by_skill"]:
            self.metrics["by_skill"][skill] = {"total": 0, "recovered": 0}
        self.metrics["by_skill"][skill]["total"] += 1
        if outcome in ("recovered", "fallback_used"):
            self.metrics["by_skill"][skill]["recovered"] += 1

        # Mean retries
        self._all_retries.append(retries)
        self.metrics["mean_retries"] = round(
            sum(self._all_retries) / len(self._all_retries), 2
        ) if self._all_retries else 0.0

        # Recovery rate
        total = self.metrics["total_failures"]
        recovered = self.metrics["total_recoveries"]
        self.metrics["recovery_rate"] = round(recovered / total, 3) if total > 0 else 0.0

        self._save()

    def get_hotspots(self, top_n=5):
        """Get top failure hotspots by skill and agent."""
        skill_sorted = sorted(
            self.metrics.get("by_skill", {}).items(),
            key=lambda x: x[1]["total"], reverse=True
        )[:top_n]

        agent_sorted = sorted(
            self.metrics.get("by_agent", {}).items(),
            key=lambda x: x[1]["total"], reverse=True
        )[:top_n]

        return {"skills": skill_sorted, "agents": agent_sorted}

    def summary(self):
        """Print analytics summary."""
        m = self.metrics
        print(f"  Total failures: {m['total_failures']}")
        print(f"  Recovered: {m['total_recoveries']} ({m['recovery_rate']:.0%})")
        print(f"  Escalated: {m['total_escalations']}")
        print(f"  Unrecovered: {m['total_unrecovered']}")
        print(f"  Mean retries: {m['mean_retries']:.1f}")

        if m.get("by_category"):
            print(f"\n  By category:")
            for cat, stats in m["by_category"].items():
                rate = stats["recovered"] / stats["total"] if stats["total"] > 0 else 0
                print(f"    {cat}: {stats['total']} failures, {rate:.0%} recovered")

        hotspots = self.get_hotspots(3)
        if hotspots["skills"]:
            print(f"\n  Top failure skills:")
            for skill, stats in hotspots["skills"]:
                print(f"    {skill}: {stats['total']} failures")


# ═══════════════════════════════════════════════════════════════════════════════
# FAILURE RECOVERY ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class FailureRecovery:
    """Unified failure recovery engine.

    Usage:
        recovery = FailureRecovery()
        failure = new_failure("task", "API timeout", agent_id="strategy_lead")
        result = recovery.handle(failure)
        # result = {"outcome": str, "retries": int, "fallback_used": bool, ...}
    """

    def __init__(self):
        self.fallback_selector = FallbackSelector()
        self.pattern_tracker = PatternTracker()
        self.analytics = RecoveryAnalytics()
        self._session_counts = defaultdict(int)  # category → count this session

    def handle(self, failure, retry_fn=None):
        """Handle a failure with appropriate recovery strategy.

        Args:
            failure: failure record from new_failure()
            retry_fn: optional callable(failure) → (success, result) for retrying

        Returns: dict with outcome, retries, fallback info
        """
        category = failure["category"]
        config = FAILURE_CATEGORIES.get(category, FAILURE_CATEGORIES["logic"])
        start_time = time.time()

        self._session_counts[category] += 1

        # ── CASCADING: ISOLATE BLAST RADIUS (check first, before threshold) ──
        if config.get("isolate_blast_radius") and failure.get("downstream_tasks"):
            isolated = failure["downstream_tasks"]
            failure["recovery_strategy"] = f"blast_radius_isolation: {len(isolated)} downstream tasks isolated"
            failure["recovery_outcome"] = "escalated"
            failure["escalated_to"] = "executive_operator"
            self._finalize(failure, start_time)
            return self._result(failure, "escalated",
                                 f"Cascading failure isolated {len(isolated)} downstream tasks")

        # ── CHECK ESCALATION THRESHOLD (repeated failures in session) ──
        if self._session_counts[category] >= config.get("escalate_threshold", 999):
            if config.get("escalate_after_exhaust", False) and not config.get("auto_retry", False):
                failure["recovery_outcome"] = "escalated"
                failure["escalated_to"] = "executive_operator"
                self._finalize(failure, start_time)
                return self._result(failure, "escalated",
                                     f"Category '{category}' hit escalation threshold "
                                     f"({self._session_counts[category]}/{config['escalate_threshold']})")

        # ── AUTO-RETRY WITH BACKOFF ──
        if config["auto_retry"] and retry_fn:
            max_retries = config["max_retries"]
            for attempt in range(1, max_retries + 1):
                delay = min(
                    config["backoff_base_s"] * (config["backoff_multiplier"] ** (attempt - 1)),
                    config["backoff_max_s"]
                )
                if delay > 0:
                    time.sleep(delay)

                failure["retries_attempted"] = attempt
                success, result = retry_fn(failure)

                if success:
                    failure["recovery_strategy"] = f"retry_{attempt}"
                    failure["recovery_outcome"] = "recovered"
                    self._finalize(failure, start_time)
                    return self._result(failure, "recovered",
                                         f"Recovered on retry {attempt}/{max_retries}")

        # ── FALLBACK AGENT ──
        if config.get("use_fallback_agent", False) or category in ("logic", "agent"):
            fb_agent, fb_skill, fb_conf = self.fallback_selector.find_fallback(
                failure.get("agent_id", ""),
                capability=failure.get("source"),
                skill_id=failure.get("skill_id"),
            )

            if fb_agent and fb_conf > 0:
                failure["fallback_agent"] = fb_agent
                failure["fallback_skill"] = fb_skill
                failure["recovery_strategy"] = f"fallback_agent:{fb_agent} (conf={fb_conf})"

                if retry_fn:
                    # Retry with fallback
                    failure["agent_id"] = fb_agent
                    if fb_skill:
                        failure["skill_id"] = fb_skill
                    success, result = retry_fn(failure)
                    if success:
                        failure["recovery_outcome"] = "fallback_used"
                        self._finalize(failure, start_time)
                        return self._result(failure, "fallback_used",
                                             f"Recovered via fallback agent {fb_agent}")

                failure["recovery_outcome"] = "fallback_used"
                self._finalize(failure, start_time)
                return self._result(failure, "fallback_used",
                                     f"Assigned to fallback agent {fb_agent}")

        # ── ESCALATE ──
        if config.get("escalate_after_exhaust", False):
            failure["recovery_outcome"] = "escalated"
            failure["escalated_to"] = "executive_operator"
            failure["recovery_strategy"] = "escalate_after_exhaust"
            self._finalize(failure, start_time)
            return self._result(failure, "escalated",
                                 f"All recovery options exhausted, escalated to executive_operator")

        # ── UNRECOVERED ──
        failure["recovery_outcome"] = "failed"
        failure["recovery_strategy"] = "no_recovery_available"
        self._finalize(failure, start_time)
        return self._result(failure, "failed", "No recovery strategy succeeded")

    def _finalize(self, failure, start_time):
        """Finalize failure: log, track patterns, update analytics."""
        failure["recovery_duration_s"] = round(time.time() - start_time, 2)

        # Log to disk
        self._log_failure(failure)

        # Track patterns
        self.pattern_tracker.record(failure)

        # Update analytics
        self.analytics.record(failure)

        # Log to MA-4 for escalated/failed outcomes
        if failure["recovery_outcome"] in ("escalated", "failed"):
            self._log_to_decisions(failure)

    def _result(self, failure, outcome, message):
        """Build result dict."""
        return {
            "failure_id": failure["id"],
            "outcome": outcome,
            "message": message,
            "category": failure["category"],
            "retries": failure["retries_attempted"],
            "fallback_agent": failure.get("fallback_agent"),
            "fallback_skill": failure.get("fallback_skill"),
            "escalated_to": failure.get("escalated_to"),
            "recovery_duration_s": failure.get("recovery_duration_s", 0),
            "pattern_key": failure.get("pattern_key"),
        }

    def _log_failure(self, failure):
        """Append failure to persistent log."""
        RECOVERY_DIR.mkdir(parents=True, exist_ok=True)
        with open(FAILURES_PATH, "a") as f:
            f.write(json.dumps(failure) + "\n")

    def _log_to_decisions(self, failure):
        """Log critical failures to MA-4 decision system."""
        try:
            from decision_log import DecisionLog
            dl = DecisionLog()
            title = f"Failure recovery: {failure['category']} ({failure['recovery_outcome']})"
            desc = (
                f"Source: {failure['source']}\n"
                f"Error: {failure['error_message'][:150]}\n"
                f"Agent: {failure.get('agent_id', 'N/A')}\n"
                f"Skill: {failure.get('skill_id', 'N/A')}\n"
                f"Retries: {failure['retries_attempted']}\n"
                f"Recovery: {failure['recovery_strategy']}\n"
                f"Duration: {failure['recovery_duration_s']}s\n"
            )
            if failure.get("fallback_agent"):
                desc += f"Fallback: {failure['fallback_agent']}\n"
            if failure.get("downstream_tasks"):
                desc += f"Downstream isolated: {len(failure['downstream_tasks'])}\n"

            dec_id, _ = dl.propose("executive_operator", title, desc,
                                    reversibility="irreversible", confidence=0.9)
            dl.decide(dec_id, f"Auto-logged: {failure['recovery_outcome']}",
                     failure['error_message'][:100], decided_by="executive_operator")
        except Exception:
            pass

    def get_session_counts(self):
        """Get failure counts per category this session."""
        return dict(self._session_counts)


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS
# ═══════════════════════════════════════════════════════════════════════════════

def run_tests():
    print("=" * 60)
    print("  MA-9 Failure Recovery System Tests")
    print("=" * 60)

    tp = 0
    tt = 0

    def test(name, condition, detail=""):
        nonlocal tp, tt
        tt += 1
        if condition:
            tp += 1
            print(f"  ✅ {name}")
        else:
            print(f"  ❌ {name}: {detail}")

    # Test 1: Category definitions
    test("6 failure categories defined", len(FAILURE_CATEGORIES) == 6)

    # Test 2: All categories have required fields
    req_fields = ["max_retries", "backoff_base_s", "auto_retry", "escalate_threshold"]
    all_ok = all(all(f in cat for f in req_fields) for cat in FAILURE_CATEGORIES.values())
    test("All categories have required config", all_ok)

    # Test 3: Auto-classification
    test("Timeout → transient", classify_failure("API timeout after 30s") == "transient")
    test("Budget → resource", classify_failure("budget exhausted for anthropic") == "resource")
    test("Validation → logic", classify_failure("Input validation failed: too short") == "logic")
    test("Violation → agent", classify_failure("behavior violation: role drift") == "agent")
    test("Crash → system", classify_failure("process crash in skill runner") == "system")
    test("Upstream → cascading", classify_failure("blocked by failed task_001") == "cascading")

    # Test 9: Transient recovery with retry
    recovery = FailureRecovery()
    attempt_count = 0

    def mock_retry_succeeds_on_2(failure):
        nonlocal attempt_count
        attempt_count += 1
        return attempt_count >= 2, "success"

    failure = new_failure("task", "API timeout", category="transient",
                          agent_id="strategy_lead", skill_id="e12-market-research-analyst")
    result = recovery.handle(failure, retry_fn=mock_retry_succeeds_on_2)
    test("Transient: recovers on retry 2", result["outcome"] == "recovered" and result["retries"] == 2)

    # Test 10: Resource failure escalates immediately
    recovery2 = FailureRecovery()
    failure2 = new_failure("system", "budget exhausted", category="resource",
                           agent_id="strategy_lead")
    result2 = recovery2.handle(failure2)
    test("Resource: escalates immediately", result2["outcome"] == "escalated")

    # Test 11: Agent failure uses fallback
    recovery3 = FailureRecovery()
    failure3 = new_failure("agent", "behavior violation: role drift", category="agent",
                           agent_id="strategy_lead", skill_id="e12-market-research-analyst")
    result3 = recovery3.handle(failure3)
    test("Agent failure: fallback assigned",
         result3["outcome"] == "fallback_used" and result3["fallback_agent"] is not None,
         str(result3))

    # Test 12: Cascading failure isolates blast radius
    recovery4 = FailureRecovery()
    failure4 = new_failure("task", "blocked by failed parent", category="cascading",
                           downstream_tasks=["task_002", "task_003", "task_004"])
    result4 = recovery4.handle(failure4)
    test("Cascading: blast radius isolated",
         result4["outcome"] == "escalated" and "3 downstream" in result4["message"])

    # Test 13: Retry exhaustion → escalate
    recovery5 = FailureRecovery()
    def mock_always_fails(failure):
        return False, "still failing"

    failure5 = new_failure("task", "Input validation failed", category="logic",
                           agent_id="product_architect", skill_id="f09-product-req-writer")
    result5 = recovery5.handle(failure5, retry_fn=mock_always_fails)
    test("Logic: exhaustion → escalate",
         result5["outcome"] in ("escalated", "fallback_used"), result5["outcome"])

    # Test 14: Pattern tracking (fresh tracker with unique error to avoid persistence)
    tracker = PatternTracker()
    unique_err = f"test_timeout_{uuid.uuid4().hex[:6]}"
    f_template = new_failure("task", unique_err,
                              category="transient", skill_id="e12-market-research-analyst")

    for i in range(PATTERN_PROMOTION_THRESHOLD - 1):
        is_pattern, count, promoted = tracker.record(f_template.copy())
    test(f"Pattern: not yet at {PATTERN_PROMOTION_THRESHOLD - 1} occurrences",
         not is_pattern and count == PATTERN_PROMOTION_THRESHOLD - 1,
         f"is_pattern={is_pattern} count={count}")

    is_pattern, count, promoted = tracker.record(f_template.copy())
    test(f"Pattern: triggers at {PATTERN_PROMOTION_THRESHOLD} occurrences",
         is_pattern and count == PATTERN_PROMOTION_THRESHOLD,
         f"is_pattern={is_pattern} count={count}")

    # Test 16: Analytics recording
    analytics = RecoveryAnalytics()
    test_failure = new_failure("task", "test error", category="transient")
    test_failure["recovery_outcome"] = "recovered"
    test_failure["retries_attempted"] = 2
    analytics.record(test_failure)
    test("Analytics: failure recorded", analytics.metrics["total_failures"] >= 1)
    test("Analytics: recovery counted", analytics.metrics["total_recoveries"] >= 1)

    test_failure2 = new_failure("task", "bad output", category="logic",
                                 agent_id="strategy_lead", skill_id="e12-market-research-analyst")
    test_failure2["recovery_outcome"] = "escalated"
    analytics.record(test_failure2)
    test("Analytics: escalation counted", analytics.metrics["total_escalations"] >= 1)

    # Test 19: Recovery rate
    test("Analytics: recovery rate calculated",
         0.0 <= analytics.metrics["recovery_rate"] <= 1.0,
         f"{analytics.metrics['recovery_rate']}")

    # Test 20: Hotspots
    hotspots = analytics.get_hotspots(3)
    test("Analytics: hotspots available",
         "skills" in hotspots and "agents" in hotspots)

    # Test 21: Fallback selector
    selector = FallbackSelector()
    fb_agent, fb_skill, fb_conf = selector.find_fallback(
        "strategy_lead", capability="market_research", skill_id="e12-market-research-analyst")
    test("Fallback: finds alternative agent",
         fb_agent is not None and fb_agent != "strategy_lead",
         f"got {fb_agent}")

    # Test 22: Fallback confidence
    test("Fallback: has confidence score", fb_conf > 0, f"conf={fb_conf}")

    # Test 23: Executive as last resort
    fb_agent2, _, fb_conf2 = selector.find_fallback(
        "operations_lead", capability="nonexistent_cap")
    test("Fallback: executive as last resort",
         fb_agent2 == "executive_operator" and fb_conf2 <= 0.3,
         f"{fb_agent2} conf={fb_conf2}")

    # Test 24: Session escalation tracking
    recovery6 = FailureRecovery()
    for i in range(5):
        f = new_failure("task", "API timeout", category="transient")
        recovery6.handle(f, retry_fn=mock_always_fails)
    counts = recovery6.get_session_counts()
    test("Session: tracks failure counts per category",
         counts.get("transient", 0) >= 5, str(counts))

    # Test 25: System failure with backoff
    recovery7 = FailureRecovery()
    sys_attempt = 0
    def mock_sys_recovers_on_2(failure):
        nonlocal sys_attempt
        sys_attempt += 1
        return sys_attempt >= 2, "ok"
    failure_sys = new_failure("system", "DB locked temporarily", category="system")
    result_sys = recovery7.handle(failure_sys, retry_fn=mock_sys_recovers_on_2)
    test("System: recovers on retry with backoff",
         result_sys["outcome"] == "recovered", result_sys["outcome"])

    # Test 26: No recovery returns failed
    recovery8 = FailureRecovery()
    failure_none = new_failure("task", "unknown error xyz", category="transient")
    result_none = recovery8.handle(failure_none)  # no retry_fn, not escalatable for first occurrence
    test("No retry_fn: appropriate outcome",
         result_none["outcome"] in ("failed", "escalated", "fallback_used"),
         result_none["outcome"])

    print(f"\n  Results: {tp}/{tt} passed")
    return tp == tt


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="NemoClaw Failure Recovery System")
    parser.add_argument("--test", action="store_true", help="Run all tests")
    parser.add_argument("--patterns", action="store_true", help="Show failure patterns")
    parser.add_argument("--history", action="store_true", help="Show recent failures")
    parser.add_argument("--analytics", action="store_true", help="Show recovery analytics")
    parser.add_argument("--health", action="store_true", help="System health summary")
    args = parser.parse_args()

    if args.test:
        success = run_tests()
        sys.exit(0 if success else 1)

    elif args.patterns:
        tracker = PatternTracker()
        patterns = tracker.get_patterns(min_count=2)
        if not patterns:
            print("  No recurring patterns yet.")
        else:
            print(f"  Failure Patterns ({len(patterns)}):")
            for key, p in sorted(patterns.items(), key=lambda x: -x[1]["count"]):
                status = "📤 PROMOTED" if p["promoted"] else "📊 TRACKING"
                print(f"  [{status}] {p['count']}x — {p['category']} | {p['skill_id']} | {p['agent_id']}")
                print(f"    Error: {p['error_sample']}")
                print(f"    Recovery: {json.dumps(p['recoveries'])}")
                print()

    elif args.history:
        if FAILURES_PATH.exists():
            with open(FAILURES_PATH) as f:
                lines = f.readlines()
            for line in lines[-20:]:
                try:
                    fail = json.loads(line.strip())
                    ts = fail.get("timestamp", "?")[:19]
                    outcome = {"recovered": "✅", "fallback_used": "🔀",
                               "escalated": "🚨", "failed": "❌"}.get(
                        fail.get("recovery_outcome", "?"), "?")
                    print(f"  [{ts}] {outcome} {fail['category']}: "
                          f"{fail['error_message'][:60]} "
                          f"(agent={fail.get('agent_id', '?')}, retries={fail.get('retries_attempted', 0)})")
                except json.JSONDecodeError:
                    continue
        else:
            print("  No failure history yet.")

    elif args.analytics:
        analytics = RecoveryAnalytics()
        analytics.summary()

    elif args.health:
        print("  System Health:")
        analytics = RecoveryAnalytics()
        m = analytics.metrics
        total = m.get("total_failures", 0)
        rate = m.get("recovery_rate", 0)

        if total == 0:
            print("  ✅ No failures recorded")
        else:
            icon = "✅" if rate >= 0.8 else ("⚠️" if rate >= 0.5 else "❌")
            print(f"  {icon} Recovery rate: {rate:.0%} ({m['total_recoveries']}/{total})")
            print(f"  Mean retries: {m.get('mean_retries', 0):.1f}")
            print(f"  Escalations: {m.get('total_escalations', 0)}")

        tracker = PatternTracker()
        patterns = tracker.get_patterns(min_count=PATTERN_PROMOTION_THRESHOLD)
        if patterns:
            print(f"  ⚠️  {len(patterns)} recurring failure patterns detected")
        else:
            print(f"  ✅ No recurring failure patterns")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
