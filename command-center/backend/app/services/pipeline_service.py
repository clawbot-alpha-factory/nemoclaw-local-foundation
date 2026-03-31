"""
NemoClaw Execution Engine — Pipeline Service (E-10)

8-stage deal pipeline: new → contacted → replied → call_booked →
proposal_sent → negotiation → won → paid.
Transitions trigger agent actions. Conversion rates. Forecast.

NEW FILE: command-center/backend/app/services/pipeline_service.py
"""
from __future__ import annotations
import json, logging, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("cc.pipeline")

STAGES = ["new", "contacted", "replied", "call_booked", "proposal_sent", "negotiation", "won", "paid"]
STAGE_ACTIONS = {
    "new": "rev-02-lead-qualification-engine",
    "contacted": "out-04-follow-up-intelligence",
    "replied": "rev-01-autonomous-sales-closer",
    "call_booked": "biz-01-proposal-generator",
    "proposal_sent": "rev-11-follow-up-enforcer",
    "negotiation": "rev-01-autonomous-sales-closer",
    "won": "biz-02-contract-drafter",
    "paid": "biz-04-client-onboarding-sequence",
}

class Deal:
    def __init__(self, deal_id: str, lead_name: str, value: float = 0,
                 stage: str = "new", agent: str = "", source: str = ""):
        self.deal_id = deal_id
        self.lead_name = lead_name
        self.value = value
        self.stage = stage
        self.agent = agent
        self.source = source
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.updated_at = self.created_at
        self.stage_history: list[dict[str, Any]] = [{"stage": stage, "at": self.created_at}]
        self.notes: list[str] = []

    def advance(self, new_stage: str) -> dict[str, Any] | None:
        if new_stage not in STAGES:
            return {"error": f"Invalid stage: {new_stage}"}
        curr_idx = STAGES.index(self.stage)
        new_idx = STAGES.index(new_stage)
        if new_idx <= curr_idx:
            return {"error": f"Cannot move backwards: {self.stage} → {new_stage}"}
        self.stage = new_stage
        self.updated_at = datetime.now(timezone.utc).isoformat()
        self.stage_history.append({"stage": new_stage, "at": self.updated_at})
        return {"trigger_skill": STAGE_ACTIONS.get(new_stage), "deal_id": self.deal_id, "new_stage": new_stage}

    def to_dict(self) -> dict[str, Any]:
        return {
            "deal_id": self.deal_id, "lead_name": self.lead_name, "value": self.value,
            "stage": self.stage, "agent": self.agent, "source": self.source,
            "created_at": self.created_at, "updated_at": self.updated_at,
            "stage_history": self.stage_history, "days_in_stage": self._days_in_stage(),
        }

    def _days_in_stage(self) -> float:
        if not self.stage_history:
            return 0
        last = self.stage_history[-1]["at"]
        try:
            dt = datetime.fromisoformat(last)
            return round((datetime.now(timezone.utc) - dt).total_seconds() / 86400, 1)
        except Exception:
            return 0


class PipelineService:
    def __init__(self, global_state=None, event_bus=None):
        self.global_state = global_state
        self.event_bus = event_bus
        self._deals: dict[str, Deal] = {}
        self._persist_path = Path.home() / ".nemoclaw" / "pipeline.json"
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        self._load()
        logger.info("PipelineService initialized (%d deals, 8 stages)", len(self._deals))

    def _load(self) -> None:
        if self._persist_path.exists():
            try:
                data = json.loads(self._persist_path.read_text())
                for d in data:
                    deal = Deal(d["deal_id"], d["lead_name"], d.get("value", 0),
                               d.get("stage", "new"), d.get("agent", ""), d.get("source", ""))
                    deal.created_at = d.get("created_at", deal.created_at)
                    deal.updated_at = d.get("updated_at", deal.updated_at)
                    deal.stage_history = d.get("stage_history", [])
                    self._deals[deal.deal_id] = deal
            except Exception as e:
                logger.warning("Failed to load pipeline: %s", e)

    def _save(self) -> None:
        try:
            data = [d.to_dict() for d in self._deals.values()]
            self._persist_path.write_text(json.dumps(data, indent=2, default=str))
        except Exception as e:
            logger.warning("Failed to save pipeline: %s", e)

    def create_deal(self, deal_id: str, lead_name: str, value: float = 0,
                    agent: str = "", source: str = "") -> dict[str, Any]:
        if deal_id in self._deals:
            return {"error": "Deal already exists", "deal_id": deal_id}
        deal = Deal(deal_id, lead_name, value, "new", agent, source)
        self._deals[deal_id] = deal
        self._save()
        if self.global_state:
            self.global_state.add("deals", deal_id, deal.to_dict(), agent=agent, tags=["new"])
        if self.event_bus:
            self.event_bus.emit("deal_created", {"deal_id": deal_id, "value": value})
        return deal.to_dict()

    def advance_deal(self, deal_id: str, new_stage: str) -> dict[str, Any]:
        deal = self._deals.get(deal_id)
        if not deal:
            return {"error": "Deal not found"}
        result = deal.advance(new_stage)
        if result and "error" not in result:
            self._save()
            if self.global_state:
                self.global_state.add("deals", deal_id, deal.to_dict(), tags=[new_stage])
            if self.event_bus:
                self.event_bus.emit("deal_advanced", {"deal_id": deal_id, "stage": new_stage, "trigger": result.get("trigger_skill")})
        return result or {}

    def get_deal(self, deal_id: str) -> dict[str, Any] | None:
        deal = self._deals.get(deal_id)
        return deal.to_dict() if deal else None

    def get_pipeline(self) -> dict[str, Any]:
        by_stage = {s: [] for s in STAGES}
        total_value = 0
        for deal in self._deals.values():
            by_stage[deal.stage].append(deal.to_dict())
            total_value += deal.value
        conversion = {}
        for i in range(len(STAGES) - 1):
            curr = len(by_stage[STAGES[i]]) + sum(len(by_stage[STAGES[j]]) for j in range(i + 1, len(STAGES)))
            nxt = sum(len(by_stage[STAGES[j]]) for j in range(i + 1, len(STAGES)))
            conversion[f"{STAGES[i]}→{STAGES[i+1]}"] = round(nxt / max(curr, 1) * 100, 1)
        return {
            "stages": {s: len(deals) for s, deals in by_stage.items()},
            "total_deals": len(self._deals),
            "total_value": total_value,
            "conversion_rates": conversion,
            "deals": [d.to_dict() for d in self._deals.values()],
        }

    def get_stale_deals(self, days: float = 3) -> list[dict[str, Any]]:
        return [d.to_dict() for d in self._deals.values() if d._days_in_stage() > days and d.stage not in ("won", "paid")]

    def get_forecast(self) -> dict[str, Any]:
        stage_weights = {"new": 0.05, "contacted": 0.1, "replied": 0.2, "call_booked": 0.4,
                        "proposal_sent": 0.6, "negotiation": 0.8, "won": 0.95, "paid": 1.0}
        weighted = sum(d.value * stage_weights.get(d.stage, 0) for d in self._deals.values())
        return {"weighted_pipeline": round(weighted, 2), "total_pipeline": round(sum(d.value for d in self._deals.values()), 2), "deal_count": len(self._deals)}
