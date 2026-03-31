"""
NemoClaw Execution Engine — Onboarding Service (E-11)

6-stage client onboarding: payment_confirmed → welcome_sent → setup_complete →
first_checkin → review → health_monitoring.

Each stage triggers agent actions via event bus.

NEW FILE: command-center/backend/app/services/onboarding_service.py
"""
from __future__ import annotations
import json, logging, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("cc.onboarding")

STAGES = ["payment_confirmed", "welcome_sent", "setup_complete", "first_checkin", "review", "health_monitoring"]
STAGE_TRIGGERS = {
    "payment_confirmed": "biz-04-client-onboarding-sequence",
    "welcome_sent": "out-02-email-executor",
    "setup_complete": "biz-05-client-health-monitor",
    "first_checkin": "out-02-email-executor",
    "review": "biz-06-upsell-opportunity-detector",
    "health_monitoring": "biz-05-client-health-monitor",
}
STAGE_DAYS = {"payment_confirmed": 0, "welcome_sent": 0, "setup_complete": 3, "first_checkin": 7, "review": 14, "health_monitoring": 30}


class OnboardingRecord:
    def __init__(self, client_id: str, client_name: str, service_id: str = "",
                 agent: str = "client_success_lead"):
        self.client_id = client_id
        self.client_name = client_name
        self.service_id = service_id
        self.agent = agent
        self.stage = "payment_confirmed"
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.updated_at = self.created_at
        self.stage_history: list[dict[str, Any]] = [{"stage": self.stage, "at": self.created_at}]
        self.completed: bool = False
        self.satisfaction_score: float | None = None
        self.notes: list[str] = []

    def advance(self, new_stage: str) -> dict[str, Any] | None:
        if new_stage not in STAGES:
            return {"error": f"Invalid stage: {new_stage}"}
        curr_idx = STAGES.index(self.stage)
        new_idx = STAGES.index(new_stage)
        if new_idx <= curr_idx:
            return {"error": f"Cannot go backwards: {self.stage} → {new_stage}"}
        self.stage = new_stage
        self.updated_at = datetime.now(timezone.utc).isoformat()
        self.stage_history.append({"stage": new_stage, "at": self.updated_at})
        if new_stage == "health_monitoring":
            self.completed = True
        trigger = STAGE_TRIGGERS.get(new_stage)
        return {"trigger_skill": trigger, "client_id": self.client_id, "new_stage": new_stage}

    def to_dict(self) -> dict[str, Any]:
        return {
            "client_id": self.client_id, "client_name": self.client_name,
            "service_id": self.service_id, "agent": self.agent,
            "stage": self.stage, "completed": self.completed,
            "satisfaction_score": self.satisfaction_score,
            "created_at": self.created_at, "updated_at": self.updated_at,
            "stage_history": self.stage_history, "notes": self.notes,
            "days_since_start": self._days_since_start(),
        }

    def _days_since_start(self) -> float:
        try:
            dt = datetime.fromisoformat(self.created_at)
            return round((datetime.now(timezone.utc) - dt).total_seconds() / 86400, 1)
        except Exception:
            return 0


class OnboardingService:
    def __init__(self, global_state=None, event_bus=None):
        self.global_state = global_state
        self.event_bus = event_bus
        self._records: dict[str, OnboardingRecord] = {}
        self._persist_path = Path.home() / ".nemoclaw" / "onboarding.json"
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        self._load()
        logger.info("OnboardingService initialized (%d records)", len(self._records))

    def _load(self) -> None:
        if self._persist_path.exists():
            try:
                data = json.loads(self._persist_path.read_text())
                for d in data:
                    r = OnboardingRecord(d["client_id"], d["client_name"], d.get("service_id", ""), d.get("agent", ""))
                    r.stage = d.get("stage", "payment_confirmed")
                    r.created_at = d.get("created_at", r.created_at)
                    r.updated_at = d.get("updated_at", r.updated_at)
                    r.stage_history = d.get("stage_history", [])
                    r.completed = d.get("completed", False)
                    r.satisfaction_score = d.get("satisfaction_score")
                    r.notes = d.get("notes", [])
                    self._records[r.client_id] = r
            except Exception as e:
                logger.warning("Failed to load onboarding: %s", e)

    def _save(self) -> None:
        try:
            self._persist_path.write_text(json.dumps([r.to_dict() for r in self._records.values()], indent=2, default=str))
        except Exception as e:
            logger.warning("Failed to save onboarding: %s", e)

    def start_onboarding(self, client_id: str, client_name: str, service_id: str = "") -> dict[str, Any]:
        if client_id in self._records:
            return {"error": "Onboarding already exists", "client_id": client_id}
        record = OnboardingRecord(client_id, client_name, service_id)
        self._records[client_id] = record
        self._save()
        if self.event_bus:
            self.event_bus.emit("onboarding_started", {"client_id": client_id, "client_name": client_name})
        return record.to_dict()

    def advance_stage(self, client_id: str, new_stage: str) -> dict[str, Any]:
        record = self._records.get(client_id)
        if not record:
            return {"error": "Onboarding not found"}
        result = record.advance(new_stage)
        if result and "error" not in result:
            self._save()
            if self.event_bus:
                self.event_bus.emit("onboarding_advanced", {"client_id": client_id, "stage": new_stage})
        return result or {}

    def set_satisfaction(self, client_id: str, score: float) -> dict[str, Any]:
        record = self._records.get(client_id)
        if not record:
            return {"error": "Onboarding not found"}
        record.satisfaction_score = max(0, min(10, score))
        self._save()
        return {"client_id": client_id, "satisfaction_score": record.satisfaction_score}

    def get_record(self, client_id: str) -> dict[str, Any] | None:
        r = self._records.get(client_id)
        return r.to_dict() if r else None

    def get_all(self) -> list[dict[str, Any]]:
        return [r.to_dict() for r in self._records.values()]

    def get_due_actions(self) -> list[dict[str, Any]]:
        actions = []
        for r in self._records.values():
            if r.completed:
                continue
            days = r._days_since_start()
            curr_idx = STAGES.index(r.stage)
            for i in range(curr_idx + 1, len(STAGES)):
                next_stage = STAGES[i]
                if days >= STAGE_DAYS[next_stage]:
                    actions.append({
                        "client_id": r.client_id, "client_name": r.client_name,
                        "current_stage": r.stage, "due_stage": next_stage,
                        "trigger_skill": STAGE_TRIGGERS.get(next_stage),
                        "days_overdue": round(days - STAGE_DAYS[next_stage], 1),
                    })
                    break
        return actions

    def get_stats(self) -> dict[str, Any]:
        by_stage = {s: 0 for s in STAGES}
        for r in self._records.values():
            by_stage[r.stage] = by_stage.get(r.stage, 0) + 1
        completed = sum(1 for r in self._records.values() if r.completed)
        return {"total": len(self._records), "completed": completed, "by_stage": by_stage, "due_actions": len(self.get_due_actions())}
