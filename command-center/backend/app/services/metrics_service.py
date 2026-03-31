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

    # ── Time-Range Aggregation (P-6) ────────────────────────────────

    MAX_RANGE_DAYS = 365

    def query_range(self, after: str, before: str) -> list[dict[str, Any]]:
        """Return snapshots within date range. Inclusive after, exclusive before, UTC.

        Snapshots sorted ascending by date.
        """
        results = []
        for snap in self._snapshots:
            date = snap.get("date", "")
            if not date:
                continue
            if date >= after and date < before:
                results.append(snap)
        results.sort(key=lambda s: s.get("date", ""))
        return results

    def aggregate(self, after: str, before: str) -> dict[str, Any]:
        """Compute avg/min/max/sum/count/first/last/trend/change_pct per numeric metric.

        Only aggregates fields that are int or float. Skips strings, dicts, lists.
        Division-by-zero guarded: change_pct = None when first is 0.
        Empty ranges return zeroed aggregation with count=0.
        """
        # Validate range
        self._validate_range(after, before)

        snapshots = self.query_range(after, before)
        count = len(snapshots)

        if count == 0:
            return {
                "after": after,
                "before": before,
                "count": 0,
                "metrics": {},
                "note": "No snapshots in range",
            }

        # Collect numeric fields
        numeric_keys: set[str] = set()
        for snap in snapshots:
            for k, v in snap.items():
                if isinstance(v, (int, float)) and k != "date":
                    numeric_keys.add(k)

        metrics: dict[str, Any] = {}
        for key in sorted(numeric_keys):
            values = []
            for snap in snapshots:
                v = snap.get(key)
                if isinstance(v, (int, float)):
                    values.append(float(v))

            if not values:
                continue

            first_val = values[0]
            last_val = values[-1]
            avg_val = sum(values) / len(values)

            # Trend: compare first vs last
            if last_val > first_val:
                trend = "up"
            elif last_val < first_val:
                trend = "down"
            else:
                trend = "flat"

            # Change pct: guard division by zero
            if first_val != 0:
                change_pct = round((last_val - first_val) / abs(first_val) * 100, 2)
            else:
                change_pct = None

            metrics[key] = {
                "avg": round(avg_val, 4),
                "min": round(min(values), 4),
                "max": round(max(values), 4),
                "sum": round(sum(values), 4),
                "count": len(values),
                "first": first_val,
                "last": last_val,
                "trend": trend,
                "change_pct": change_pct,
            }

        return {
            "after": after,
            "before": before,
            "count": count,
            "metrics": metrics,
        }

    def compare_periods(
        self,
        a_after: str, a_before: str,
        b_after: str, b_before: str,
    ) -> dict[str, Any]:
        """Compare two date ranges. Returns delta + pct_change per metric.

        Includes count mismatch warning if sample sizes differ >50%.
        """
        agg_a = self.aggregate(a_after, a_before)
        agg_b = self.aggregate(b_after, b_before)

        comparison: dict[str, Any] = {}
        all_keys = set(agg_a.get("metrics", {}).keys()) | set(agg_b.get("metrics", {}).keys())

        for key in sorted(all_keys):
            a_avg = agg_a.get("metrics", {}).get(key, {}).get("avg", 0)
            b_avg = agg_b.get("metrics", {}).get(key, {}).get("avg", 0)
            delta = round(b_avg - a_avg, 4)

            if a_avg != 0:
                change_pct = round(delta / abs(a_avg) * 100, 2)
            else:
                change_pct = None

            if b_avg > a_avg:
                direction = "up"
            elif b_avg < a_avg:
                direction = "down"
            else:
                direction = "flat"

            comparison[key] = {
                "a_avg": a_avg,
                "b_avg": b_avg,
                "delta": delta,
                "change_pct": change_pct,
                "direction": direction,
            }

        # Count mismatch warning
        a_count = agg_a.get("count", 0)
        b_count = agg_b.get("count", 0)
        warning = ""
        if a_count > 0 and b_count > 0:
            ratio = min(a_count, b_count) / max(a_count, b_count)
            if ratio < 0.5:
                warning = f"Unequal sample sizes: period_a={a_count}, period_b={b_count}"

        return {
            "period_a": {"after": a_after, "before": a_before, "count": a_count, "aggregation": agg_a.get("metrics", {})},
            "period_b": {"after": b_after, "before": b_before, "count": b_count, "aggregation": agg_b.get("metrics", {})},
            "comparison": comparison,
            "warning": warning,
        }

    def get_period_preset(self, preset: str) -> dict[str, Any]:
        """Get aggregation or comparison for a preset period.

        Presets use full days excluding today.
        "7d" = last 7 complete days (yesterday back 7), compared to previous 7.
        """
        valid_presets = {"24h": 1, "7d": 7, "30d": 30, "90d": 90}
        if preset not in valid_presets:
            raise ValueError(f"Invalid preset '{preset}'. Must be one of: {', '.join(valid_presets)}")

        days = valid_presets[preset]
        today = datetime.now(timezone.utc).date()

        # Period B (recent): yesterday back N days
        b_before = today.isoformat()  # exclusive: today not included
        b_after = (today - timedelta(days=days)).isoformat()

        # Period A (previous): the N days before period B
        a_before = b_after
        a_after = (today - timedelta(days=days * 2)).isoformat()

        return self.compare_periods(a_after, a_before, b_after, b_before)

    def _validate_range(self, after: str, before: str) -> None:
        """Validate date range. Max 365 days."""
        try:
            a = datetime.fromisoformat(after).date() if "T" not in after else datetime.fromisoformat(after.replace("Z", "+00:00")).date()
            b = datetime.fromisoformat(before).date() if "T" not in before else datetime.fromisoformat(before.replace("Z", "+00:00")).date()
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid date format: {e}")

        span = (b - a).days
        if span > self.MAX_RANGE_DAYS:
            raise ValueError(f"Range spans {span} days — max is {self.MAX_RANGE_DAYS}")
        if span < 0:
            raise ValueError("'after' must be before 'before'")

