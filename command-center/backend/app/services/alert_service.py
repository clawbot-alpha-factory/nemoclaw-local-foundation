"""
NemoClaw Execution Engine — AlertService (E-4c)

Alerting (#5): failures, bridge down, spend warnings, revenue shutdown.
Channels: WebSocket broadcast, in-memory log (Slack/email in E-8).

NEW FILE: command-center/backend/app/services/alert_service.py
"""
from __future__ import annotations
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("cc.alert")

class AlertSeverity:
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"

class AlertService:
    def __init__(self):
        self.alerts: list[dict[str, Any]] = []
        self._consecutive_failures: dict[str, int] = {}
        logger.info("AlertService initialized")

    def fire(self, severity: str, title: str, message: str, source: str = "", data: dict[str, Any] | None = None) -> dict[str, Any]:
        alert = {
            "alert_id": str(uuid.uuid4())[:8],
            "severity": severity,
            "title": title,
            "message": message,
            "source": source,
            "data": data or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "acknowledged": False,
        }
        self.alerts.append(alert)
        if len(self.alerts) > 1000:
            self.alerts = self.alerts[-1000:]
        logger.warning("ALERT [%s] %s: %s", severity, title, message[:100])
        return alert

    def record_failure(self, component: str) -> dict[str, Any] | None:
        count = self._consecutive_failures.get(component, 0) + 1
        self._consecutive_failures[component] = count
        if count >= 3:
            self._consecutive_failures[component] = 0
            return self.fire(AlertSeverity.CRITICAL, f"{component} consecutive failures", f"{count} consecutive failures detected", source=component)
        return None

    def record_success(self, component: str):
        self._consecutive_failures[component] = 0

    def spend_warning(self, current: float, ceiling: float):
        pct = current / ceiling * 100 if ceiling else 0
        if pct >= 80:
            self.fire(AlertSeverity.WARNING, "Spend at 80%", f"${current:.2f} of ${ceiling:.2f} ceiling ({pct:.0f}%)", source="guardrails")

    def get_alerts(self, limit: int = 50, severity: str = "") -> list[dict[str, Any]]:
        alerts = self.alerts
        if severity:
            alerts = [a for a in alerts if a["severity"] == severity]
        return alerts[-limit:]

    def acknowledge(self, alert_id: str) -> bool:
        for a in self.alerts:
            if a["alert_id"] == alert_id:
                a["acknowledged"] = True
                return True
        return False
