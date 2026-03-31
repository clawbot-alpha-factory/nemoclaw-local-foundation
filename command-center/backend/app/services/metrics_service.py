"""
NemoClaw Execution Engine — Metrics Service (E-12)

System-wide metrics: cost/lead, conversion rate, revenue/channel,
ROI/workflow, agent efficiency. Powers the autonomous dashboard.

NEW FILE: command-center/backend/app/services/metrics_service.py
"""
from __future__ import annotations
import json, logging, time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger("cc.metrics")


class MetricsService:
    """
    Aggregates metrics from all services into a unified dashboard.

    Pulls from: PipelineService, AttributionService, GlobalStateService,
    ABTestService, ChurnService, BridgeManager, GuardrailService.
    """

    def __init__(self, pipeline=None, attribution=None, global_state=None,
                 ab_test=None, churn=None, bridge_manager=None, guardrail=None,
                 skill_agent_mapping=None):
        self.pipeline = pipeline
        self.attribution = attribution
        self.global_state = global_state
        self.ab_test = ab_test
        self.churn = churn
        self.bridge_manager = bridge_manager
        self.guardrail = guardrail
        self.skill_agent_mapping = skill_agent_mapping
        self._snapshots: list[dict[str, Any]] = []
        self._persist_path = Path.home() / ".nemoclaw" / "metrics-history.json"
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        self._load_history()
        logger.info("MetricsService initialized")

    def _load_history(self) -> None:
        if self._persist_path.exists():
            try:
                self._snapshots = json.loads(self._persist_path.read_text())
            except Exception:
                pass

    def _save_history(self) -> None:
        try:
            self._persist_path.write_text(json.dumps(self._snapshots[-100:], indent=2, default=str))
        except Exception:
            pass

    def get_dashboard(self) -> dict[str, Any]:
        """Complete metrics dashboard."""
        now = datetime.now(timezone.utc).isoformat()
        dashboard = {"timestamp": now, "revenue": {}, "pipeline": {}, "agents": {},
                    "skills": {}, "bridges": {}, "health": {}, "costs": {}}

        # Pipeline metrics
        if self.pipeline:
            p = self.pipeline.get_pipeline()
            f = self.pipeline.get_forecast()
            dashboard["pipeline"] = {
                "total_deals": p.get("total_deals", 0),
                "total_value": p.get("total_value", 0),
                "stages": p.get("stages", {}),
                "conversion_rates": p.get("conversion_rates", {}),
                "weighted_forecast": f.get("weighted_pipeline", 0),
                "stale_deals": len(self.pipeline.get_stale_deals()),
            }

        # Attribution / Revenue metrics
        if self.attribution:
            stats = self.attribution.get_stats()
            dashboard["revenue"] = {
                "total_revenue": stats.get("total_revenue", 0),
                "total_spend": stats.get("total_spend", 0),
                "overall_roi": round(
                    (stats.get("total_revenue", 0) - stats.get("total_spend", 0)) /
                    max(stats.get("total_spend", 0), 0.01), 2
                ),
                "channel_roi": stats.get("channel_roi", {}),
                "leads_tracked": stats.get("total_leads_tracked", 0),
            }

        # A/B Test metrics
        if self.ab_test:
            tests = self.ab_test.get_all()
            dashboard["experiments"] = {
                "total": len(tests),
                "running": sum(1 for t in tests if t["status"] == "running"),
                "completed": sum(1 for t in tests if t["status"] == "completed"),
            }

        # Client health
        if self.churn:
            dashboard["health"] = self.churn.get_stats()

        # Bridge usage
        if self.bridge_manager:
            dashboard["bridges"] = self.bridge_manager.get_status()

        # Guardrail / costs
        if self.guardrail:
            dashboard["costs"] = {
                "daily_spent": getattr(self.guardrail, '_daily_spent', 0),
                "ceiling": getattr(self.guardrail, '_ceiling', 20),
            }

        # Agent efficiency
        if self.skill_agent_mapping:
            dashboard["agents"] = self.skill_agent_mapping.get_stats()

        # Skill performance from global state
        if self.global_state:
            dashboard["skills"] = {
                "performance": self.global_state.get_skill_performance(),
                "channel_roi": self.global_state.get_channel_roi(),
            }

        return dashboard

    def get_roi_report(self) -> dict[str, Any]:
        """Focused ROI report."""
        if not self.attribution:
            return {"error": "Attribution not available"}
        return self.attribution.get_stats()

    def get_daily_summary(self) -> dict[str, Any]:
        """Quick daily summary for executive review."""
        dashboard = self.get_dashboard()
        return {
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "revenue": dashboard.get("revenue", {}).get("total_revenue", 0),
            "pipeline_value": dashboard.get("pipeline", {}).get("total_value", 0),
            "weighted_forecast": dashboard.get("pipeline", {}).get("weighted_forecast", 0),
            "deals": dashboard.get("pipeline", {}).get("total_deals", 0),
            "stale_deals": dashboard.get("pipeline", {}).get("stale_deals", 0),
            "at_risk_clients": dashboard.get("health", {}).get("at_risk", 0),
            "experiments_running": dashboard.get("experiments", {}).get("running", 0),
            "daily_spend": dashboard.get("costs", {}).get("daily_spent", 0),
        }

    def take_snapshot(self) -> dict[str, Any]:
        """Take a metrics snapshot for trend analysis."""
        summary = self.get_daily_summary()
        self._snapshots.append(summary)
        if len(self._snapshots) > 365:
            self._snapshots = self._snapshots[-365:]
        self._save_history()
        return summary


    def check_thresholds(self) -> list[dict[str, Any]]:
        """Check metric thresholds and return breaches."""
        dashboard = self.get_dashboard()
        breaches = []
        pipeline = dashboard.get("pipeline", {})
        revenue = dashboard.get("revenue", {})
        health = dashboard.get("health", {})

        if pipeline.get("stale_deals", 0) > 3:
            breaches.append({"metric": "stale_deals", "value": pipeline["stale_deals"], "threshold": 3, "action": "rev-11-follow-up-enforcer"})
        if revenue.get("overall_roi", 1) < 0:
            breaches.append({"metric": "negative_roi", "value": revenue["overall_roi"], "threshold": 0, "action": "rev-12-risk-capital-allocator"})
        if health.get("at_risk", 0) > 0:
            breaches.append({"metric": "at_risk_clients", "value": health["at_risk"], "threshold": 0, "action": "biz-05-client-health-monitor"})
        if pipeline.get("total_deals", 1) == 0:
            breaches.append({"metric": "empty_pipeline", "value": 0, "threshold": 1, "action": "rev-10-lead-source-engine"})

        return breaches

    def get_trends(self, days: int = 7) -> list[dict[str, Any]]:
        """Get metric trends over N days."""
        return self._snapshots[-days:]
