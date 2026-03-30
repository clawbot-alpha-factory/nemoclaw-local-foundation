"""
NemoClaw Execution Engine — SLAService (E-4c)

SLA enforcement (#42): deadline tracking, velocity monitoring, auto-escalation.

NEW FILE: command-center/backend/app/services/sla_service.py
"""
from __future__ import annotations
import logging
import time
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("cc.sla")

class SLAService:
    def __init__(self, alert_service=None):
        self.alert_service = alert_service
        self.slas: dict[str, dict[str, Any]] = {}
        logger.info("SLAService initialized")

    def set_sla(self, project_id: str, target: str, deadline_hours: float, metric_name: str = "tasks") -> dict[str, Any]:
        try:
            float(target)
        except (ValueError, TypeError):
            return {"error": f"Target must be numeric, got: {target}"}
        sla = {
            "project_id": project_id,
            "target": target,
            "deadline_hours": deadline_hours,
            "metric_name": metric_name,
            "created_at": time.time(),
            "current_value": 0,
            "status": "active",
        }
        self.slas[project_id] = sla
        logger.info("SLA set: project %s → %s in %dh", project_id, target, deadline_hours)
        return sla

    def update_progress(self, project_id: str, value: float) -> dict[str, Any] | None:
        sla = self.slas.get(project_id)
        if not sla:
            return None
        sla["current_value"] = value
        elapsed_h = (time.time() - sla["created_at"]) / 3600
        pct_time = elapsed_h / sla["deadline_hours"] * 100 if sla["deadline_hours"] else 0
        try:
            target_val = float(sla["target"])
            pct_progress = value / target_val * 100 if target_val else 0
        except (ValueError, TypeError):
            pct_progress = 0

        if pct_time > 50 and pct_progress < 30 and self.alert_service:
            self.alert_service.fire("warning", f"SLA at risk: {project_id}", f"50% time elapsed, only {pct_progress:.0f}% progress", source="sla")

        if pct_time >= 100:
            sla["status"] = "breached" if pct_progress < 100 else "met"

        return {"sla": sla, "pct_time": round(pct_time, 1), "pct_progress": round(pct_progress, 1)}

    def get_sla(self, project_id: str) -> dict[str, Any] | None:
        return self.slas.get(project_id)

    def get_all(self) -> list[dict[str, Any]]:
        return list(self.slas.values())
