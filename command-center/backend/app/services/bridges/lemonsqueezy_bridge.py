"""
NemoClaw Execution Engine — LemonSqueezyBridge (P-10)

Payment bridge: products, checkouts, subscriptions, orders, customers.
Wraps the existing scripts/lemonsqueezy_bridge.py client as an async bridge.

Integrates with BridgeManager for rate limiting, cost tracking, approval gates.

Payment lifecycle:
  create_checkout → customer pays → webhook (order_created) → create client → onboard

NEW FILE: command-center/backend/app/services/bridges/lemonsqueezy_bridge.py
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore

logger = logging.getLogger("cc.bridge.lemonsqueezy")

BASE_URL = "https://api.lemonsqueezy.com/v1"


class LemonSqueezyBridge:
    """
    Lemon Squeezy payment bridge.

    Actions: health, list_products, list_variants, create_checkout,
    list_orders, get_order, list_subscriptions, cancel_subscription, list_customers.
    """

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or os.environ.get("LEMONSQUEEZY_API_KEY", "")
        self._client: Any = None
        if httpx and self.api_key:
            self._client = httpx.AsyncClient(
                base_url=BASE_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/vnd.api+json",
                    "Accept": "application/vnd.api+json",
                },
                timeout=30.0,
            )
        logger.info("LemonSqueezyBridge initialized")

    async def _get(self, path: str, params: dict | None = None) -> dict[str, Any]:
        if not self._client:
            return {"error": "Lemon Squeezy API key not configured or httpx unavailable"}
        try:
            resp = await self._client.get(path, params=params)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            return {"error": f"HTTP {e.response.status_code}", "detail": e.response.text[:300]}
        except httpx.RequestError as e:
            return {"error": str(e)}

    async def _post(self, path: str, data: dict | None = None) -> dict[str, Any]:
        if not self._client:
            return {"error": "Lemon Squeezy API key not configured or httpx unavailable"}
        try:
            resp = await self._client.post(path, json=data or {})
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            return {"error": f"HTTP {e.response.status_code}", "detail": e.response.text[:300]}
        except httpx.RequestError as e:
            return {"error": str(e)}

    async def _patch(self, path: str, data: dict | None = None) -> dict[str, Any]:
        if not self._client:
            return {"error": "Lemon Squeezy API key not configured or httpx unavailable"}
        try:
            resp = await self._client.patch(path, json=data or {})
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            return {"error": f"HTTP {e.response.status_code}", "detail": e.response.text[:300]}
        except httpx.RequestError as e:
            return {"error": str(e)}

    # ── Actions ─────────────────────────────────────────────────────

    async def health(self) -> dict[str, Any]:
        """Check API connectivity."""
        result = await self._get("/users/me")
        return {"connected": "error" not in result, "result": result}

    async def list_products(self, store_id: str = "") -> dict[str, Any]:
        """List all products, optionally filtered by store."""
        params = {"filter[store_id]": store_id} if store_id else None
        return await self._get("/products", params)

    async def list_variants(self, product_id: str = "") -> dict[str, Any]:
        """List pricing variants for a product."""
        params = {"filter[product_id]": product_id} if product_id else None
        return await self._get("/variants", params)

    async def create_checkout(
        self,
        store_id: str,
        variant_id: str,
        customer_email: str = "",
        customer_name: str = "",
        custom_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a checkout URL for a prospect.

        Returns: {"data": {"attributes": {"url": "https://checkout..."}}}
        """
        checkout_data: dict[str, Any] = custom_data or {}
        if customer_email:
            checkout_data["email"] = customer_email
        if customer_name:
            checkout_data["name"] = customer_name

        body = {
            "data": {
                "type": "checkouts",
                "attributes": {"checkout_data": checkout_data},
                "relationships": {
                    "store": {"data": {"type": "stores", "id": str(store_id)}},
                    "variant": {"data": {"type": "variants", "id": str(variant_id)}},
                },
            }
        }
        result = await self._post("/checkouts", body)
        # Extract URL for convenience
        url = ""
        try:
            url = result.get("data", {}).get("attributes", {}).get("url", "")
        except (AttributeError, TypeError):
            pass
        return {"checkout_url": url, "result": result}

    async def list_orders(self, store_id: str = "") -> dict[str, Any]:
        """List completed orders."""
        params = {"filter[store_id]": store_id} if store_id else None
        return await self._get("/orders", params)

    async def get_order(self, order_id: str) -> dict[str, Any]:
        """Get a specific order."""
        return await self._get(f"/orders/{order_id}")

    async def list_subscriptions(self, store_id: str = "") -> dict[str, Any]:
        """List active subscriptions."""
        params = {"filter[store_id]": store_id} if store_id else None
        return await self._get("/subscriptions", params)

    async def cancel_subscription(self, subscription_id: str) -> dict[str, Any]:
        """Cancel a subscription. HIGH RISK — requires approval."""
        body = {
            "data": {
                "type": "subscriptions",
                "id": str(subscription_id),
                "attributes": {"cancelled": True},
            }
        }
        return await self._patch(f"/subscriptions/{subscription_id}", body)

    async def list_customers(self, store_id: str = "") -> dict[str, Any]:
        """List customers."""
        params = {"filter[store_id]": store_id} if store_id else None
        return await self._get("/customers", params)

    # ── Bridge Interface ────────────────────────────────────────────

    async def execute(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        """Unified bridge execution interface for BridgeManager."""
        actions = {
            "health": lambda: self.health(),
            "list_products": lambda: self.list_products(params.get("store_id", "")),
            "list_variants": lambda: self.list_variants(params.get("product_id", "")),
            "create_checkout": lambda: self.create_checkout(
                store_id=params.get("store_id", ""),
                variant_id=params.get("variant_id", ""),
                customer_email=params.get("customer_email", ""),
                customer_name=params.get("customer_name", ""),
                custom_data=params.get("custom_data"),
            ),
            "list_orders": lambda: self.list_orders(params.get("store_id", "")),
            "get_order": lambda: self.get_order(params.get("order_id", "")),
            "list_subscriptions": lambda: self.list_subscriptions(params.get("store_id", "")),
            "cancel_subscription": lambda: self.cancel_subscription(params.get("subscription_id", "")),
            "list_customers": lambda: self.list_customers(params.get("store_id", "")),
        }

        handler = actions.get(action)
        if not handler:
            return {"error": f"Unknown action '{action}'. Available: {list(actions.keys())}"}

        return await handler()
