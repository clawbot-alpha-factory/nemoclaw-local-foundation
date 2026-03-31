"""
NemoClaw Execution Engine — Instantly Bridge (E-8)

Real Instantly API bridge for outreach campaigns.
Actions: list_campaigns, create_campaign, add_leads, get_campaign, health

API: v2 (https://api.instantly.ai/api/v2/)

NEW FILE: command-center/backend/app/services/bridges/instantly_bridge.py
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

logger = logging.getLogger("cc.bridge.instantly")


class InstantlyBridge:
    """Real Instantly API bridge for outreach automation."""

    BASE_URL = "https://api.instantly.ai/api/v2"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        logger.info("InstantlyBridge initialized")

    async def execute(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        """Execute an Instantly action."""
        actions = {
            "list_campaigns": self._list_campaigns,
            "get_campaign": self._get_campaign,
            "create_campaign": self._create_campaign,
            "add_leads": self._add_leads,
            "list_leads": self._list_leads,
            "get_analytics": self._get_analytics,
            "health": self._health_check,
        }

        handler = actions.get(action)
        if not handler:
            raise ValueError(f"Unknown Instantly action: {action}. Available: {list(actions.keys())}")

        return await handler(params)

    async def _list_campaigns(self, params: dict[str, Any]) -> dict[str, Any]:
        """List all campaigns."""
        try:
            limit = params.get("limit", 10)
            resp = await self._client.get(f"{self.BASE_URL}/campaigns", params={"limit": limit})
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Instantly list error ({e.response.status_code}): {e.response.text[:200]}")
        except httpx.RequestError as e:
            raise RuntimeError(f"Instantly connection error: {e}")

    async def _get_campaign(self, params: dict[str, Any]) -> dict[str, Any]:
        """Get campaign details."""
        campaign_id = params.get("campaign_id", "")
        if not campaign_id:
            raise ValueError("Missing campaign_id")
        try:
            resp = await self._client.get(f"{self.BASE_URL}/campaigns/{campaign_id}")
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Instantly get error ({e.response.status_code}): {e.response.text[:200]}")

    async def _create_campaign(self, params: dict[str, Any]) -> dict[str, Any]:
        """Create a new campaign."""
        required = ["name"]
        for field in required:
            if field not in params:
                raise ValueError(f"Missing required field: {field}")

        payload = {
            "name": params["name"],
        }
        if params.get("schedule"):
            payload["schedule"] = params["schedule"]

        try:
            resp = await self._client.post(f"{self.BASE_URL}/campaigns", json=payload)
            resp.raise_for_status()
            data = resp.json()
            logger.info("Campaign created: %s", params["name"])
            return data
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Instantly create error ({e.response.status_code}): {e.response.text[:200]}")

    async def _add_leads(self, params: dict[str, Any]) -> dict[str, Any]:
        """Add leads to a campaign."""
        campaign_id = params.get("campaign_id", "")
        leads = params.get("leads", [])
        if not campaign_id:
            raise ValueError("Missing campaign_id")
        if not leads:
            raise ValueError("Missing leads list")

        try:
            resp = await self._client.post(
                f"{self.BASE_URL}/leads",
                json={"campaign_id": campaign_id, "leads": leads},
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Instantly add leads error ({e.response.status_code}): {e.response.text[:200]}")

    async def _list_leads(self, params: dict[str, Any]) -> dict[str, Any]:
        """List leads in a campaign."""
        campaign_id = params.get("campaign_id", "")
        if not campaign_id:
            raise ValueError("Missing campaign_id")
        try:
            resp = await self._client.get(
                f"{self.BASE_URL}/leads",
                params={"campaign_id": campaign_id, "limit": params.get("limit", 20)},
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Instantly list leads error ({e.response.status_code}): {e.response.text[:200]}")

    async def _get_analytics(self, params: dict[str, Any]) -> dict[str, Any]:
        """Get campaign analytics."""
        campaign_id = params.get("campaign_id", "")
        if not campaign_id:
            raise ValueError("Missing campaign_id")
        try:
            resp = await self._client.get(f"{self.BASE_URL}/campaigns/{campaign_id}/analytics")
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Instantly analytics error ({e.response.status_code}): {e.response.text[:200]}")

    async def _health_check(self, params: dict[str, Any]) -> dict[str, Any]:
        """Check if Instantly API is reachable."""
        try:
            resp = await self._client.get(f"{self.BASE_URL}/campaigns", params={"limit": 1})
            return {"healthy": resp.status_code == 200, "status_code": resp.status_code}
        except Exception as e:
            return {"healthy": False, "error": str(e)}
