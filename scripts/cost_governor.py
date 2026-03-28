#!/usr/bin/env python3
"""
NemoClaw Cost Governance & Circuit Breaker v1.0 (MA-6)

Real-time cost monitoring during plan execution:
- Budget reservation with warn-then-block enforcement
- Circuit breaker at 150% of estimate (CLOSED → OPEN → HALF_OPEN)
- Per-agent cost ledger
- Threshold alerts at 50%, 75%, 90%, 100%
- Integration with MA-5 task decomposer and budget-enforcer.py

Usage:
  # Imported by task_decomposer.py during execution
  from scripts.cost_governor import CostGovernor
  gov = CostGovernor(plan)
  gov.reserve()
  gov.track_task(task, actual_cost)
  gov.check_breaker()
  gov.release()

  # Standalone
  python3 scripts/cost_governor.py --status
  python3 scripts/cost_governor.py --ledger
  python3 scripts/cost_governor.py --test
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path.home() / "nemoclaw-local-foundation"
LOGS_DIR = Path.home() / ".nemoclaw" / "logs"
GOVERNOR_DIR = Path.home() / ".nemoclaw" / "cost-governance"
SPEND_PATH = LOGS_DIR / "provider-spend.json"
USAGE_PATH = LOGS_DIR / "provider-usage.jsonl"
LEDGER_PATH = GOVERNOR_DIR / "agent-ledger.json"
ALERTS_PATH = GOVERNOR_DIR / "cost-alerts.jsonl"
RESERVATIONS_PATH = GOVERNOR_DIR / "reservations.json"

# Thresholds
CIRCUIT_BREAKER_TRIP_PCT = 1.5  # 150% of estimate → trip
ALERT_THRESHOLDS = [0.50, 0.75, 0.90, 1.00]  # % of plan budget

# Browser action budgets (enforced by web_browser.py bridge + tracked here)
BROWSER_BUDGETS = {
    "max_navigations_per_hour": 100,
    "max_clicks_per_task": 50,
    "max_text_extractions_per_hour": 200,
    "max_screenshots_per_hour": 50,
}


# ═══════════════════════════════════════════════════════════════════════════════
# CIRCUIT BREAKER
# ═══════════════════════════════════════════════════════════════════════════════

class CircuitBreaker:
    """Three-state circuit breaker: CLOSED (normal) → OPEN (blocked) → HALF_OPEN (testing).

    Trips when actual cost exceeds 150% of estimated cost.
    HALF_OPEN allows one task to test if costs normalize.
    """

    def __init__(self):
        self.state = "CLOSED"  # CLOSED | OPEN | HALF_OPEN
        self.trip_reason = None
        self.trip_time = None
        self.half_open_task_id = None
        self.trip_count = 0
        self.half_open_remaining = 0

    def check(self, estimated_total, actual_total):
        """Check if breaker should trip.

        Returns: (should_continue: bool, state: str, message: str)
        """
        if estimated_total <= 0:
            return True, self.state, "No estimate — skipping breaker check"

        ratio = actual_total / estimated_total

        if self.state == "OPEN":
            return False, "OPEN", f"Circuit OPEN — actual ${actual_total:.3f} is {ratio:.1f}x estimate ${estimated_total:.3f}. Approval required."

        if self.state == "HALF_OPEN":
            self.half_open_remaining = max(0, self.half_open_remaining - 1)
            if ratio <= 1.0:
                # Cost normalized — reset to CLOSED
                self.state = "CLOSED"
                self.half_open_task_id = None
                self.half_open_remaining = 0
                return True, "CLOSED", f"Circuit recovered — costs normalized ({ratio:.1f}x)"
            elif self.half_open_remaining > 0:
                # Still testing — allow more tasks
                return True, "HALF_OPEN", f"Testing recovery ({self.half_open_remaining} tasks remaining, ratio={ratio:.1f}x)"
            else:
                # All test tasks exhausted, still high — trip again
                self.state = "OPEN"
                self.trip_count += 1
                self.trip_reason = f"HALF_OPEN test failed after all test tasks: {ratio:.1f}x estimate"
                self.trip_time = datetime.now(timezone.utc).isoformat()
                return False, "OPEN", f"Circuit re-tripped — still {ratio:.1f}x after recovery test"

        # CLOSED state — check threshold
        if ratio >= CIRCUIT_BREAKER_TRIP_PCT:
            self.state = "OPEN"
            self.trip_count += 1
            self.trip_reason = f"Actual ${actual_total:.3f} >= {CIRCUIT_BREAKER_TRIP_PCT:.0%} of estimate ${estimated_total:.3f}"
            self.trip_time = datetime.now(timezone.utc).isoformat()
            return False, "OPEN", f"⚡ CIRCUIT BREAKER TRIPPED — actual ${actual_total:.3f} is {ratio:.1f}x estimate ${estimated_total:.3f}"

        return True, "CLOSED", f"OK ({ratio:.1%} of estimate)"

    def attempt_half_open(self, task_id, max_test_tasks=1):
        """Allow N tasks to test recovery before deciding.

        Args:
            task_id: first task to test with
            max_test_tasks: how many tasks can run before re-evaluation (default 1)
        """
        if self.state != "OPEN":
            return False, "Breaker not open"
        self.state = "HALF_OPEN"
        self.half_open_task_id = task_id
        self.half_open_remaining = max_test_tasks
        return True, f"HALF_OPEN — testing with {max_test_tasks} task(s), starting {task_id}"

    def force_close(self, approved_by):
        """Executive override — force breaker closed."""
        self.state = "CLOSED"
        self.trip_reason = None
        self.half_open_task_id = None
        return True, f"Circuit force-closed by {approved_by}"

    def to_dict(self):
        return {
            "state": self.state,
            "trip_reason": self.trip_reason,
            "trip_time": self.trip_time,
            "trip_count": self.trip_count,
            "half_open_task_id": self.half_open_task_id,
            "half_open_remaining": self.half_open_remaining,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT LEDGER
# ═══════════════════════════════════════════════════════════════════════════════

class AgentLedger:
    """Per-agent cumulative cost tracking."""

    def __init__(self):
        self.ledger = {}
        self._load()

    def _load(self):
        GOVERNOR_DIR.mkdir(parents=True, exist_ok=True)
        if LEDGER_PATH.exists():
            try:
                with open(LEDGER_PATH) as f:
                    self.ledger = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.ledger = {}

    def _save(self):
        GOVERNOR_DIR.mkdir(parents=True, exist_ok=True)
        with open(LEDGER_PATH, "w") as f:
            json.dump(self.ledger, f, indent=2)

    def record(self, agent_id, cost, plan_id, task_id, skill):
        """Record a cost entry for an agent."""
        if agent_id not in self.ledger:
            self.ledger[agent_id] = {
                "total_cost_usd": 0.0,
                "task_count": 0,
                "plan_count": set(),
                "last_task": None,
                "entries": [],
            }
            self.ledger[agent_id]["plan_count"] = []

        entry = self.ledger[agent_id]
        entry["total_cost_usd"] = round(entry["total_cost_usd"] + cost, 4)
        entry["task_count"] += 1
        if plan_id not in entry.get("plan_count", []):
            if isinstance(entry.get("plan_count"), list):
                entry["plan_count"].append(plan_id)
            else:
                entry["plan_count"] = [plan_id]
        entry["last_task"] = {
            "task_id": task_id,
            "skill": skill,
            "cost": cost,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        entry["entries"].append({
            "plan_id": plan_id,
            "task_id": task_id,
            "skill": skill,
            "cost": cost,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # Keep only last 100 entries per agent
        if len(entry["entries"]) > 100:
            entry["entries"] = entry["entries"][-100:]

        self._save()

    def record_browser(self, agent_id, action_type, plan_id=None, task_id=None):
        """Record a browser action for an agent.

        Args:
            agent_id: acting agent
            action_type: navigate, click, text, screenshot, fill, etc.
            plan_id: optional plan context
            task_id: optional task context
        """
        if agent_id not in self.ledger:
            self.ledger[agent_id] = {
                "total_cost_usd": 0.0,
                "task_count": 0,
                "plan_count": [],
                "last_task": None,
                "entries": [],
            }

        # Initialize browser tracking if not present
        if "browser_actions" not in self.ledger[agent_id]:
            self.ledger[agent_id]["browser_actions"] = {
                "total": 0,
                "by_type": {},
                "hourly_window_start": None,
                "hourly_counts": {},
            }

        ba = self.ledger[agent_id]["browser_actions"]
        ba["total"] += 1

        # Track by type
        if action_type not in ba["by_type"]:
            ba["by_type"][action_type] = 0
        ba["by_type"][action_type] += 1

        # Track hourly for rate-limited actions
        import time
        now = time.time()
        if ba["hourly_window_start"] is None or now - (ba.get("_hour_epoch", 0)) >= 3600:
            ba["hourly_counts"] = {}
            ba["_hour_epoch"] = now

        if action_type not in ba["hourly_counts"]:
            ba["hourly_counts"][action_type] = 0
        ba["hourly_counts"][action_type] += 1

        self._save()

    def get_browser_usage(self, agent_id):
        """Get browser action usage for an agent.

        Returns: dict with total, by_type, hourly_counts
        """
        agent_data = self.ledger.get(agent_id, {})
        return agent_data.get("browser_actions", {
            "total": 0, "by_type": {}, "hourly_counts": {}
        })

    def check_browser_budget(self, agent_id, action_type):
        """Check if agent is within browser action budget.

        Returns: (allowed: bool, message: str)
        """
        usage = self.get_browser_usage(agent_id)
        hourly = usage.get("hourly_counts", {})

        if action_type == "navigate":
            count = hourly.get("navigate", 0)
            limit = BROWSER_BUDGETS["max_navigations_per_hour"]
            if count >= limit:
                return False, f"{agent_id}: {count}/{limit} navigations/hour exceeded"

        elif action_type == "click":
            count = hourly.get("click", 0)
            limit = BROWSER_BUDGETS["max_clicks_per_task"]
            if count >= limit:
                return False, f"{agent_id}: {count}/{limit} clicks/task exceeded"

        elif action_type == "text":
            count = hourly.get("text", 0)
            limit = BROWSER_BUDGETS["max_text_extractions_per_hour"]
            if count >= limit:
                return False, f"{agent_id}: {count}/{limit} text extractions/hour exceeded"

        elif action_type == "screenshot":
            count = hourly.get("screenshot", 0)
            limit = BROWSER_BUDGETS["max_screenshots_per_hour"]
            if count >= limit:
                return False, f"{agent_id}: {count}/{limit} screenshots/hour exceeded"

        return True, "OK"

    def get_agent_cost(self, agent_id):
        """Get total cost for an agent."""
        return self.ledger.get(agent_id, {}).get("total_cost_usd", 0.0)

    def get_all(self):
        """Get full ledger."""
        return self.ledger

    def summary(self):
        """Print agent cost summary."""
        if not self.ledger:
            print("  No agent cost data yet.")
            return

        print(f"  {'Agent':<25s} {'Total Cost':>10s} {'Tasks':>6s} {'Plans':>6s}")
        print(f"  {'-'*25} {'-'*10} {'-'*6} {'-'*6}")
        for agent_id, data in sorted(self.ledger.items(),
                                      key=lambda x: x[1].get("total_cost_usd", 0),
                                      reverse=True):
            cost = data.get("total_cost_usd", 0)
            tasks = data.get("task_count", 0)
            plans = len(data.get("plan_count", []))
            print(f"  {agent_id:<25s} ${cost:>9.3f} {tasks:>6d} {plans:>6d}")

        # Browser action summary
        has_browser = any("browser_actions" in d for d in self.ledger.values())
        if has_browser:
            print(f"\n  {'Agent':<25s} {'Browser Actions':>15s} {'Nav':>5s} {'Click':>6s} {'Text':>5s}")
            print(f"  {'-'*25} {'-'*15} {'-'*5} {'-'*6} {'-'*5}")
            for agent_id, data in sorted(self.ledger.items()):
                ba = data.get("browser_actions", {})
                total = ba.get("total", 0)
                if total > 0:
                    by_type = ba.get("by_type", {})
                    print(f"  {agent_id:<25s} {total:>15d} "
                          f"{by_type.get('navigate', 0):>5d} "
                          f"{by_type.get('click', 0):>6d} "
                          f"{by_type.get('text', 0):>5d}")


# ═══════════════════════════════════════════════════════════════════════════════
# COST GOVERNOR
# ═══════════════════════════════════════════════════════════════════════════════

class CostGovernor:
    """Real-time cost governance for plan execution.

    Lifecycle:
    1. reserve(plan) — check budget, warn or block
    2. pre_task(task) — check breaker before each task
    3. post_task(task, actual_cost) — track cost, check alerts, update ledger
    4. release(plan) — release unused reservation
    """

    def __init__(self, plan_id=None, estimated_total=0.0):
        self.plan_id = plan_id
        self.estimated_total = estimated_total
        self.actual_total = 0.0
        self.task_costs = {}  # task_id → actual cost
        self.breaker = CircuitBreaker()
        self.ledger = AgentLedger()
        self.alerts_fired = set()  # threshold values already fired
        self.reservation_warned = False
        self.reservation_blocked = False

        GOVERNOR_DIR.mkdir(parents=True, exist_ok=True)

    def _get_remaining_budget(self):
        """Get total remaining budget across all providers."""
        try:
            import yaml
            with open(REPO / "config" / "routing" / "budget-config.yaml") as f:
                bcfg = yaml.safe_load(f)
            with open(SPEND_PATH) as f:
                spend = json.load(f)

            total_remaining = 0.0
            for provider in ["anthropic", "openai", "google"]:
                budget = bcfg["budgets"][provider]["total_usd"]
                spent = spend.get(provider, {})
                if isinstance(spent, dict):
                    spent = spent.get("cumulative_spend_usd", 0)
                total_remaining += max(0, budget - spent)
            return total_remaining
        except Exception:
            return 999.0  # fail open

    def _get_task_actual_cost(self):
        """Read actual cost of most recent task from usage log."""
        if not USAGE_PATH.exists():
            return 0.0

        try:
            # Read last few lines of usage log
            with open(USAGE_PATH) as f:
                lines = f.readlines()

            if not lines:
                return 0.0

            # Sum costs from last batch (same approximate timestamp)
            total = 0.0
            cutoff = time.time() - 120  # last 2 minutes

            for line in reversed(lines[-20:]):
                try:
                    entry = json.loads(line.strip())
                    ts = entry.get("timestamp", "")
                    cost = entry.get("estimated_cost_usd", 0)
                    total += cost
                except (json.JSONDecodeError, KeyError):
                    continue

            return total
        except Exception:
            return 0.0

    def reserve(self, estimated_cost):
        """Reserve budget for a plan.

        Behavior: warn first time, hard block second time.
        Returns: (allowed: bool, message: str)
        """
        self.estimated_total = estimated_cost
        remaining = self._get_remaining_budget()

        if estimated_cost > remaining:
            if not self.reservation_warned:
                # First time — warn but allow
                self.reservation_warned = True
                self._log_alert("RESERVATION_WARN",
                                f"Plan ${estimated_cost:.2f} may exceed remaining ${remaining:.2f}")
                return True, f"⚠️  Budget warning: plan estimates ${estimated_cost:.2f} but only ${remaining:.2f} remaining. Proceeding with caution."

            else:
                # Second time — hard block
                self.reservation_blocked = True
                self._log_alert("RESERVATION_BLOCK",
                                f"Plan ${estimated_cost:.2f} blocked — insufficient remaining ${remaining:.2f}")
                return False, f"❌ Budget BLOCKED: plan ${estimated_cost:.2f} exceeds remaining ${remaining:.2f}. Increase budget or reduce plan scope."

        return True, f"✅ Budget reserved: ${estimated_cost:.2f} of ${remaining:.2f} remaining"

    def pre_task(self, task):
        """Check if task should execute. Applies per-task risk_factor.

        risk_factor (in task dict): multiplier on breaker threshold.
          1.0 = normal, 0.5 = trip at half threshold (high-risk), 2.0 = more tolerance.

        Returns: (allowed: bool, message: str)
        """
        risk_factor = task.get("risk_factor", 1.0)

        # Adjust effective threshold for this task
        effective_threshold = CIRCUIT_BREAKER_TRIP_PCT * risk_factor
        effective_estimate = self.estimated_total * risk_factor if risk_factor > 0 else self.estimated_total

        can_continue, state, msg = self.breaker.check(effective_estimate, self.actual_total)

        if not can_continue:
            return False, f"{msg} (risk_factor={risk_factor})"

        return True, f"OK — breaker {state} (risk_factor={risk_factor})"

    def post_task(self, task, actual_cost=None):
        """Record task cost and check alerts.

        Args:
            task: task dict from plan
            actual_cost: override cost (if None, reads from usage log)

        Returns: (alerts: list[str])
        """
        if actual_cost is None:
            actual_cost = task.get("estimated_cost_usd", 0.15)

        self.actual_total = round(self.actual_total + actual_cost, 4)
        self.task_costs[task["id"]] = actual_cost

        # Update agent ledger
        self.ledger.record(
            agent_id=task.get("assigned_to", "unknown"),
            cost=actual_cost,
            plan_id=self.plan_id,
            task_id=task["id"],
            skill=task.get("skill", "unknown"),
        )

        # Check threshold alerts
        alerts = []
        if self.estimated_total > 0:
            ratio = self.actual_total / self.estimated_total
            for threshold in ALERT_THRESHOLDS:
                if ratio >= threshold and threshold not in self.alerts_fired:
                    self.alerts_fired.add(threshold)
                    alert_msg = f"Cost alert: {threshold:.0%} of plan budget used (${self.actual_total:.3f} / ${self.estimated_total:.3f})"
                    alerts.append(alert_msg)
                    self._log_alert(f"THRESHOLD_{int(threshold*100)}", alert_msg)

        # Check breaker
        can_continue, state, breaker_msg = self.breaker.check(self.estimated_total, self.actual_total)
        if not can_continue:
            alerts.append(breaker_msg)
            self._log_to_decision_system("circuit_breaker_trip", breaker_msg, task)

        # Log significant cost events to decision system
        if self.estimated_total > 0 and self.actual_total / self.estimated_total >= 1.0:
            self._log_to_decision_system("budget_overrun",
                f"Plan {self.plan_id}: actual ${self.actual_total:.3f} exceeded estimate ${self.estimated_total:.3f}",
                task)

        return alerts

    def release(self):
        """Release budget reservation and return summary.

        Returns: dict with cost summary
        """
        summary = {
            "plan_id": self.plan_id,
            "estimated_total": self.estimated_total,
            "actual_total": self.actual_total,
            "tasks_tracked": len(self.task_costs),
            "overrun": self.actual_total > self.estimated_total,
            "overrun_pct": round((self.actual_total / self.estimated_total - 1) * 100, 1) if self.estimated_total > 0 else 0,
            "breaker_state": self.breaker.state,
            "breaker_trips": self.breaker.trip_count,
            "alerts_fired": list(self.alerts_fired),
            "per_task": self.task_costs,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Save to governance dir
        summary_path = GOVERNOR_DIR / f"cost-report-{self.plan_id}.json"
        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2)

        return summary

    def _log_to_decision_system(self, event_type, message, task=None):
        """Log cost governance events to MA-4 decision log."""
        try:
            from scripts.decision_log import DecisionLog
            dl = DecisionLog()
            title = f"Cost governance: {event_type}"
            description = (
                f"{message}\n"
                f"Plan: {self.plan_id}\n"
                f"Estimated: ${self.estimated_total:.3f}\n"
                f"Actual: ${self.actual_total:.3f}\n"
                f"Breaker: {self.breaker.state}\n"
            )
            if task:
                description += (
                    f"Task: {task.get('id', '?')} ({task.get('skill', '?')})\n"
                    f"Agent: {task.get('assigned_to', '?')}\n"
                    f"Task cost: ${task.get('estimated_cost_usd', 0):.3f}\n"
                )
            dec_id, _ = dl.propose("executive_operator", title, description,
                                    reversibility="irreversible", confidence=0.9)
            dl.decide(dec_id, f"Auto-logged: {event_type}", message,
                     decided_by="executive_operator")
        except Exception:
            pass  # Don't let decision log failures block cost governance

    def _log_alert(self, alert_type, message):
        """Append alert to alerts log."""
        GOVERNOR_DIR.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "plan_id": self.plan_id,
            "alert_type": alert_type,
            "message": message,
            "actual_total": self.actual_total,
            "estimated_total": self.estimated_total,
            "breaker_state": self.breaker.state,
        }
        with open(ALERTS_PATH, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def status(self):
        """Print current governor status."""
        print(f"  Plan: {self.plan_id}")
        print(f"  Estimated: ${self.estimated_total:.3f}")
        print(f"  Actual: ${self.actual_total:.3f}")
        if self.estimated_total > 0:
            print(f"  Ratio: {self.actual_total / self.estimated_total:.1%}")
        print(f"  Breaker: {self.breaker.state}")
        print(f"  Trips: {self.breaker.trip_count}")
        print(f"  Tasks tracked: {len(self.task_costs)}")
        print(f"  Alerts fired: {sorted(self.alerts_fired)}")


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS
# ═══════════════════════════════════════════════════════════════════════════════

def run_tests():
    print("=" * 60)
    print("  MA-6 Cost Governance Tests")
    print("=" * 60)

    tests_passed = 0
    tests_total = 0

    def test(name, condition, detail=""):
        nonlocal tests_passed, tests_total
        tests_total += 1
        if condition:
            tests_passed += 1
            print(f"  ✅ {name}")
        else:
            print(f"  ❌ {name}: {detail}")

    # Test 1: Circuit breaker — stays closed under threshold
    cb = CircuitBreaker()
    ok, state, _ = cb.check(1.0, 0.5)
    test("Breaker stays CLOSED at 50%", ok and state == "CLOSED")

    # Test 2: Circuit breaker — stays closed at 149%
    ok, state, _ = cb.check(1.0, 1.49)
    test("Breaker stays CLOSED at 149%", ok and state == "CLOSED")

    # Test 3: Circuit breaker — trips at 150%
    cb2 = CircuitBreaker()
    ok, state, msg = cb2.check(1.0, 1.50)
    test("Breaker TRIPS at 150%", not ok and state == "OPEN", msg)

    # Test 4: Circuit breaker — blocked when OPEN
    ok, state, msg = cb2.check(1.0, 1.50)
    test("Breaker blocks when OPEN", not ok and state == "OPEN")

    # Test 5: Half-open allows one task (default)
    ok, msg = cb2.attempt_half_open("task_test")
    test("Half-open allowed", ok and cb2.state == "HALF_OPEN")

    # Test 6: Half-open recovers if costs normalize
    ok, state, _ = cb2.check(1.0, 0.8)
    test("Half-open recovers at 80%", ok and state == "CLOSED")

    # Test 7: Half-open re-trips if still high
    cb3 = CircuitBreaker()
    cb3.check(1.0, 1.6)  # trip
    cb3.attempt_half_open("task_x")
    ok, state, _ = cb3.check(1.0, 1.5)
    test("Half-open re-trips if still high", not ok and state == "OPEN")

    # Test 8: Force close
    ok, msg = cb3.force_close("executive_operator")
    test("Force close works", ok and cb3.state == "CLOSED")

    # Test 9: Budget reservation — warn first
    gov = CostGovernor("test_plan", 100.0)
    # Mock remaining budget to be low
    gov._get_remaining_budget = lambda: 5.0
    allowed, msg = gov.reserve(10.0)
    test("Reservation warns first", allowed and "warning" in msg.lower(), msg)

    # Test 10: Budget reservation — block second time
    allowed, msg = gov.reserve(10.0)
    test("Reservation blocks second time", not allowed and "BLOCK" in msg, msg)

    # Test 11: Post-task tracking
    gov2 = CostGovernor("test_plan_2", 1.0)
    task = {"id": "t1", "assigned_to": "strategy_lead", "skill": "e12-market-research-analyst", "estimated_cost_usd": 0.15}
    alerts = gov2.post_task(task, actual_cost=0.15)
    test("Post-task tracks cost", gov2.actual_total == 0.15)

    # Test 12: Threshold alert at 50%
    task2 = {"id": "t2", "assigned_to": "strategy_lead", "skill": "e12-tech-trend-scanner", "estimated_cost_usd": 0.4}
    alerts = gov2.post_task(task2, actual_cost=0.40)
    test("50% alert fires", 0.50 in gov2.alerts_fired, str(gov2.alerts_fired))

    # Test 13: Agent ledger records (check delta, not absolute — ledger persists)
    ledger = gov2.ledger
    cost = ledger.get_agent_cost("strategy_lead")
    test("Agent ledger tracks cost", cost >= 0.55, f"${cost} (>= $0.55)")

    # Test 14: Release returns summary
    summary = gov2.release()
    test("Release returns summary", summary["actual_total"] == 0.55 and summary["tasks_tracked"] == 2)

    # Test 15: Trip count tracking
    cb4 = CircuitBreaker()
    cb4.check(1.0, 1.5)  # trip 1
    cb4.force_close("exec")
    cb4.check(1.0, 1.6)  # trip 2
    test("Trip count tracks", cb4.trip_count == 2, f"trips={cb4.trip_count}")

    # Test 16: Per-task risk factor (high-risk trips earlier)
    gov_risk = CostGovernor("risk_test", 1.0)
    gov_risk.actual_total = 0.8  # 80% normally OK, but risk_factor=0.5 → effective=0.5 → 0.8/0.5=160% → trips
    high_risk_task = {"id": "t_hr", "risk_factor": 0.5, "assigned_to": "strategy_lead", "skill": "test", "estimated_cost_usd": 0.1}
    ok, msg = gov_risk.pre_task(high_risk_task)
    test("High risk_factor=0.5 trips at 80%", not ok, msg)

    # Test 17: Normal risk passes at 70%
    normal_task = {"id": "t_nr", "risk_factor": 1.0, "assigned_to": "strategy_lead", "skill": "test", "estimated_cost_usd": 0.1}
    gov_risk2 = CostGovernor("risk_test2", 1.0)
    gov_risk2.actual_total = 0.7
    ok, msg = gov_risk2.pre_task(normal_task)
    test("Normal risk_factor=1.0 OK at 70%", ok, msg)

    # Test 18: Multi-task half-open recovery
    cb_multi = CircuitBreaker()
    cb_multi.check(1.0, 1.6)  # trip
    cb_multi.attempt_half_open("task_m1", max_test_tasks=3)
    ok1, state1, _ = cb_multi.check(1.0, 1.3)  # still high but has remaining
    ok2, state2, _ = cb_multi.check(1.0, 1.2)  # second test
    test("Multi half-open allows 2 tasks", ok1 and ok2 and state2 == "HALF_OPEN")

    # Test 19: Zero estimate doesn't crash
    cb5 = CircuitBreaker()
    ok, state, _ = cb5.check(0, 0.5)
    test("Zero estimate safe", ok)

    # ── Browser Budget Tests ──

    # Test: Browser budgets defined
    test("Browser budgets defined", len(BROWSER_BUDGETS) == 4)

    # Test: Record browser action
    ledger_b = AgentLedger()
    initial_total = ledger_b.get_browser_usage("test_browser_agent").get("total", 0)
    ledger_b.record_browser("test_browser_agent", "navigate", "plan_b1", "task_b1")
    usage = ledger_b.get_browser_usage("test_browser_agent")
    test("Browser action recorded", usage["total"] == initial_total + 1)
    test("Browser action typed", usage["by_type"].get("navigate", 0) >= 1)

    # Test: Multiple action types tracked
    ledger_b.record_browser("test_browser_agent", "click", "plan_b1", "task_b1")
    ledger_b.record_browser("test_browser_agent", "text", "plan_b1", "task_b1")
    usage2 = ledger_b.get_browser_usage("test_browser_agent")
    test("Multiple browser types tracked",
         usage2["by_type"].get("click", 0) >= 1 and usage2["by_type"].get("text", 0) >= 1)

    # Test: Budget check — within limits
    allowed, msg = ledger_b.check_browser_budget("test_browser_agent", "navigate")
    test("Browser budget: navigate within limit", allowed)

    # Test: Budget check — exceeded (simulate)
    ledger_b2 = AgentLedger()
    if "test_exceeded_agent" not in ledger_b2.ledger:
        ledger_b2.ledger["test_exceeded_agent"] = {
            "total_cost_usd": 0.0, "task_count": 0, "plan_count": [],
            "last_task": None, "entries": [],
            "browser_actions": {
                "total": 100, "by_type": {"navigate": 100},
                "hourly_window_start": None, "hourly_counts": {"navigate": 100},
                "_hour_epoch": __import__("time").time(),
            }
        }
        ledger_b2._save()
    allowed, msg = ledger_b2.check_browser_budget("test_exceeded_agent", "navigate")
    test("Browser budget: navigate exceeded blocked", not allowed and "exceeded" in msg, msg)

    # Test: Click budget check
    allowed_click, _ = ledger_b.check_browser_budget("test_browser_agent", "click")
    test("Browser budget: click within limit", allowed_click)

    # Test: Text budget check
    allowed_text, _ = ledger_b.check_browser_budget("test_browser_agent", "text")
    test("Browser budget: text within limit", allowed_text)

    # Test: Screenshot budget check
    allowed_ss, _ = ledger_b.check_browser_budget("test_browser_agent", "screenshot")
    test("Browser budget: screenshot within limit", allowed_ss)

    print(f"\n  Results: {tests_passed}/{tests_total} passed")
    return tests_passed == tests_total


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="NemoClaw Cost Governor")
    parser.add_argument("--test", action="store_true", help="Run all tests")
    parser.add_argument("--status", action="store_true", help="Show governor status")
    parser.add_argument("--ledger", action="store_true", help="Show per-agent cost ledger")
    parser.add_argument("--alerts", action="store_true", help="Show recent cost alerts")
    parser.add_argument("--remaining", action="store_true", help="Show remaining budget")
    args = parser.parse_args()

    if args.test:
        success = run_tests()
        sys.exit(0 if success else 1)

    elif args.ledger:
        ledger = AgentLedger()
        ledger.summary()

    elif args.alerts:
        if ALERTS_PATH.exists():
            with open(ALERTS_PATH) as f:
                for line in f:
                    try:
                        alert = json.loads(line.strip())
                        ts = alert.get("timestamp", "?")[:19]
                        print(f"  [{ts}] {alert.get('alert_type')}: {alert.get('message')}")
                    except json.JSONDecodeError:
                        continue
        else:
            print("  No alerts yet.")

    elif args.remaining:
        gov = CostGovernor()
        remaining = gov._get_remaining_budget()
        print(f"  Total remaining budget: ${remaining:.2f}")

    elif args.status:
        print("  Cost Governor Status:")
        print(f"  Alerts log: {ALERTS_PATH}")
        print(f"  Agent ledger: {LEDGER_PATH}")
        print(f"  Reservations: {RESERVATIONS_PATH}")

        gov = CostGovernor()
        remaining = gov._get_remaining_budget()
        print(f"  Total remaining: ${remaining:.2f}")

        # Show recent reports
        reports = sorted(GOVERNOR_DIR.glob("cost-report-*.json"), reverse=True)[:5]
        if reports:
            print(f"\n  Recent cost reports:")
            for rp in reports:
                with open(rp) as f:
                    data = json.load(f)
                est = data.get("estimated_total", 0)
                act = data.get("actual_total", 0)
                overrun = data.get("overrun_pct", 0)
                print(f"    {rp.stem}: est=${est:.3f} actual=${act:.3f} overrun={overrun:.1f}%")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
