#!/usr/bin/env python3
"""
NemoClaw Agent Performance Metrics v1.0 (MA-12)

Unified performance tracking across 5 dimensions:
- Quality: peer review scores, decision outcomes
- Speed: task completion time, decision velocity
- Cost Efficiency: actual vs estimated cost
- Reliability: failure rate, recovery rate (with recovery credit)
- Compliance: behavior violations, role adherence

Features:
- Role-specific dimension weights (CSO vs CTO vs CEO)
- Configurable weights per organization goal
- Graduated alerts: watch (65%) → warning (50%) → critical (35%)
- Minimum sample threshold for normalization (avoids low-N skew)
- Decision accuracy: confidence vs outcome tracking from MA-4
- Recovery credit: agents who recover from failures get partial credit
- Trend tracking over configurable time windows
- Composite score with ranking

Usage:
  python3 scripts/agent_performance.py --test
  python3 scripts/agent_performance.py --dashboard
  python3 scripts/agent_performance.py --agent strategy_lead
  python3 scripts/agent_performance.py --rankings
  python3 scripts/agent_performance.py --alerts
"""

import argparse
import json
import os
import sys
import uuid
import yaml
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict

REPO = Path.home() / "nemoclaw-local-foundation"
PERF_DIR = Path.home() / ".nemoclaw" / "performance"
METRICS_PATH = PERF_DIR / "agent-metrics.json"
HISTORY_PATH = PERF_DIR / "metrics-history.jsonl"
ALERTS_PATH = PERF_DIR / "performance-alerts.jsonl"

MIN_SAMPLE_THRESHOLD = 3  # minimum events before scoring a dimension

# ═══════════════════════════════════════════════════════════════════════════════
# ROLE-SPECIFIC DIMENSION WEIGHTS
# ═══════════════════════════════════════════════════════════════════════════════

ROLE_WEIGHTS = {
    "strategy_lead": {
        "quality": 0.35, "speed": 0.10, "cost_efficiency": 0.15,
        "reliability": 0.20, "compliance": 0.20,
    },
    "product_architect": {
        "quality": 0.30, "speed": 0.15, "cost_efficiency": 0.15,
        "reliability": 0.20, "compliance": 0.20,
    },
    "growth_revenue_lead": {
        "quality": 0.25, "speed": 0.20, "cost_efficiency": 0.25,
        "reliability": 0.15, "compliance": 0.15,
    },
    "narrative_content_lead": {
        "quality": 0.40, "speed": 0.20, "cost_efficiency": 0.10,
        "reliability": 0.15, "compliance": 0.15,
    },
    "engineering_lead": {
        "quality": 0.25, "speed": 0.15, "cost_efficiency": 0.15,
        "reliability": 0.30, "compliance": 0.15,
    },
    "operations_lead": {
        "quality": 0.15, "speed": 0.25, "cost_efficiency": 0.25,
        "reliability": 0.25, "compliance": 0.10,
    },
    "executive_operator": {
        "quality": 0.25, "speed": 0.15, "cost_efficiency": 0.15,
        "reliability": 0.20, "compliance": 0.25,
    },
}

DEFAULT_WEIGHTS = {
    "quality": 0.25, "speed": 0.20, "cost_efficiency": 0.15,
    "reliability": 0.20, "compliance": 0.20,
}

# Organization goal overrides (applied on top of role weights)
ORG_GOAL_PROFILES = {
    "speed_critical": {"speed": 1.5, "quality": 0.8},  # multipliers
    "quality_critical": {"quality": 1.5, "speed": 0.8},
    "cost_critical": {"cost_efficiency": 1.5, "quality": 0.9},
    "reliability_critical": {"reliability": 1.5, "speed": 0.8},
    "balanced": {},  # no adjustments
}

# ═══════════════════════════════════════════════════════════════════════════════
# GRADUATED ALERT THRESHOLDS
# ═══════════════════════════════════════════════════════════════════════════════

ALERT_LEVELS = {
    "watch": {
        "composite_below": 0.65,
        "dimension_below": 0.50,
        "description": "Performance declining — monitor closely",
        "severity": "info",
    },
    "warning": {
        "composite_below": 0.50,
        "dimension_below": 0.35,
        "description": "Significant underperformance — intervention needed",
        "severity": "warn",
    },
    "critical": {
        "composite_below": 0.35,
        "dimension_below": 0.20,
        "description": "Critical underperformance — immediate action required",
        "severity": "critical",
    },
}

# Per-dimension custom thresholds
DIMENSION_ALERT_OVERRIDES = {
    "reliability": {"watch": 0.70, "warning": 0.50, "critical": 0.30},
    "compliance": {"watch": 0.75, "warning": 0.55, "critical": 0.35},
}

# ═══════════════════════════════════════════════════════════════════════════════
# RAW METRICS COLLECTOR
# ═══════════════════════════════════════════════════════════════════════════════

class MetricsCollector:
    """Collects raw performance events per agent."""

    def __init__(self):
        self.events = defaultdict(lambda: defaultdict(list))
        # events[agent_id][dimension] = [{value, timestamp, source, metadata}]

    def record(self, agent_id, dimension, value, source="manual", metadata=None):
        """Record a performance event.

        Args:
            agent_id: which agent
            dimension: quality|speed|cost_efficiency|reliability|compliance
            value: 0.0-1.0 normalized score
            source: which MA system produced this event
            metadata: optional context
        """
        self.events[agent_id][dimension].append({
            "value": max(0.0, min(1.0, value)),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "metadata": metadata or {},
        })

    # ── QUALITY EVENTS ──

    def record_review_score(self, agent_id, score, max_score=10.0):
        """Record from MA-11 peer review (normalized to 0-1)."""
        normalized = score / max_score
        self.record(agent_id, "quality", normalized, "MA-11",
                     {"raw_score": score, "max": max_score})

    def record_decision_outcome(self, agent_id, outcome_score, max_score=10.0,
                                  confidence=None, predicted_score=None):
        """Record from MA-4 decision evaluation.

        Includes decision accuracy: how close was confidence to actual outcome.
        """
        normalized = outcome_score / max_score
        metadata = {"raw_score": outcome_score}

        # Decision accuracy: compare confidence to outcome
        if confidence is not None and predicted_score is not None:
            predicted_norm = predicted_score / max_score
            accuracy = 1.0 - abs(confidence - predicted_norm)
            metadata["confidence"] = confidence
            metadata["predicted"] = predicted_norm
            metadata["decision_accuracy"] = round(accuracy, 3)
            # Blend outcome quality with prediction accuracy
            normalized = 0.7 * normalized + 0.3 * accuracy

        self.record(agent_id, "quality", normalized, "MA-4", metadata)

    # ── SPEED EVENTS ──

    def record_task_duration(self, agent_id, duration_s, expected_s=300):
        """Record from MA-5 task completion."""
        # Faster = better. Score = expected/actual (capped at 1.0)
        if duration_s <= 0:
            duration_s = 1
        speed_score = min(1.0, expected_s / duration_s)
        self.record(agent_id, "speed", speed_score, "MA-5",
                     {"duration_s": duration_s, "expected_s": expected_s})

    def record_decision_velocity(self, agent_id, time_to_decision_s, target_s=600):
        """Record from MA-4 decision velocity."""
        if time_to_decision_s <= 0:
            time_to_decision_s = 1
        speed_score = min(1.0, target_s / time_to_decision_s)
        self.record(agent_id, "speed", speed_score, "MA-4",
                     {"time_s": time_to_decision_s, "target_s": target_s})

    # ── COST EFFICIENCY EVENTS ──

    def record_cost_efficiency(self, agent_id, actual_cost, estimated_cost):
        """Record from MA-6 cost tracking."""
        if estimated_cost <= 0:
            estimated_cost = 0.01
        # Under budget = good. Score = estimated/actual (capped at 1.0)
        efficiency = min(1.0, estimated_cost / max(actual_cost, 0.001))
        self.record(agent_id, "cost_efficiency", efficiency, "MA-6",
                     {"actual": actual_cost, "estimated": estimated_cost})

    # ── RELIABILITY EVENTS ──

    def record_task_success(self, agent_id):
        """Record successful task completion."""
        self.record(agent_id, "reliability", 1.0, "MA-5", {"outcome": "success"})

    def record_task_failure(self, agent_id, recovered=False):
        """Record task failure with recovery credit.

        recovered=True gives partial credit (0.5) instead of 0.
        """
        score = 0.5 if recovered else 0.0
        self.record(agent_id, "reliability", score, "MA-9",
                     {"outcome": "recovered" if recovered else "failed",
                      "recovery_credit": recovered})

    def record_recovery(self, agent_id, recovery_outcome):
        """Record from MA-9 failure recovery.

        Outcomes: recovered (0.7), fallback_used (0.5), escalated (0.3), failed (0.0)
        """
        scores = {"recovered": 0.7, "fallback_used": 0.5, "escalated": 0.3, "failed": 0.0}
        score = scores.get(recovery_outcome, 0.0)
        self.record(agent_id, "reliability", score, "MA-9",
                     {"recovery_outcome": recovery_outcome})

    # ── COMPLIANCE EVENTS ──

    def record_compliance_pass(self, agent_id):
        """Record clean behavior check."""
        self.record(agent_id, "compliance", 1.0, "MA-8", {"outcome": "pass"})

    def record_compliance_violation(self, agent_id, severity="warn"):
        """Record behavior violation from MA-8."""
        scores = {"warn": 0.5, "block": 0.2, "escalate": 0.0}
        score = scores.get(severity, 0.3)
        self.record(agent_id, "compliance", score, "MA-8",
                     {"outcome": "violation", "severity": severity})

    def get_events(self, agent_id, dimension=None, since=None):
        """Get events for an agent, optionally filtered."""
        if dimension:
            events = self.events.get(agent_id, {}).get(dimension, [])
        else:
            events = []
            for dim_events in self.events.get(agent_id, {}).values():
                events.extend(dim_events)

        if since:
            events = [e for e in events if e["timestamp"] >= since]

        return events

    def get_all_agents(self):
        """Get all agent IDs with recorded events."""
        return list(self.events.keys())


# ═══════════════════════════════════════════════════════════════════════════════
# PERFORMANCE SCORER
# ═══════════════════════════════════════════════════════════════════════════════

class PerformanceScorer:
    """Computes per-agent scores with normalization and weighting."""

    def __init__(self, collector, org_goal="balanced"):
        self.collector = collector
        self.org_goal = org_goal
        self._goal_multipliers = ORG_GOAL_PROFILES.get(org_goal, {})

    def score_dimension(self, agent_id, dimension):
        """Score a single dimension (0.0-1.0).

        Returns: (score, sample_count, is_sufficient)
        """
        events = self.collector.get_events(agent_id, dimension)
        if not events:
            return None, 0, False

        values = [e["value"] for e in events]
        count = len(values)
        is_sufficient = count >= MIN_SAMPLE_THRESHOLD

        # Simple average (could be weighted by recency later)
        avg = sum(values) / count
        return round(avg, 3), count, is_sufficient

    def score_agent(self, agent_id, custom_weights=None):
        """Compute composite score for an agent.

        Args:
            custom_weights: override role weights

        Returns: dict with per-dimension + composite scores
        """
        # Get weights
        weights = custom_weights or ROLE_WEIGHTS.get(agent_id, DEFAULT_WEIGHTS).copy()

        # Apply org goal multipliers
        for dim, multiplier in self._goal_multipliers.items():
            if dim in weights:
                weights[dim] *= multiplier

        # Normalize weights to sum to 1.0
        total_weight = sum(weights.values())
        if total_weight > 0:
            weights = {k: v / total_weight for k, v in weights.items()}

        dimensions = {}
        composite_parts = []
        insufficient_dimensions = []

        for dim in ["quality", "speed", "cost_efficiency", "reliability", "compliance"]:
            score, count, sufficient = self.score_dimension(agent_id, dim)

            dimensions[dim] = {
                "score": score,
                "sample_count": count,
                "sufficient": sufficient,
                "weight": round(weights.get(dim, 0.2), 3),
            }

            if score is not None:
                if sufficient:
                    composite_parts.append((score, weights.get(dim, 0.2)))
                else:
                    insufficient_dimensions.append(dim)
                    # Use score but flag as low-confidence
                    composite_parts.append((score, weights.get(dim, 0.2) * 0.5))

        # Composite score
        if composite_parts:
            total_w = sum(w for _, w in composite_parts)
            composite = sum(s * w for s, w in composite_parts) / total_w if total_w > 0 else 0
        else:
            composite = None

        return {
            "agent_id": agent_id,
            "composite_score": round(composite, 3) if composite is not None else None,
            "dimensions": dimensions,
            "insufficient_dimensions": insufficient_dimensions,
            "weights_used": weights,
            "org_goal": self.org_goal,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def rank_agents(self, agents=None):
        """Rank all agents by composite score.

        Returns: sorted list of (agent_id, composite_score, rank)
        """
        if agents is None:
            agents = self.collector.get_all_agents()

        scores = []
        for agent_id in agents:
            result = self.score_agent(agent_id)
            composite = result.get("composite_score")
            if composite is not None:
                scores.append((agent_id, composite, result))

        scores.sort(key=lambda x: -x[1])

        ranked = []
        for rank, (agent_id, score, result) in enumerate(scores, 1):
            ranked.append({
                "rank": rank,
                "agent_id": agent_id,
                "composite_score": score,
                "dimensions": {d: v["score"] for d, v in result["dimensions"].items()},
            })

        return ranked


# ═══════════════════════════════════════════════════════════════════════════════
# ALERT SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

class AlertSystem:
    """Graduated performance alerts."""

    def __init__(self, scorer):
        self.scorer = scorer
        self.fired = []

    def check_agent(self, agent_id):
        """Check an agent against all alert thresholds.

        Returns: list of alerts [{level, dimension, score, threshold, message}]
        """
        result = self.scorer.score_agent(agent_id)
        alerts = []
        composite = result.get("composite_score")

        # Check composite score
        if composite is not None:
            for level_name, level_def in sorted(ALERT_LEVELS.items(),
                                                  key=lambda x: x[1]["composite_below"]):
                if composite < level_def["composite_below"]:
                    alert = {
                        "level": level_name,
                        "agent": agent_id,
                        "dimension": "composite",
                        "score": composite,
                        "threshold": level_def["composite_below"],
                        "message": f"{agent_id} composite {composite:.0%} below {level_name} threshold {level_def['composite_below']:.0%}",
                        "severity": level_def["severity"],
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    alerts.append(alert)
                    break  # only fire highest severity

        # Check individual dimensions
        for dim, dim_data in result.get("dimensions", {}).items():
            score = dim_data.get("score")
            if score is None:
                continue

            # Use dimension-specific override or default
            overrides = DIMENSION_ALERT_OVERRIDES.get(dim, {})

            for level_name in ["critical", "warning", "watch"]:
                threshold = overrides.get(level_name,
                                           ALERT_LEVELS[level_name]["dimension_below"])
                if score < threshold:
                    alert = {
                        "level": level_name,
                        "agent": agent_id,
                        "dimension": dim,
                        "score": score,
                        "threshold": threshold,
                        "message": f"{agent_id} {dim} {score:.0%} below {level_name} threshold {threshold:.0%}",
                        "severity": ALERT_LEVELS[level_name]["severity"],
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    alerts.append(alert)
                    break  # only fire highest severity per dimension

        self.fired.extend(alerts)
        self._log_alerts(alerts)
        return alerts

    def check_all(self, agents):
        """Check all agents for alerts.

        Returns: dict of agent_id → alerts
        """
        all_alerts = {}
        for agent_id in agents:
            alerts = self.check_agent(agent_id)
            if alerts:
                all_alerts[agent_id] = alerts
        return all_alerts

    def _log_alerts(self, alerts):
        """Persist alerts to disk."""
        if not alerts:
            return
        PERF_DIR.mkdir(parents=True, exist_ok=True)
        with open(ALERTS_PATH, "a") as f:
            for alert in alerts:
                f.write(json.dumps(alert) + "\n")


# ═══════════════════════════════════════════════════════════════════════════════
# TREND TRACKER
# ═══════════════════════════════════════════════════════════════════════════════

class TrendTracker:
    """Tracks performance trends over time windows."""

    def __init__(self, scorer):
        self.scorer = scorer

    def snapshot(self, agents):
        """Take a point-in-time snapshot of all agent scores.

        Returns: snapshot dict
        """
        snapshot = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agents": {},
        }
        for agent_id in agents:
            result = self.scorer.score_agent(agent_id)
            snapshot["agents"][agent_id] = {
                "composite": result.get("composite_score"),
                "dimensions": {d: v["score"] for d, v in result["dimensions"].items()},
            }

        # Persist
        PERF_DIR.mkdir(parents=True, exist_ok=True)
        with open(HISTORY_PATH, "a") as f:
            f.write(json.dumps(snapshot) + "\n")

        return snapshot

    def get_trend(self, agent_id, last_n=10):
        """Get recent trend for an agent.

        Returns: list of {timestamp, composite, dimensions}
        """
        if not HISTORY_PATH.exists():
            return []

        entries = []
        with open(HISTORY_PATH) as f:
            for line in f:
                try:
                    snap = json.loads(line.strip())
                    if agent_id in snap.get("agents", {}):
                        agent_data = snap["agents"][agent_id]
                        entries.append({
                            "timestamp": snap["timestamp"],
                            "composite": agent_data.get("composite"),
                            "dimensions": agent_data.get("dimensions", {}),
                        })
                except json.JSONDecodeError:
                    continue

        return entries[-last_n:]

    def compute_direction(self, agent_id, last_n=5):
        """Compute trend direction: improving, declining, stable.

        Returns: (direction, delta)
        """
        trend = self.get_trend(agent_id, last_n)
        if len(trend) < 2:
            return "insufficient_data", 0.0

        composites = [t["composite"] for t in trend if t["composite"] is not None]
        if len(composites) < 2:
            return "insufficient_data", 0.0

        first_half = sum(composites[:len(composites)//2]) / (len(composites)//2)
        second_half = sum(composites[len(composites)//2:]) / (len(composites) - len(composites)//2)
        delta = round(second_half - first_half, 3)

        if delta > 0.05:
            return "improving", delta
        elif delta < -0.05:
            return "declining", delta
        else:
            return "stable", delta


# ═══════════════════════════════════════════════════════════════════════════════
# PERFORMANCE MANAGER (main interface)
# ═══════════════════════════════════════════════════════════════════════════════

class PerformanceManager:
    """Top-level interface for agent performance tracking."""

    def __init__(self, org_goal="balanced"):
        self.collector = MetricsCollector()
        self.scorer = PerformanceScorer(self.collector, org_goal)
        self.alerts = AlertSystem(self.scorer)
        self.trends = TrendTracker(self.scorer)

    def get_agent_report(self, agent_id):
        """Full performance report for one agent."""
        score = self.scorer.score_agent(agent_id)
        alerts = self.alerts.check_agent(agent_id)
        direction, delta = self.trends.compute_direction(agent_id)

        return {
            "agent_id": agent_id,
            "composite_score": score.get("composite_score"),
            "dimensions": score.get("dimensions"),
            "weights": score.get("weights_used"),
            "org_goal": score.get("org_goal"),
            "alerts": alerts,
            "trend_direction": direction,
            "trend_delta": delta,
            "insufficient_dimensions": score.get("insufficient_dimensions", []),
        }

    def get_dashboard(self, agents=None):
        """Dashboard view of all agents."""
        if agents is None:
            agents = self.collector.get_all_agents()
            if not agents:
                # Load from schema
                try:
                    with open(REPO / "config" / "agents" / "agent-schema.yaml") as f:
                        schema = yaml.safe_load(f)
                    agents = [a["agent_id"] for a in schema.get("agents", [])]
                except Exception:
                    agents = list(ROLE_WEIGHTS.keys())

        rankings = self.scorer.rank_agents(agents)
        all_alerts = self.alerts.check_all(agents)

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "org_goal": self.scorer.org_goal,
            "rankings": rankings,
            "alerts": all_alerts,
            "total_agents": len(agents),
            "agents_with_data": len(self.collector.get_all_agents()),
        }

    def save_metrics(self):
        """Save current metrics state."""
        PERF_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "org_goal": self.scorer.org_goal,
            "agents": {},
        }
        for agent_id in self.collector.get_all_agents():
            score = self.scorer.score_agent(agent_id)
            data["agents"][agent_id] = score
        with open(METRICS_PATH, "w") as f:
            json.dump(data, f, indent=2)


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS
# ═══════════════════════════════════════════════════════════════════════════════

def run_tests():
    print("=" * 60)
    print("  MA-12 Agent Performance Metrics Tests")
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

    # Test 1: Role weights defined for all 7 agents
    test("7 role weight profiles", len(ROLE_WEIGHTS) == 7)

    # Test 2: All weights sum to 1.0
    for agent_id, weights in ROLE_WEIGHTS.items():
        total = sum(weights.values())
        if abs(total - 1.0) > 0.01:
            test(f"Weights sum to 1.0 for {agent_id}", False, f"sum={total}")
            break
    else:
        test("All role weights sum to 1.0", True)

    # Test 3: 3 alert levels
    test("3 alert levels", len(ALERT_LEVELS) == 3)

    # Test 4: 5 org goal profiles
    test("5 org goal profiles", len(ORG_GOAL_PROFILES) == 5)

    # Test 5: Collector records events
    pm = PerformanceManager()
    pm.collector.record_review_score("strategy_lead", 8.0)
    pm.collector.record_review_score("strategy_lead", 7.5)
    pm.collector.record_review_score("strategy_lead", 9.0)
    events = pm.collector.get_events("strategy_lead", "quality")
    test("Collector records events", len(events) == 3)

    # Test 6: Quality scoring
    score, count, sufficient = pm.scorer.score_dimension("strategy_lead", "quality")
    test("Quality score calculated", score is not None and 0 <= score <= 1.0,
         f"score={score}, count={count}")

    # Test 7: Minimum sample threshold
    pm.collector.record("engineering_lead", "speed", 0.8)
    _, count, sufficient = pm.scorer.score_dimension("engineering_lead", "speed")
    test(f"Insufficient with {count} sample(s)", not sufficient and count < MIN_SAMPLE_THRESHOLD)

    # Test 8: Sufficient after threshold
    for _ in range(MIN_SAMPLE_THRESHOLD):
        pm.collector.record("engineering_lead", "speed", 0.7)
    _, count, sufficient = pm.scorer.score_dimension("engineering_lead", "speed")
    test(f"Sufficient with {count} samples", sufficient)

    # Test 9: Task duration speed scoring
    pm.collector.record_task_duration("operations_lead", 150, expected_s=300)
    events = pm.collector.get_events("operations_lead", "speed")
    test("Speed: fast task scores high", events[-1]["value"] >= 0.9)

    pm.collector.record_task_duration("operations_lead", 600, expected_s=300)
    events = pm.collector.get_events("operations_lead", "speed")
    test("Speed: slow task scores low", events[-1]["value"] <= 0.6)

    # Test 11: Cost efficiency scoring
    pm.collector.record_cost_efficiency("growth_revenue_lead", 0.10, 0.15)
    events = pm.collector.get_events("growth_revenue_lead", "cost_efficiency")
    test("Cost: under budget scores high", events[-1]["value"] >= 0.9)

    pm.collector.record_cost_efficiency("growth_revenue_lead", 0.30, 0.15)
    events = pm.collector.get_events("growth_revenue_lead", "cost_efficiency")
    test("Cost: over budget scores low", events[-1]["value"] <= 0.6)

    # Test 13: Reliability — success vs failure
    pm.collector.record_task_success("product_architect")
    pm.collector.record_task_success("product_architect")
    pm.collector.record_task_failure("product_architect", recovered=False)
    score, _, _ = pm.scorer.score_dimension("product_architect", "reliability")
    test("Reliability: 2 success + 1 failure", score is not None and 0.5 < score < 1.0,
         f"score={score}")

    # Test 14: Recovery credit
    pm.collector.record_task_failure("engineering_lead", recovered=True)
    events = pm.collector.get_events("engineering_lead", "reliability")
    recovery_events = [e for e in events if e.get("metadata", {}).get("recovery_credit")]
    test("Recovery credit: partial score (0.5)", 
         len(recovery_events) > 0 and recovery_events[-1]["value"] == 0.5)

    # Test 15: Recovery outcome scoring
    pm.collector.record_recovery("engineering_lead", "recovered")
    pm.collector.record_recovery("engineering_lead", "fallback_used")
    pm.collector.record_recovery("engineering_lead", "failed")
    events = pm.collector.get_events("engineering_lead", "reliability")
    test("Recovery outcomes have different scores",
         len(set(e["value"] for e in events[-3:])) >= 2)

    # Test 16: Compliance scoring
    pm.collector.record_compliance_pass("narrative_content_lead")
    pm.collector.record_compliance_pass("narrative_content_lead")
    pm.collector.record_compliance_violation("narrative_content_lead", "warn")
    score, _, _ = pm.scorer.score_dimension("narrative_content_lead", "compliance")
    test("Compliance: 2 pass + 1 warn", score is not None and score > 0.5, f"score={score}")

    # Test 17: Decision accuracy integration
    pm.collector.record_decision_outcome("strategy_lead", outcome_score=7, max_score=10,
                                          confidence=0.8, predicted_score=8)
    events = pm.collector.get_events("strategy_lead", "quality")
    has_accuracy = any(e.get("metadata", {}).get("decision_accuracy") for e in events)
    test("Decision accuracy tracked", has_accuracy)

    # Test 18: Composite score with role weights
    # Add enough data for strategy_lead
    for _ in range(3):
        pm.collector.record("strategy_lead", "speed", 0.7)
        pm.collector.record("strategy_lead", "cost_efficiency", 0.8)
        pm.collector.record("strategy_lead", "reliability", 0.9)
        pm.collector.record("strategy_lead", "compliance", 0.95)

    result = pm.scorer.score_agent("strategy_lead")
    test("Composite score calculated",
         result["composite_score"] is not None and 0 <= result["composite_score"] <= 1.0,
         f"composite={result.get('composite_score')}")

    # Test 19: Role-specific weights applied
    weights = result.get("weights_used", {})
    test("Strategy lead: quality weighted highest",
         weights.get("quality", 0) > weights.get("speed", 0),
         f"quality={weights.get('quality')}, speed={weights.get('speed')}")

    # Test 20: Org goal override
    pm_speed = PerformanceManager("speed_critical")
    for _ in range(3):
        pm_speed.collector.record("strategy_lead", "quality", 0.8)
        pm_speed.collector.record("strategy_lead", "speed", 0.8)
    result_speed = pm_speed.scorer.score_agent("strategy_lead")
    test("Org goal 'speed_critical' applied",
         result_speed.get("org_goal") == "speed_critical")

    # Test 21: Rankings
    rankings = pm.scorer.rank_agents()
    test("Rankings produced", len(rankings) > 0 and "rank" in rankings[0],
         f"{len(rankings)} agents ranked")

    # Test 22: Rankings sorted by composite
    if len(rankings) >= 2:
        test("Rankings sorted descending",
             rankings[0]["composite_score"] >= rankings[1]["composite_score"])
    else:
        test("Rankings sorted descending", True, "only 1 agent")

    # Test 23: Alert — watch level
    # Create an agent with low scores
    for _ in range(5):
        pm.collector.record("growth_revenue_lead", "quality", 0.4)
        pm.collector.record("growth_revenue_lead", "speed", 0.45)
        pm.collector.record("growth_revenue_lead", "reliability", 0.4)
        pm.collector.record("growth_revenue_lead", "compliance", 0.5)

    alerts = pm.alerts.check_agent("growth_revenue_lead")
    test("Alert fires for low performer", len(alerts) > 0, f"{len(alerts)} alerts")

    # Test 24: Alert has required fields
    if alerts:
        alert = alerts[0]
        test("Alert has required fields",
             all(k in alert for k in ["level", "agent", "dimension", "score", "threshold"]))
    else:
        test("Alert has required fields", False, "no alerts to check")

    # Test 25: Graduated severity
    severities = set(a["level"] for a in alerts)
    test("Graduated severity levels", len(severities) >= 1, str(severities))

    # Test 26: Dimension-specific alert overrides
    has_reliability_override = "reliability" in DIMENSION_ALERT_OVERRIDES
    test("Dimension-specific thresholds exist", has_reliability_override)

    # Test 27: Trend tracking
    pm.trends.snapshot(pm.collector.get_all_agents())
    pm.trends.snapshot(pm.collector.get_all_agents())
    direction, delta = pm.trends.compute_direction("strategy_lead")
    test("Trend direction computed", direction in ("improving", "declining", "stable", "insufficient_data"),
         f"direction={direction}, delta={delta}")

    # Test 28: Full agent report
    report = pm.get_agent_report("strategy_lead")
    test("Full report has all fields",
         all(k in report for k in ["composite_score", "dimensions", "weights",
                                     "alerts", "trend_direction"]))

    # Test 29: Dashboard
    dashboard = pm.get_dashboard()
    test("Dashboard produced",
         "rankings" in dashboard and "alerts" in dashboard and "total_agents" in dashboard)

    # Test 30: Save metrics
    pm.save_metrics()
    test("Metrics saved to disk", METRICS_PATH.exists())

    print(f"\n  Results: {tp}/{tt} passed")
    return tp == tt


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="NemoClaw Agent Performance Metrics")
    parser.add_argument("--test", action="store_true", help="Run all tests")
    parser.add_argument("--dashboard", action="store_true", help="Show performance dashboard")
    parser.add_argument("--agent", metavar="ID", help="Show agent report")
    parser.add_argument("--rankings", action="store_true", help="Show agent rankings")
    parser.add_argument("--alerts", action="store_true", help="Show performance alerts")
    parser.add_argument("--goal", default="balanced",
                       choices=list(ORG_GOAL_PROFILES.keys()),
                       help="Organization goal profile")
    args = parser.parse_args()

    if args.test:
        success = run_tests()
        sys.exit(0 if success else 1)

    pm = PerformanceManager(args.goal)

    if args.dashboard:
        dashboard = pm.get_dashboard()
        print(f"  Performance Dashboard (goal: {dashboard.get('org_goal', 'balanced')})")
        print(f"  Agents: {dashboard['total_agents']} total, {dashboard['agents_with_data']} with data")
        print()

        rankings = dashboard.get("rankings", [])
        if rankings:
            print(f"  {'Rank':<5} {'Agent':<25} {'Composite':>10} {'Qual':>6} {'Speed':>6} {'Cost':>6} {'Rel':>6} {'Comp':>6}")
            print(f"  {'-'*5} {'-'*25} {'-'*10} {'-'*6} {'-'*6} {'-'*6} {'-'*6} {'-'*6}")
            for r in rankings:
                dims = r.get("dimensions", {})
                def fmt(v): return f"{v:.0%}" if v is not None else "N/A"
                print(f"  {r['rank']:<5} {r['agent_id']:<25} {r['composite_score']:>9.0%} "
                      f"{fmt(dims.get('quality')):>6} {fmt(dims.get('speed')):>6} "
                      f"{fmt(dims.get('cost_efficiency')):>6} {fmt(dims.get('reliability')):>6} "
                      f"{fmt(dims.get('compliance')):>6}")
        else:
            print("  No performance data yet. Run skills and MA systems to generate data.")

        alerts = dashboard.get("alerts", {})
        if alerts:
            print(f"\n  Alerts:")
            for agent_id, agent_alerts in alerts.items():
                for a in agent_alerts:
                    icon = {"info": "👀", "warn": "⚠️", "critical": "🚨"}.get(a["severity"], "?")
                    print(f"    {icon} {a['message']}")

    elif args.agent:
        report = pm.get_agent_report(args.agent)
        print(f"  Agent: {report['agent_id']}")
        print(f"  Composite: {report['composite_score']:.0%}" if report['composite_score'] else "  Composite: N/A")
        print(f"  Trend: {report['trend_direction']} ({report['trend_delta']:+.1%})")
        print(f"  Goal: {report.get('org_goal', 'balanced')}")
        print()
        for dim, data in report.get("dimensions", {}).items():
            score = data.get("score")
            icon = "✅" if score and score >= 0.7 else ("⚠️" if score and score >= 0.5 else "❌")
            suf = "✓" if data.get("sufficient") else f"(n={data.get('sample_count', 0)})"
            score_str = f"{score:.0%}" if score is not None else "N/A"
            print(f"    {icon} {dim:<18} {score_str:>6} weight={data.get('weight', 0):.0%} {suf}")

    elif args.rankings:
        rankings = pm.scorer.rank_agents()
        if rankings:
            for r in rankings:
                print(f"  #{r['rank']} {r['agent_id']}: {r['composite_score']:.0%}")
        else:
            print("  No data yet.")

    elif args.alerts:
        if ALERTS_PATH.exists():
            with open(ALERTS_PATH) as f:
                for line in f.readlines()[-20:]:
                    try:
                        a = json.loads(line.strip())
                        icon = {"info": "👀", "warn": "⚠️", "critical": "🚨"}.get(a.get("severity"), "?")
                        print(f"  {icon} [{a.get('timestamp', '?')[:19]}] {a.get('message', '?')}")
                    except json.JSONDecodeError:
                        continue
        else:
            print("  No alerts yet.")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
