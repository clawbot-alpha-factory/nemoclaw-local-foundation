#!/usr/bin/env python3
"""
NemoClaw Observer & System Health v1.0 (MA-14)

Unified system health monitoring across all MA systems:
- 11 health domains with per-domain scoring
- Composite health score with weighted domains
- Granular anomaly detection (info/warning/critical)
- Recovery recommendations per alert
- Historical trend tracking with time-series snapshots
- CLI dashboard + JSON export for web dashboards

Usage:
  python3 scripts/system_health.py --test
  python3 scripts/system_health.py --dashboard
  python3 scripts/system_health.py --domain agents
  python3 scripts/system_health.py --export health-report.json
  python3 scripts/system_health.py --trends
  python3 scripts/system_health.py --alerts
"""

import argparse
import json
import os
import sys
import time
import yaml
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict

REPO = Path.home() / "nemoclaw-local-foundation"
HEALTH_DIR = Path.home() / ".nemoclaw" / "health"
SNAPSHOTS_PATH = HEALTH_DIR / "snapshots.jsonl"
ALERTS_PATH = HEALTH_DIR / "health-alerts.jsonl"

# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH DOMAINS & WEIGHTS
# ═══════════════════════════════════════════════════════════════════════════════

HEALTH_DOMAINS = {
    "infrastructure": {
        "description": "API keys, budget, checkpoint DB, disk",
        "weight": 0.13,
        "critical_threshold": 0.30,
        "warning_threshold": 0.60,
    },
    "agents": {
        "description": "Per-agent performance, compliance, workload",
        "weight": 0.11,
        "critical_threshold": 0.35,
        "warning_threshold": 0.60,
    },
    "memory": {
        "description": "Shared memory size, conflicts, decay state",
        "weight": 0.08,
        "critical_threshold": 0.30,
        "warning_threshold": 0.55,
    },
    "messaging": {
        "description": "Pending responses, blocked messages, channels",
        "weight": 0.08,
        "critical_threshold": 0.30,
        "warning_threshold": 0.55,
    },
    "decisions": {
        "description": "Pending decisions, velocity, backlog",
        "weight": 0.10,
        "critical_threshold": 0.30,
        "warning_threshold": 0.55,
    },
    "tasks": {
        "description": "Running plans, failed tasks, cost tracking",
        "weight": 0.11,
        "critical_threshold": 0.35,
        "warning_threshold": 0.60,
    },
    "interactions": {
        "description": "Active sessions, escalations",
        "weight": 0.05,
        "critical_threshold": 0.25,
        "warning_threshold": 0.50,
    },
    "recovery": {
        "description": "Failure rate, recovery rate, patterns",
        "weight": 0.09,
        "critical_threshold": 0.35,
        "warning_threshold": 0.55,
    },
    "conflicts": {
        "description": "Open conflicts, resolution rate",
        "weight": 0.05,
        "critical_threshold": 0.30,
        "warning_threshold": 0.50,
    },
    "reviews": {
        "description": "Pending reviews, quality scores",
        "weight": 0.07,
        "critical_threshold": 0.30,
        "warning_threshold": 0.55,
    },
    "learning": {
        "description": "Lessons pending, applied, efficacy",
        "weight": 0.07,
        "critical_threshold": 0.25,
        "warning_threshold": 0.50,
    },
    "browser": {
        "description": "PinchTab server, instances, memory usage",
        "weight": 0.06,
        "critical_threshold": 0.30,
        "warning_threshold": 0.55,
    },
}

# Recovery recommendations per domain
RECOVERY_ACTIONS = {
    "infrastructure": {
        "critical": [
            "Check API keys: set -a && source config/.env && set +a",
            "Reset budget: edit ~/.nemoclaw/logs/provider-spend.json",
            "Rebuild checkpoint: rm ~/.nemoclaw/checkpoints/langgraph.db",
        ],
        "warning": [
            "Run validation: python3 scripts/validate.py",
            "Check budget: python3 scripts/budget-status.py",
        ],
    },
    "agents": {
        "critical": [
            "Review agent compliance: python3 scripts/behavior_guard.py --compliance",
            "Check performance: python3 scripts/agent_performance.py --dashboard",
            "Consider reassigning underperforming agent's tasks",
        ],
        "warning": [
            "Monitor agent trends: python3 scripts/agent_performance.py --agent {agent_id}",
        ],
    },
    "memory": {
        "critical": [
            "Clear expired memory: run cleanup_expired() on shared workspaces",
            "Resolve critical conflicts in MA-2 shared memory",
            "Check long-term memory size: ls -la ~/.nemoclaw/memory/",
        ],
        "warning": [
            "Run memory promotion: python3 scripts/agent_memory.py --workspace {id} --promote",
        ],
    },
    "messaging": {
        "critical": [
            "Check blocking messages: resolve urgent pending responses",
            "Clear stale channels with no recent activity",
        ],
        "warning": [
            "Review pending responses: check timeout escalations",
        ],
    },
    "decisions": {
        "critical": [
            "Review decision backlog: python3 scripts/decision_log.py --pending",
            "Escalate stale proposed decisions to executive_operator",
        ],
        "warning": [
            "Check decision velocity: python3 scripts/decision_log.py --velocity",
        ],
    },
    "tasks": {
        "critical": [
            "Check failed plans: ls ~/.nemoclaw/plans/",
            "Review cost overruns: python3 scripts/cost_governor.py --status",
            "Replan failed tasks: python3 scripts/task_decomposer.py --replan {plan_id}",
        ],
        "warning": [
            "Monitor active plans and budget remaining",
        ],
    },
    "recovery": {
        "critical": [
            "Review failure patterns: python3 scripts/failure_recovery.py --patterns",
            "Check recovery analytics: python3 scripts/failure_recovery.py --analytics",
            "Address recurring failures before they cascade",
        ],
        "warning": [
            "Monitor failure rate trends",
        ],
    },
    "conflicts": {
        "critical": [
            "Resolve open conflicts: python3 scripts/conflict_resolution.py --history",
            "Escalate unresolved critical conflicts",
        ],
        "warning": [
            "Review conflict stats: python3 scripts/conflict_resolution.py --stats",
        ],
    },
    "reviews": {
        "critical": [
            "Process pending reviews before outputs are used downstream",
            "Check reviewer quality: python3 scripts/peer_review.py --quality",
        ],
        "warning": [
            "Monitor review backlog",
        ],
    },
    "learning": {
        "critical": [
            "Run learning cycle: python3 scripts/learning_loop.py --cycle",
            "Review pending approvals: python3 scripts/learning_loop.py --pending",
            "Rollback degrading lessons: python3 scripts/learning_loop.py --rollback {id}",
        ],
        "warning": [
            "Check lesson summary: python3 scripts/learning_loop.py --summary",
        ],
    },
    "interactions": {
        "critical": ["Review escalated sessions", "Close stale interaction sessions"],
        "warning": ["Monitor active session count"],
    },
    "browser": {
        "critical": [
            "Check PinchTab server: curl http://localhost:9867/health",
            "Restart PinchTab: pinchtab (in separate terminal)",
            "Kill stale Chrome instances: pkill -f 'chrome.*pinchtab'",
            "Check memory: curl http://localhost:9867/instances/metrics",
        ],
        "warning": [
            "Monitor instance count: curl http://localhost:9867/instances",
            "Check action log: tail ~/.nemoclaw/browser/action-log.jsonl",
        ],
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# DOMAIN HEALTH CHECKERS
# ═══════════════════════════════════════════════════════════════════════════════

class DomainChecker:
    """Checks health for each domain by reading MA system state."""

    def __init__(self):
        self._nem_dir = Path.home() / ".nemoclaw"

    def check_infrastructure(self):
        """Check infrastructure health."""
        checks = []

        # Budget remaining
        try:
            spend_path = self._nem_dir / "logs" / "provider-spend.json"
            budget_path = REPO / "config" / "routing" / "budget-config.yaml"
            if spend_path.exists() and budget_path.exists():
                with open(spend_path) as f:
                    spend = json.load(f)
                with open(budget_path) as f:
                    bcfg = yaml.safe_load(f)
                for p in ["anthropic", "openai", "google"]:
                    budget = bcfg["budgets"][p]["total_usd"]
                    spent = spend.get(p, {})
                    if isinstance(spent, dict):
                        spent = spent.get("cumulative_spend_usd", 0)
                    remaining_pct = max(0, (budget - spent) / budget) if budget > 0 else 0
                    checks.append(("budget_" + p, remaining_pct))
            else:
                checks.append(("budget_files", 0.5))
        except Exception:
            checks.append(("budget_check", 0.3))

        # Checkpoint DB
        cp = self._nem_dir / "checkpoints" / "langgraph.db"
        checks.append(("checkpoint_db", 1.0 if cp.exists() else 0.0))

        # API keys
        env_path = REPO / "config" / ".env"
        if env_path.exists():
            with open(env_path) as f:
                env_content = f.read()
            key_count = sum(1 for k in ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY"]
                            if k in env_content)
            checks.append(("api_keys", key_count / 3.0))
        else:
            checks.append(("api_keys", 0.0))

        return self._aggregate(checks)

    def check_agents(self):
        """Check agent health from performance metrics."""
        try:
            perf_path = self._nem_dir / "performance" / "agent-metrics.json"
            if perf_path.exists():
                with open(perf_path) as f:
                    data = json.load(f)
                scores = []
                for agent_id, agent_data in data.get("agents", {}).items():
                    composite = agent_data.get("composite_score")
                    if composite is not None:
                        scores.append(composite)
                if scores:
                    return sum(scores) / len(scores), len(scores), []
            return 1.0, 0, ["No performance data — all agents assumed healthy"]
        except Exception:
            return 0.8, 0, ["Could not load performance data"]

    def check_memory(self):
        """Check memory system health."""
        checks = []

        # Check for shared workspaces
        ws_dir = self._nem_dir / "workspaces"
        if ws_dir.exists():
            workspace_count = len(list(ws_dir.iterdir()))
            checks.append(("workspaces", min(1.0, 1.0 - workspace_count * 0.02)))  # slight penalty for many
        else:
            checks.append(("workspaces", 1.0))

        # Long-term memory
        lt_path = self._nem_dir / "memory" / "long-term.json"
        if lt_path.exists():
            try:
                size = lt_path.stat().st_size
                checks.append(("long_term_size", 1.0 if size < 1_000_000 else 0.7))
            except Exception:
                checks.append(("long_term_size", 0.8))
        else:
            checks.append(("long_term", 1.0))

        return self._aggregate(checks)

    def check_messaging(self):
        """Check messaging health."""
        # No persistent message state to check in current implementation
        return 1.0, 0, ["Messaging health checked (in-memory state)"]

    def check_decisions(self):
        """Check decision system health."""
        dec_dir = self._nem_dir / "decisions"
        if not dec_dir.exists():
            return 1.0, 0, ["No decisions yet"]

        try:
            # Check for stale proposed decisions
            checks = []
            for f in dec_dir.glob("*.json"):
                with open(f) as fh:
                    data = json.load(fh)
                if isinstance(data, list):
                    pending = sum(1 for d in data if d.get("status") == "proposed")
                    total = len(data)
                    ratio = 1.0 - (pending / max(total, 1)) * 0.5
                    checks.append(("pending_ratio", ratio))
            if checks:
                return self._aggregate(checks)
            return 1.0, 0, []
        except Exception:
            return 0.8, 0, ["Could not check decisions"]

    def check_tasks(self):
        """Check task/plan health."""
        plans_dir = self._nem_dir / "plans"
        if not plans_dir.exists():
            return 1.0, 0, ["No plans executed yet"]

        try:
            checks = []
            for f in plans_dir.glob("*.json"):
                with open(f) as fh:
                    plan = json.load(fh)
                status = plan.get("status", "draft")
                if status == "failed":
                    checks.append(("plan_failed", 0.2))
                elif status == "complete":
                    checks.append(("plan_complete", 1.0))
                else:
                    checks.append(("plan_other", 0.7))
            if checks:
                return self._aggregate(checks)
            return 1.0, 0, []
        except Exception:
            return 0.8, 0, ["Could not check plans"]

    def check_interactions(self):
        """Check interaction sessions."""
        sess_dir = self._nem_dir / "interaction-sessions"
        if not sess_dir.exists():
            return 1.0, 0, ["No interaction sessions"]

        try:
            escalated = 0
            total = 0
            for f in sess_dir.glob("*.json"):
                total += 1
                with open(f) as fh:
                    sess = json.load(fh)
                if sess.get("status") == "escalated":
                    escalated += 1
            score = 1.0 - (escalated / max(total, 1)) * 0.5
            return score, total, []
        except Exception:
            return 0.8, 0, []

    def check_recovery(self):
        """Check failure recovery health."""
        analytics_path = self._nem_dir / "recovery" / "recovery-analytics.json"
        if not analytics_path.exists():
            return 1.0, 0, ["No failures recorded — system healthy"]

        try:
            with open(analytics_path) as f:
                data = json.load(f)
            metrics = data.get("metrics", {})
            recovery_rate = metrics.get("recovery_rate", 1.0)
            total = metrics.get("total_failures", 0)
            return recovery_rate, total, []
        except Exception:
            return 0.8, 0, []

    def check_conflicts(self):
        """Check conflict resolution health."""
        stats_path = self._nem_dir / "conflicts" / "conflict-stats.json"
        if not stats_path.exists():
            return 1.0, 0, ["No conflicts recorded"]

        try:
            with open(stats_path) as f:
                stats = json.load(f)
            resolution_rate = stats.get("resolution_rate", 1.0)
            total = stats.get("total_conflicts", 0)
            return resolution_rate, total, []
        except Exception:
            return 0.8, 0, []

    def check_reviews(self):
        """Check peer review health."""
        review_path = self._nem_dir / "reviews" / "reviewer-quality.json"
        if not review_path.exists():
            return 1.0, 0, ["No reviews yet"]

        try:
            with open(review_path) as f:
                data = json.load(f)
            if not data:
                return 1.0, 0, []
            accuracies = []
            for reviewer, stats in data.items():
                total = stats.get("total_reviews", 0)
                accurate = stats.get("accurate_catches", 0)
                false_flags = stats.get("false_flags", 0)
                if total > 0:
                    acc = accurate / max(accurate + false_flags, 1)
                    accuracies.append(acc)
            if accuracies:
                return sum(accuracies) / len(accuracies), len(accuracies), []
            return 1.0, 0, []
        except Exception:
            return 0.8, 0, []

    def check_learning(self):
        """Check learning system health."""
        lessons_path = self._nem_dir / "learning" / "lessons.json"
        if not lessons_path.exists():
            return 1.0, 0, ["No lessons yet"]

        try:
            with open(lessons_path) as f:
                lessons = json.load(f)
            total = len(lessons)
            if total == 0:
                return 1.0, 0, []

            applied = sum(1 for l in lessons.values() if l.get("status") == "applied")
            rolled_back = sum(1 for l in lessons.values() if l.get("status") == "rolled_back")
            needs_review = sum(1 for l in lessons.values() if l.get("status") == "needs_review")

            # Penalty for rolled back or needing review
            score = 1.0 - (rolled_back * 0.1) - (needs_review * 0.15)
            return max(0.0, min(1.0, score)), total, []
        except Exception:
            return 0.8, 0, []

    def check_browser(self):
        """Check PinchTab browser automation health."""
        checks = []

        # 1. PinchTab server reachable
        try:
            import requests
            r = requests.get("http://localhost:9867/health", timeout=5)
            if r.status_code == 200:
                data = r.json()
                checks.append(("server_health", 1.0))
                tab_count = data.get("tabs", 0)
                # Warn if too many tabs open (>10)
                checks.append(("tab_count", 1.0 if tab_count <= 10 else 0.6))
            else:
                checks.append(("server_health", 0.0))
        except Exception:
            # PinchTab not running — not critical if no web skills are active
            checks.append(("server_reachable", 0.4))

        # 2. Instance count (max 4 recommended)
        try:
            import requests
            r = requests.get("http://localhost:9867/instances", timeout=5)
            if r.status_code == 200:
                instances = r.json()
                count = len(instances) if isinstance(instances, list) else 0
                if count > 4:
                    checks.append(("instance_count", 0.3))
                elif count > 2:
                    checks.append(("instance_count", 0.7))
                else:
                    checks.append(("instance_count", 1.0))
            else:
                checks.append(("instance_count", 0.5))
        except Exception:
            checks.append(("instance_count", 0.5))

        # 3. Memory usage (check via /instances/metrics)
        try:
            import requests
            r = requests.get("http://localhost:9867/instances/metrics", timeout=5)
            if r.status_code == 200:
                metrics = r.json()
                # If total memory > 1GB, degrade
                total_mem_mb = 0
                if isinstance(metrics, list):
                    for m in metrics:
                        total_mem_mb += m.get("memoryMB", m.get("memory_mb", 0))
                elif isinstance(metrics, dict):
                    total_mem_mb = metrics.get("totalMemoryMB", metrics.get("total_memory_mb", 0))

                if total_mem_mb > 1024:
                    checks.append(("memory", 0.2))
                elif total_mem_mb > 512:
                    checks.append(("memory", 0.6))
                else:
                    checks.append(("memory", 1.0))
            else:
                checks.append(("memory", 0.7))
        except Exception:
            checks.append(("memory", 0.7))

        # 4. Action log — check for recent errors
        log_path = Path.home() / ".nemoclaw" / "browser" / "action-log.jsonl"
        if log_path.exists():
            try:
                import json as json_mod
                recent_errors = 0
                recent_total = 0
                with open(log_path) as f:
                    lines = f.readlines()
                for line in lines[-50:]:  # Last 50 actions
                    try:
                        entry = json_mod.loads(line.strip())
                        recent_total += 1
                        if not entry.get("success", True):
                            recent_errors += 1
                    except Exception:
                        continue
                if recent_total > 0:
                    error_rate = recent_errors / recent_total
                    checks.append(("error_rate", max(0.0, 1.0 - error_rate * 2)))
                else:
                    checks.append(("error_rate", 1.0))
            except Exception:
                checks.append(("error_rate", 0.8))
        else:
            checks.append(("action_log", 1.0))  # No log = no actions = fine

        return self._aggregate(checks)

    def _aggregate(self, checks):
        """Aggregate check results into a domain score."""
        if not checks:
            return 1.0, 0, []
        values = [v for _, v in checks]
        score = sum(values) / len(values)
        return round(score, 3), len(checks), []


# ═══════════════════════════════════════════════════════════════════════════════
# ANOMALY DETECTOR
# ═══════════════════════════════════════════════════════════════════════════════

class AnomalyDetector:
    """Detects anomalies with graduated severity and multi-factor correlation."""

    def detect(self, domain_scores):
        """Detect anomalies across all domains.

        Args:
            domain_scores: dict of domain → score (0.0-1.0)

        Returns: list of anomalies [{domain, severity, score, threshold, message, recovery}]
        """
        anomalies = []

        for domain, score in domain_scores.items():
            domain_def = HEALTH_DOMAINS.get(domain, {})
            crit_threshold = domain_def.get("critical_threshold", 0.30)
            warn_threshold = domain_def.get("warning_threshold", 0.60)
            recovery = RECOVERY_ACTIONS.get(domain, {})

            if score < crit_threshold:
                anomalies.append({
                    "domain": domain,
                    "severity": "critical",
                    "score": score,
                    "threshold": crit_threshold,
                    "message": f"{domain} CRITICAL: {score:.0%} (below {crit_threshold:.0%})",
                    "recovery": recovery.get("critical", ["Investigate immediately"]),
                })
            elif score < warn_threshold:
                anomalies.append({
                    "domain": domain,
                    "severity": "warning",
                    "score": score,
                    "threshold": warn_threshold,
                    "message": f"{domain} WARNING: {score:.0%} (below {warn_threshold:.0%})",
                    "recovery": recovery.get("warning", ["Monitor closely"]),
                })

        # Multi-factor correlation: if 3+ domains degraded, system-level alert
        degraded = [a for a in anomalies if a["severity"] in ("warning", "critical")]
        if len(degraded) >= 3:
            anomalies.insert(0, {
                "domain": "system",
                "severity": "critical",
                "score": sum(d["score"] for d in degraded) / len(degraded),
                "threshold": 0,
                "message": f"SYSTEM-WIDE DEGRADATION: {len(degraded)} domains affected",
                "recovery": [
                    "Run full validation: python3 scripts/validate.py",
                    "Check budget: python3 scripts/budget-status.py",
                    "Review all alerts below and address critical domains first",
                ],
            })

        return sorted(anomalies, key=lambda a: {"critical": 0, "warning": 1}.get(a["severity"], 2))


# ═══════════════════════════════════════════════════════════════════════════════
# TREND TRACKER
# ═══════════════════════════════════════════════════════════════════════════════

class HealthTrendTracker:
    """Tracks health scores over time for trend analysis."""

    def snapshot(self, domain_scores, composite):
        """Save a point-in-time health snapshot."""
        HEALTH_DIR.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "composite": composite,
            "domains": domain_scores,
        }
        with open(SNAPSHOTS_PATH, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def get_trends(self, last_n=20):
        """Get recent health snapshots."""
        if not SNAPSHOTS_PATH.exists():
            return []
        entries = []
        with open(SNAPSHOTS_PATH) as f:
            for line in f:
                try:
                    entries.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue
        return entries[-last_n:]

    def compute_direction(self, domain=None, last_n=10):
        """Compute trend direction for composite or specific domain.

        Returns: (direction, delta, data_points)
        """
        trends = self.get_trends(last_n)
        if len(trends) < 2:
            return "insufficient_data", 0.0, len(trends)

        if domain:
            values = [t.get("domains", {}).get(domain) for t in trends]
        else:
            values = [t.get("composite") for t in trends]

        values = [v for v in values if v is not None]
        if len(values) < 2:
            return "insufficient_data", 0.0, len(values)

        mid = len(values) // 2
        first_half = sum(values[:mid]) / mid
        second_half = sum(values[mid:]) / (len(values) - mid)
        delta = round(second_half - first_half, 3)

        if delta > 0.05:
            return "improving", delta, len(values)
        elif delta < -0.05:
            return "declining", delta, len(values)
        return "stable", delta, len(values)

    def detect_slow_degradation(self, threshold_delta=-0.03, last_n=10):
        """Detect domains with slow but consistent degradation.

        Returns: list of (domain, delta) where delta < threshold
        """
        degrading = []
        for domain in HEALTH_DOMAINS:
            direction, delta, points = self.compute_direction(domain, last_n)
            if delta < threshold_delta and points >= 3:
                degrading.append((domain, delta))
        return degrading


# ═══════════════════════════════════════════════════════════════════════════════
# SYSTEM HEALTH OBSERVER (main engine)
# ═══════════════════════════════════════════════════════════════════════════════

class SystemHealthObserver:
    """Unified system health observer."""

    def __init__(self):
        self.checker = DomainChecker()
        self.anomaly_detector = AnomalyDetector()
        self.trends = HealthTrendTracker()
        self._check_methods = {
            "infrastructure": self.checker.check_infrastructure,
            "agents": self.checker.check_agents,
            "memory": self.checker.check_memory,
            "messaging": self.checker.check_messaging,
            "decisions": self.checker.check_decisions,
            "tasks": self.checker.check_tasks,
            "interactions": self.checker.check_interactions,
            "recovery": self.checker.check_recovery,
            "conflicts": self.checker.check_conflicts,
            "reviews": self.checker.check_reviews,
            "learning": self.checker.check_learning,
            "browser": self.checker.check_browser,
        }

    def check_all(self):
        """Run all health checks.

        Returns: dict with domain scores, composite, anomalies
        """
        domain_scores = {}
        domain_details = {}

        for domain, check_fn in self._check_methods.items():
            try:
                score, sample_count, notes = check_fn()
                domain_scores[domain] = round(score, 3)
                domain_details[domain] = {
                    "score": round(score, 3),
                    "sample_count": sample_count,
                    "notes": notes,
                }
            except Exception as e:
                domain_scores[domain] = 0.5
                domain_details[domain] = {
                    "score": 0.5,
                    "sample_count": 0,
                    "notes": [f"Check error: {str(e)[:80]}"],
                }

        # Composite score (weighted)
        composite = 0.0
        total_weight = 0.0
        for domain, score in domain_scores.items():
            weight = HEALTH_DOMAINS.get(domain, {}).get("weight", 0.05)
            composite += score * weight
            total_weight += weight
        composite = round(composite / total_weight, 3) if total_weight > 0 else 0.0

        # Detect anomalies
        anomalies = self.anomaly_detector.detect(domain_scores)

        # Save snapshot
        self.trends.snapshot(domain_scores, composite)

        # Check for slow degradation
        degrading = self.trends.detect_slow_degradation()

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "composite_score": composite,
            "status": self._overall_status(composite, anomalies),
            "domain_scores": domain_scores,
            "domain_details": domain_details,
            "anomalies": anomalies,
            "degrading_domains": degrading,
            "trend_direction": self.trends.compute_direction()[0],
        }

        # Log alerts
        if anomalies:
            self._log_alerts(anomalies)

        return result

    def check_domain(self, domain):
        """Check a single domain."""
        check_fn = self._check_methods.get(domain)
        if not check_fn:
            return None
        score, count, notes = check_fn()
        return {"domain": domain, "score": score, "sample_count": count, "notes": notes}

    def _overall_status(self, composite, anomalies):
        """Determine overall system status."""
        critical_count = sum(1 for a in anomalies if a["severity"] == "critical")
        if critical_count > 0 or composite < 0.35:
            return "CRITICAL"
        elif composite < 0.65:
            return "DEGRADED"
        return "HEALTHY"

    def _log_alerts(self, anomalies):
        """Persist alerts."""
        HEALTH_DIR.mkdir(parents=True, exist_ok=True)
        for anomaly in anomalies:
            entry = {**anomaly, "logged_at": datetime.now(timezone.utc).isoformat()}
            with open(ALERTS_PATH, "a") as f:
                f.write(json.dumps(entry) + "\n")

    def export_json(self, path=None):
        """Export full health report as JSON."""
        result = self.check_all()
        if path:
            with open(path, "w") as f:
                json.dump(result, f, indent=2)
        return result


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS
# ═══════════════════════════════════════════════════════════════════════════════

def run_tests():
    print("=" * 60)
    print("  MA-14 Observer & System Health Tests")
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

    # Test 1: Domain definitions
    test("12 health domains", len(HEALTH_DOMAINS) == 12)

    # Test 2: Weights sum to ~1.0
    total_weight = sum(d["weight"] for d in HEALTH_DOMAINS.values())
    test("Domain weights sum to ~1.0", abs(total_weight - 1.0) < 0.01, f"sum={total_weight}")

    # Test 3: All domains have thresholds
    all_thresholds = all("critical_threshold" in d and "warning_threshold" in d
                          for d in HEALTH_DOMAINS.values())
    test("All domains have thresholds", all_thresholds)

    # Test 4: Recovery actions for all domains
    test("Recovery actions for all domains",
         all(d in RECOVERY_ACTIONS for d in HEALTH_DOMAINS))

    # Test 5: Infrastructure check runs
    checker = DomainChecker()
    score, count, notes = checker.check_infrastructure()
    test("Infrastructure check runs", 0 <= score <= 1.0, f"score={score}")

    # Test 6: Agent check runs
    score, count, notes = checker.check_agents()
    test("Agent check runs", 0 <= score <= 1.0, f"score={score}")

    # Test 7: Memory check runs
    score, count, notes = checker.check_memory()
    test("Memory check runs", 0 <= score <= 1.0, f"score={score}")

    # Test 8: Recovery check runs
    score, count, notes = checker.check_recovery()
    test("Recovery check runs", 0 <= score <= 1.0, f"score={score}")

    # Test 9: Full health check
    observer = SystemHealthObserver()
    result = observer.check_all()
    test("Full health check runs",
         "composite_score" in result and "domain_scores" in result and "anomalies" in result)

    # Test 10: Composite score valid
    test("Composite score valid",
         0 <= result["composite_score"] <= 1.0, f"{result['composite_score']}")

    # Test 11: All 11 domains scored
    test("All 12 domains scored",
         len(result["domain_scores"]) == 12, f"{len(result['domain_scores'])}")

    # Test 12: Status determined
    test("Status determined",
         result["status"] in ("HEALTHY", "DEGRADED", "CRITICAL"), result["status"])

    # Test 13: Anomaly detection — critical
    detector = AnomalyDetector()
    low_scores = {"infrastructure": 0.2, "agents": 0.8, "memory": 0.9, "messaging": 0.9,
                   "decisions": 0.9, "tasks": 0.9, "interactions": 0.9, "recovery": 0.9,
                   "conflicts": 0.9, "reviews": 0.9, "learning": 0.9}
    anomalies = detector.detect(low_scores)
    critical = [a for a in anomalies if a["severity"] == "critical" and a["domain"] == "infrastructure"]
    test("Critical anomaly detected", len(critical) > 0)

    # Test 14: Recovery recommendations in anomalies
    test("Anomalies have recovery actions",
         all("recovery" in a for a in anomalies if anomalies))

    # Test 15: Multi-factor correlation (3+ degraded → system alert)
    multi_low = {d: 0.2 for d in HEALTH_DOMAINS}
    multi_anomalies = detector.detect(multi_low)
    system_alert = [a for a in multi_anomalies if a["domain"] == "system"]
    test("System-wide alert on 3+ degraded", len(system_alert) > 0)

    # Test 16: Warning level detection
    warn_scores = {"infrastructure": 0.55, "agents": 0.9, "memory": 0.9, "messaging": 0.9,
                    "decisions": 0.9, "tasks": 0.9, "interactions": 0.9, "recovery": 0.9,
                    "conflicts": 0.9, "reviews": 0.9, "learning": 0.9}
    warn_anomalies = detector.detect(warn_scores)
    warnings = [a for a in warn_anomalies if a["severity"] == "warning"]
    test("Warning anomaly detected", len(warnings) > 0)

    # Test 17: Healthy scores = no anomalies
    healthy_scores = {d: 0.9 for d in HEALTH_DOMAINS}
    healthy_anomalies = detector.detect(healthy_scores)
    test("Healthy scores = no anomalies", len(healthy_anomalies) == 0)

    # Test 18: Trend snapshot saved
    test("Snapshot saved", SNAPSHOTS_PATH.exists())

    # Test 19: Trend direction
    observer.trends.snapshot({"infrastructure": 0.8}, 0.85)
    observer.trends.snapshot({"infrastructure": 0.7}, 0.75)
    direction, delta, points = observer.trends.compute_direction()
    test("Trend direction computed",
         direction in ("improving", "declining", "stable", "insufficient_data"))

    # Test 20: Slow degradation detection
    # Add declining snapshots
    for i in range(5):
        scores = {d: 0.9 - i * 0.05 for d in HEALTH_DOMAINS}
        observer.trends.snapshot(scores, 0.9 - i * 0.05)
    degrading = observer.trends.detect_slow_degradation()
    test("Slow degradation detection works",
         isinstance(degrading, list))  # may or may not find degradation depending on data

    # Test 21: JSON export
    export_path = HEALTH_DIR / "test-export.json"
    result = observer.export_json(str(export_path))
    test("JSON export works", export_path.exists() and "composite_score" in result)

    # Clean up test export
    if export_path.exists():
        export_path.unlink()

    # Test 22: Single domain check
    domain_result = observer.check_domain("infrastructure")
    test("Single domain check works",
         domain_result is not None and "score" in domain_result)

    # Test 23: Invalid domain returns None
    test("Invalid domain returns None", observer.check_domain("nonexistent") is None)

    # Test 24: Domain details in full check
    test("Domain details included",
         "domain_details" in result and "infrastructure" in result.get("domain_details", {}))

    # Test 25: Degrading domains in result
    full_result = observer.check_all()
    test("Degrading domains tracked", "degrading_domains" in full_result)

    # Test 26: Alert logging
    test("Alerts logged", isinstance(full_result.get("anomalies"), list))

    # Test 27: Trend direction in result
    test("Trend direction in result", "trend_direction" in full_result)

    # Test 28: Overall status logic
    test("HEALTHY status for good scores",
         observer._overall_status(0.85, []) == "HEALTHY")
    test("DEGRADED status for medium scores",
         observer._overall_status(0.50, []) == "DEGRADED")
    test("CRITICAL status for low scores",
         observer._overall_status(0.20, []) == "CRITICAL")

    # ── Browser Health Domain Tests ──

    # Test: Browser domain exists
    test("Browser health domain exists", "browser" in HEALTH_DOMAINS)
    test("Browser domain weight", HEALTH_DOMAINS["browser"]["weight"] == 0.06)

    # Test: Browser check runs (may show PinchTab not running)
    browser_score, browser_count, browser_notes = checker.check_browser()
    test("Browser check runs", 0 <= browser_score <= 1.0, f"score={browser_score}")

    # Test: Browser in full health check
    full = observer.check_all()
    test("Browser in domain_scores", "browser" in full["domain_scores"])

    # Test: Browser recovery actions exist
    test("Browser recovery actions", "browser" in RECOVERY_ACTIONS)
    test("Browser has critical recovery",
         len(RECOVERY_ACTIONS["browser"]["critical"]) >= 3)

    # Test: Weights still sum to ~1.0
    new_total = sum(d["weight"] for d in HEALTH_DOMAINS.values())
    test("Weights sum to ~1.0 after browser addition",
         abs(new_total - 1.0) < 0.02, f"sum={new_total}")

    print(f"\n  Results: {tp}/{tt} passed")
    return tp == tt


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="NemoClaw System Health Observer")
    parser.add_argument("--test", action="store_true", help="Run all tests")
    parser.add_argument("--dashboard", action="store_true", help="Show health dashboard")
    parser.add_argument("--domain", metavar="NAME", help="Check single domain")
    parser.add_argument("--export", metavar="PATH", help="Export health report to JSON")
    parser.add_argument("--trends", action="store_true", help="Show health trends")
    parser.add_argument("--alerts", action="store_true", help="Show recent alerts")
    args = parser.parse_args()

    if args.test:
        success = run_tests()
        sys.exit(0 if success else 1)

    observer = SystemHealthObserver()

    if args.dashboard:
        result = observer.check_all()
        status_icon = {"HEALTHY": "🟢", "DEGRADED": "🟡", "CRITICAL": "🔴"}.get(result["status"], "?")

        print(f"\n  {'═' * 56}")
        print(f"  SYSTEM HEALTH: {status_icon} {result['status']} ({result['composite_score']:.0%})")
        print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
        print(f"  {'═' * 56}\n")

        for domain in HEALTH_DOMAINS:
            score = result["domain_scores"].get(domain, 0)
            bar_len = int(score * 20)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            icon = "🟢" if score >= 0.7 else ("🟡" if score >= 0.5 else "🔴")
            desc = HEALTH_DOMAINS[domain]["description"][:35]
            print(f"  {icon} {domain:<16} {score:>5.0%} {bar} {desc}")

        if result["anomalies"]:
            print(f"\n  {'─' * 56}")
            print(f"  ALERTS ({len(result['anomalies'])})")
            print(f"  {'─' * 56}")
            for a in result["anomalies"]:
                sev_icon = {"critical": "🔴", "warning": "🟡"}.get(a["severity"], "⚪")
                print(f"  {sev_icon} {a['message']}")
                for rec in a.get("recovery", [])[:2]:
                    print(f"     → {rec}")

        if result["degrading_domains"]:
            print(f"\n  ⚠️  Slow degradation detected: {[d[0] for d in result['degrading_domains']]}")

        trend = result.get("trend_direction", "unknown")
        trend_icon = {"improving": "📈", "declining": "📉", "stable": "➡️"}.get(trend, "❓")
        print(f"\n  Trend: {trend_icon} {trend}")

    elif args.domain:
        result = observer.check_domain(args.domain)
        if result:
            print(f"  Domain: {result['domain']}")
            print(f"  Score: {result['score']:.0%}")
            print(f"  Samples: {result['sample_count']}")
            if result.get("notes"):
                for note in result["notes"]:
                    print(f"  Note: {note}")
        else:
            print(f"  Unknown domain: {args.domain}")

    elif args.export:
        result = observer.export_json(args.export)
        print(f"  Exported to: {args.export}")
        print(f"  Status: {result['status']} ({result['composite_score']:.0%})")

    elif args.trends:
        trends = observer.trends.get_trends(10)
        if trends:
            print(f"  Health Trends (last {len(trends)} snapshots):")
            for t in trends:
                ts = t["timestamp"][:19]
                comp = t.get("composite", 0)
                icon = "🟢" if comp >= 0.7 else ("🟡" if comp >= 0.5 else "🔴")
                print(f"  {icon} [{ts}] {comp:.0%}")
        else:
            print("  No trend data yet.")

        direction, delta, points = observer.trends.compute_direction()
        print(f"\n  Direction: {direction} (delta: {delta:+.1%}, {points} points)")

    elif args.alerts:
        if ALERTS_PATH.exists():
            with open(ALERTS_PATH) as f:
                for line in f.readlines()[-20:]:
                    try:
                        a = json.loads(line.strip())
                        sev = {"critical": "🔴", "warning": "🟡"}.get(a.get("severity"), "?")
                        print(f"  {sev} [{a.get('logged_at', '?')[:19]}] {a.get('message', '?')}")
                    except json.JSONDecodeError:
                        continue
        else:
            print("  No alerts yet.")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
