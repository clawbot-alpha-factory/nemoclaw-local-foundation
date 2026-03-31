"""
NemoClaw Execution Engine — Attribution Service (E-10)

Multi-touch attribution. Spend → lead → revenue. Channel ROI.

NEW FILE: command-center/backend/app/services/attribution_service.py
"""
from __future__ import annotations
import json, logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("cc.attribution")


class TouchPoint:
    def __init__(self, channel: str, action: str, cost: float = 0):
        self.channel = channel
        self.action = action
        self.cost = cost
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {"channel": self.channel, "action": self.action, "cost": self.cost, "timestamp": self.timestamp}


class AttributionService:
    def __init__(self, global_state=None):
        self.global_state = global_state
        self._touchpoints: dict[str, list[TouchPoint]] = {}  # lead_id → touchpoints
        self._revenue: dict[str, float] = {}  # lead_id → revenue
        self._channel_spend: dict[str, float] = {}
        self._persist_path = Path.home() / ".nemoclaw" / "attribution.json"
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info("AttributionService initialized")

    def record_touch(self, lead_id: str, channel: str, action: str, cost: float = 0) -> dict[str, Any]:
        if lead_id not in self._touchpoints:
            self._touchpoints[lead_id] = []
        tp = TouchPoint(channel, action, cost)
        self._touchpoints[lead_id].append(tp)
        self._channel_spend[channel] = self._channel_spend.get(channel, 0) + cost
        self._save()
        return {"status": "recorded", "lead_id": lead_id, "channel": channel, "touches": len(self._touchpoints[lead_id])}

    def record_revenue(self, lead_id: str, amount: float) -> dict[str, Any]:
        self._revenue[lead_id] = self._revenue.get(lead_id, 0) + amount
        self._save()
        if self.global_state:
            self.global_state.record_performance("revenue", True, amount, self._primary_channel(lead_id))
        return {"status": "recorded", "lead_id": lead_id, "total_revenue": self._revenue[lead_id]}

    def _primary_channel(self, lead_id: str) -> str:
        touches = self._touchpoints.get(lead_id, [])
        if not touches:
            return "unknown"
        channels = [t.channel for t in touches]
        return max(set(channels), key=channels.count)

    def get_channel_roi(self) -> dict[str, Any]:
        channel_rev: dict[str, float] = {}
        for lead_id, revenue in self._revenue.items():
            touches = self._touchpoints.get(lead_id, [])
            if not touches:
                continue
            per_touch = revenue / len(touches)
            for tp in touches:
                channel_rev[tp.channel] = channel_rev.get(tp.channel, 0) + per_touch

        roi = {}
        for ch in set(list(self._channel_spend.keys()) + list(channel_rev.keys())):
            spend = self._channel_spend.get(ch, 0)
            rev = channel_rev.get(ch, 0)
            roi[ch] = {
                "spend": round(spend, 2), "revenue": round(rev, 2),
                "roi": round((rev - spend) / max(spend, 0.01), 2),
                "leads_touched": sum(1 for tps in self._touchpoints.values() if any(t.channel == ch for t in tps)),
            }
        return roi

    def get_lead_journey(self, lead_id: str) -> dict[str, Any]:
        touches = self._touchpoints.get(lead_id, [])
        return {
            "lead_id": lead_id,
            "touchpoints": [t.to_dict() for t in touches],
            "total_touches": len(touches),
            "revenue": self._revenue.get(lead_id, 0),
            "channels": list(set(t.channel for t in touches)),
        }

    def get_stats(self) -> dict[str, Any]:
        return {
            "total_leads_tracked": len(self._touchpoints),
            "total_revenue": round(sum(self._revenue.values()), 2),
            "total_spend": round(sum(self._channel_spend.values()), 2),
            "channels": list(self._channel_spend.keys()),
            "channel_roi": self.get_channel_roi(),
        }

    def _save(self) -> None:
        try:
            data = {
                "touchpoints": {lid: [t.to_dict() for t in tps] for lid, tps in self._touchpoints.items()},
                "revenue": self._revenue,
                "channel_spend": self._channel_spend,
            }
            self._persist_path.write_text(json.dumps(data, indent=2, default=str))
        except Exception:
            pass
