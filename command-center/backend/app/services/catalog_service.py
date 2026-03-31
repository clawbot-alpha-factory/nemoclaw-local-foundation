"""
NemoClaw Execution Engine — Catalog Service (E-10)

Product/service catalog with pricing, tiers.
Agents reference when selling.

NEW FILE: command-center/backend/app/services/catalog_service.py
"""
from __future__ import annotations
import json, logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("cc.catalog")

DEFAULT_CATALOG = [
    {"id": "svc-ai-outreach", "name": "AI Outreach Automation", "type": "service",
     "price": 2500, "currency": "USD", "billing": "monthly",
     "description": "Automated multi-channel outreach: email + LinkedIn + WhatsApp. 500 leads/month.",
     "deliverables": ["outreach setup", "lead sourcing", "sequence optimization", "weekly reporting"]},
    {"id": "svc-content-engine", "name": "AI Content Engine", "type": "service",
     "price": 1500, "currency": "USD", "billing": "monthly",
     "description": "30 pieces/month across IG, TikTok, LinkedIn, YouTube. Strategy + creation + posting.",
     "deliverables": ["content calendar", "30 posts", "performance analytics", "monthly strategy call"]},
    {"id": "svc-full-revenue", "name": "Full Revenue System", "type": "service",
     "price": 5000, "currency": "USD", "billing": "monthly",
     "description": "Complete autonomous revenue: outreach + content + CRM + analytics + optimization.",
     "deliverables": ["everything in outreach + content", "pipeline management", "A/B testing", "attribution"]},
    {"id": "pkg-launch", "name": "Business Launch Sprint", "type": "project",
     "price": 3000, "currency": "USD", "billing": "one_time",
     "description": "2-week sprint: offer creation, landing page, outreach sequence, content batch, first 50 leads.",
     "deliverables": ["offer design", "landing page", "outreach sequence", "20 content pieces", "50 qualified leads"]},
]


class CatalogService:
    def __init__(self):
        self._items: list[dict[str, Any]] = []
        self._persist_path = Path.home() / ".nemoclaw" / "catalog.json"
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        self._load()
        logger.info("CatalogService initialized (%d items)", len(self._items))

    def _load(self) -> None:
        if self._persist_path.exists():
            try:
                self._items = json.loads(self._persist_path.read_text())
            except Exception:
                self._items = list(DEFAULT_CATALOG)
                self._save()
        else:
            self._items = list(DEFAULT_CATALOG)
            self._save()

    def _save(self) -> None:
        try:
            self._persist_path.write_text(json.dumps(self._items, indent=2))
        except Exception as e:
            logger.warning("Failed to save catalog: %s", e)

    def get_catalog(self) -> list[dict[str, Any]]:
        return self._items

    def get_item(self, item_id: str) -> dict[str, Any] | None:
        return next((i for i in self._items if i["id"] == item_id), None)

    def add_item(self, item: dict[str, Any]) -> dict[str, Any]:
        if any(i["id"] == item.get("id") for i in self._items):
            return {"error": "Item already exists"}
        self._items.append(item)
        self._save()
        return {"status": "added", "id": item.get("id")}

    def update_item(self, item_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        for i, item in enumerate(self._items):
            if item["id"] == item_id:
                self._items[i].update(updates)
                self._save()
                return {"status": "updated", "id": item_id}
        return {"error": "Item not found"}

    def get_pricing_for_agent(self) -> str:
        lines = ["Available services/products:\n"]
        for item in self._items:
            lines.append(f"- {item['name']} (${item['price']}/{item['billing']}): {item['description']}")
        return "\n".join(lines)
