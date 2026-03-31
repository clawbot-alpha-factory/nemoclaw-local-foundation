"""
NemoClaw Execution Engine — Insight → Action Bridge (E-12)

Converts audit findings + metric thresholds into executable skill calls.
Routes through PriorityEngine for scheduling.
Logs decision→action→result chains for learning.

NEW FILE: command-center/backend/app/services/insight_action_bridge.py
"""
from __future__ import annotations
import json, logging, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("cc.insight_bridge")

# ── METRIC THRESHOLDS ──────────────────────────────────────────────
METRIC_THRESHOLDS = {
    "roi_negative": {
        "condition": lambda m: m.get("revenue", {}).get("overall_roi", 1) < 0,
        "skill": "rev-12-risk-capital-allocator",
        "priority": "critical",
        "description": "Negative ROI detected — reallocate resources",
    },
    "no_deals": {
        "condition": lambda m: m.get("pipeline", {}).get("total_deals", 1) == 0,
        "skill": "rev-10-lead-source-engine",
        "priority": "critical",
        "description": "No deals in pipeline — generate leads",
    },
    "stale_deals": {
        "condition": lambda m: m.get("pipeline", {}).get("stale_deals", 0) > 3,
        "skill": "rev-11-follow-up-enforcer",
        "priority": "high",
        "description": "Multiple stale deals — trigger follow-up",
    },
    "high_churn_risk": {
        "condition": lambda m: m.get("health", {}).get("at_risk", 0) > 0,
        "skill": "biz-05-client-health-monitor",
        "priority": "high",
        "description": "Clients at risk — proactive outreach",
    },
    "spend_near_ceiling": {
        "condition": lambda m: m.get("costs", {}).get("daily_spent", 0) > m.get("costs", {}).get("ceiling", 20) * 0.8,
        "skill": "rev-23-resource-allocator",
        "priority": "high",
        "description": "Approaching spend ceiling — optimize allocation",
    },
    "low_conversion": {
        "condition": lambda m: any(v < 5 for v in m.get("pipeline", {}).get("conversion_rates", {}).values()),
        "skill": "rev-13-live-experiment-runner",
        "priority": "medium",
        "description": "Low conversion rate detected — run experiments",
    },
}

# ── FINDING → SKILL MAP ──────────────────────────────────────────
FINDING_SKILL_MAP = {
    "revenue": "rev-16-speed-to-revenue-optimizer",
    "skills": "rev-19-system-learning-engine",
    "costs": "rev-12-risk-capital-allocator",
    "agents": "rev-06-revenue-orchestrator",
    "pipeline": "rev-11-follow-up-enforcer",
    "health": "biz-05-client-health-monitor",
}


class InsightActionBridge:
    """
    Converts insights into actions.

    Two inputs:
    1. Audit findings → skill triggers (from SelfImprovementService)
    2. Metric thresholds → skill triggers (from MetricsService)

    Output: Tasks added to PriorityEngine for execution by AutonomousLoop.
    """

    def __init__(self, priority_engine=None, metrics=None, global_state=None):
        self.priority_engine = priority_engine
        self.metrics = metrics
        self.global_state = global_state
        self._action_log: list[dict[str, Any]] = []
        self._persist_path = Path.home() / ".nemoclaw" / "insight-actions.json"
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info("InsightActionBridge initialized (%d thresholds, %d finding maps)",
                    len(METRIC_THRESHOLDS), len(FINDING_SKILL_MAP))

    def check_metrics(self) -> list[dict[str, Any]]:
        """Check all metric thresholds and generate actions."""
        if not self.metrics:
            return []

        dashboard = self.metrics.get_dashboard()
        triggered = []

        for name, threshold in METRIC_THRESHOLDS.items():
            try:
                if threshold["condition"](dashboard):
                    action = {
                        "trigger": name,
                        "skill": threshold["skill"],
                        "priority": threshold["priority"],
                        "description": threshold["description"],
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    triggered.append(action)

                    # Add to priority engine
                    if self.priority_engine:
                        factors = {
                            "urgency": 9 if threshold["priority"] == "critical" else 7,
                            "value": 8,
                            "staleness": 5,
                            "confidence": 9,
                            "agent_fit": 8,
                        }
                        self.priority_engine.add_task(
                            f"insight-{name}-{int(time.time())}",
                            "metric_threshold",
                            threshold["description"],
                            factors=factors,
                            metadata={"skill_id": threshold["skill"]},
                        )

                    self._log_action(action)
            except Exception as e:
                logger.warning("Threshold check failed for %s: %s", name, e)

        if triggered:
            logger.info("InsightBridge: %d metric thresholds triggered", len(triggered))
        return triggered

    def process_audit_findings(self, findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert audit findings into prioritized tasks."""
        actions = []

        for finding in findings:
            severity = finding.get("severity", "info")
            if severity not in ("critical", "high"):
                continue

            category = finding.get("category", "")
            skill_id = FINDING_SKILL_MAP.get(category)
            if not skill_id:
                continue

            action = {
                "trigger": f"audit:{category}",
                "skill": skill_id,
                "priority": severity,
                "description": finding.get("description", ""),
                "recommendation": finding.get("recommendation", ""),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            actions.append(action)

            if self.priority_engine:
                self.priority_engine.add_task(
                    f"audit-finding-{category}-{int(time.time())}",
                    "audit_finding",
                    finding.get("description", ""),
                    factors={"urgency": 9 if severity == "critical" else 6,
                            "value": 7, "staleness": 3, "confidence": 8, "agent_fit": 7},
                    metadata={"skill_id": skill_id},
                )

            self._log_action(action)

        if actions:
            logger.info("InsightBridge: %d audit findings → actions", len(actions))
        return actions

    def _log_action(self, action: dict[str, Any]) -> None:
        self._action_log.append(action)
        if len(self._action_log) > 500:
            self._action_log = self._action_log[-500:]
        try:
            self._persist_path.write_text(
                json.dumps(self._action_log[-100:], indent=2, default=str)
            )
        except Exception:
            pass

    def get_action_log(self, limit: int = 50) -> list[dict[str, Any]]:
        return self._action_log[-limit:]

    def get_stats(self) -> dict[str, Any]:
        return {
            "thresholds": len(METRIC_THRESHOLDS),
            "finding_maps": len(FINDING_SKILL_MAP),
            "actions_logged": len(self._action_log),
        }
