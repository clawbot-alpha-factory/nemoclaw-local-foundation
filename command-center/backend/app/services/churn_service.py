"""
NemoClaw Execution Engine — Churn Service (E-11)

Client health scoring 0-100. Predictive churn detection.
>70: proactive outreach. >90: escalation to executive.
Competitive monitoring loop: daily scan, weekly summary, alerts.

NEW FILE: command-center/backend/app/services/churn_service.py
"""
from __future__ import annotations
import json, logging, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("cc.churn")


class ClientHealth:
    def __init__(self, client_id: str, client_name: str):
        self.client_id = client_id
        self.client_name = client_name
        self.health_score: float = 80.0  # Start healthy
        self.churn_risk: str = "low"  # low, medium, high, critical
        self.factors: dict[str, float] = {
            "deliverable_completion": 8.0,  # 0-10
            "response_time": 8.0,
            "satisfaction": 8.0,
            "engagement": 8.0,
            "payment_history": 10.0,
        }
        self.last_contact: str = datetime.now(timezone.utc).isoformat()
        self.alerts: list[dict[str, Any]] = []
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def update_factor(self, factor: str, value: float) -> None:
        if factor in self.factors:
            self.factors[factor] = max(0, min(10, value))
            self._recalculate()

    def _recalculate(self) -> None:
        weights = {"deliverable_completion": 25, "response_time": 20, "satisfaction": 25, "engagement": 15, "payment_history": 15}
        total = sum(self.factors.get(f, 5) * w for f, w in weights.items()) / sum(weights.values())
        self.health_score = round(total * 10, 1)
        if self.health_score >= 70:
            self.churn_risk = "low"
        elif self.health_score >= 50:
            self.churn_risk = "medium"
        elif self.health_score >= 30:
            self.churn_risk = "high"
        else:
            self.churn_risk = "critical"
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "client_id": self.client_id, "client_name": self.client_name,
            "health_score": self.health_score, "churn_risk": self.churn_risk,
            "factors": self.factors, "last_contact": self.last_contact,
            "alerts": self.alerts[-10:], "updated_at": self.updated_at,
        }


class ChurnService:
    OUTREACH_THRESHOLD = 70
    ESCALATION_THRESHOLD = 40

    def __init__(self, global_state=None, event_bus=None):
        self.global_state = global_state
        self.event_bus = event_bus
        self._clients: dict[str, ClientHealth] = {}
        self._competitors: list[dict[str, Any]] = []
        self._persist_path = Path.home() / ".nemoclaw" / "churn.json"
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        self._load()
        logger.info("ChurnService initialized (%d clients tracked)", len(self._clients))

    def _load(self) -> None:
        if self._persist_path.exists():
            try:
                data = json.loads(self._persist_path.read_text())
                for d in data.get("clients", []):
                    ch = ClientHealth(d["client_id"], d["client_name"])
                    ch.health_score = d.get("health_score", 80)
                    ch.churn_risk = d.get("churn_risk", "low")
                    ch.factors = d.get("factors", ch.factors)
                    ch.last_contact = d.get("last_contact", ch.last_contact)
                    ch.alerts = d.get("alerts", [])
                    self._clients[ch.client_id] = ch
                self._competitors = data.get("competitors", [])
            except Exception as e:
                logger.warning("Failed to load churn data: %s", e)

    def _save(self) -> None:
        try:
            data = {
                "clients": [c.to_dict() for c in self._clients.values()],
                "competitors": self._competitors[-50:],
            }
            self._persist_path.write_text(json.dumps(data, indent=2, default=str))
        except Exception:
            pass

    def track_client(self, client_id: str, client_name: str) -> dict[str, Any]:
        if client_id not in self._clients:
            self._clients[client_id] = ClientHealth(client_id, client_name)
            self._save()
        return self._clients[client_id].to_dict()

    def update_health(self, client_id: str, factor: str, value: float) -> dict[str, Any]:
        ch = self._clients.get(client_id)
        if not ch:
            return {"error": "Client not tracked"}
        old_score = ch.health_score
        ch.update_factor(factor, value)
        self._save()

        # Auto-trigger based on thresholds
        actions: list[str] = []
        if ch.health_score < self.ESCALATION_THRESHOLD and old_score >= self.ESCALATION_THRESHOLD:
            ch.alerts.append({"type": "escalation", "at": datetime.now(timezone.utc).isoformat(),
                            "message": f"Health dropped to {ch.health_score} — escalating"})
            actions.append("escalate_to_executive")
            if self.event_bus:
                self.event_bus.emit("churn_escalation", {"client_id": client_id, "score": ch.health_score})

        elif ch.health_score < self.OUTREACH_THRESHOLD and old_score >= self.OUTREACH_THRESHOLD:
            ch.alerts.append({"type": "proactive_outreach", "at": datetime.now(timezone.utc).isoformat(),
                            "message": f"Health at {ch.health_score} — proactive outreach"})
            actions.append("proactive_outreach")
            if self.event_bus:
                self.event_bus.emit("churn_warning", {"client_id": client_id, "score": ch.health_score})

        self._save()
        return {"client_id": client_id, "health_score": ch.health_score, "churn_risk": ch.churn_risk, "actions": actions}

    def get_client(self, client_id: str) -> dict[str, Any] | None:
        ch = self._clients.get(client_id)
        return ch.to_dict() if ch else None

    def get_at_risk(self) -> list[dict[str, Any]]:
        return [c.to_dict() for c in self._clients.values() if c.health_score < self.OUTREACH_THRESHOLD]

    def add_competitor_intel(self, competitor: str, change_type: str, details: str) -> dict[str, Any]:
        entry = {"competitor": competitor, "change_type": change_type, "details": details,
                "detected_at": datetime.now(timezone.utc).isoformat()}
        self._competitors.append(entry)
        if len(self._competitors) > 200:
            self._competitors = self._competitors[-200:]
        self._save()
        if self.event_bus:
            self.event_bus.emit("competitor_change", entry)
        return entry

    def get_competitor_intel(self, limit: int = 20) -> list[dict[str, Any]]:
        return self._competitors[-limit:]

    def get_stats(self) -> dict[str, Any]:
        risk_counts = {"low": 0, "medium": 0, "high": 0, "critical": 0}
        for c in self._clients.values():
            risk_counts[c.churn_risk] = risk_counts.get(c.churn_risk, 0) + 1
        return {
            "total_clients": len(self._clients),
            "by_risk": risk_counts,
            "at_risk": len(self.get_at_risk()),
            "avg_health": round(sum(c.health_score for c in self._clients.values()) / max(len(self._clients), 1), 1),
            "competitor_entries": len(self._competitors),
        }
