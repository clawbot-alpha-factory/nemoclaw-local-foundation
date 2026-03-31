#!/usr/bin/env python3
"""
NemoClaw P-10 Deployment: Payment Bridge (Lemon Squeezy)

Creates: lemonsqueezy_bridge.py (in bridges/)
Patches: bridge_manager.py (register), webhook_service.py (expand handlers)

Run from repo root:
    cd ~/nemoclaw-local-foundation
    python3 scripts/deploy-p10.py
"""

from pathlib import Path
import sys

BACKEND = Path.home() / "nemoclaw-local-foundation" / "command-center" / "backend"

# ═══════════════════════════════════════════════════════════════════
# FILE 1: lemonsqueezy_bridge.py
# ═══════════════════════════════════════════════════════════════════

BRIDGE_CODE = r'''"""
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
'''

# ═══════════════════════════════════════════════════════════════════
# DEPLOY
# ═══════════════════════════════════════════════════════════════════

def deploy():
    errors = []

    # 1. Write bridge
    print("1/3 Writing lemonsqueezy_bridge.py...")
    bridge_path = BACKEND / "app" / "services" / "bridges" / "lemonsqueezy_bridge.py"
    bridge_path.write_text(BRIDGE_CODE.strip() + "\n")
    try:
        compile(bridge_path.read_text(), str(bridge_path), "exec")
        print("  ✅ Compiles")
    except SyntaxError as e:
        errors.append(f"lemonsqueezy_bridge.py: {e}")
        print(f"  ❌ {e}")

    # 2. Patch bridge_manager.py — add config + init
    print("2/3 Patching bridge_manager.py...")
    bm_path = BACKEND / "app" / "services" / "bridge_manager.py"
    bm = bm_path.read_text()

    # Config: add after whatsapp config
    config_old = '''            # P-9: WhatsApp bridge (MENA adaptation)
            "whatsapp": BridgeConfig(
                name="whatsapp",
                enabled=bool(os.environ.get("WHATSAPP_ACCOUNT_SID") or os.environ.get("WHATSAPP_ACCESS_TOKEN")),
                rate_limit_per_minute=30,
                daily_cap=500,
                requires_approval=True,  # Sends to real people
                cost_per_call=0.005,
            ),
        }'''

    config_new = '''            # P-9: WhatsApp bridge (MENA adaptation)
            "whatsapp": BridgeConfig(
                name="whatsapp",
                enabled=bool(os.environ.get("WHATSAPP_ACCOUNT_SID") or os.environ.get("WHATSAPP_ACCESS_TOKEN")),
                rate_limit_per_minute=30,
                daily_cap=500,
                requires_approval=True,  # Sends to real people
                cost_per_call=0.005,
            ),
            # P-10: Lemon Squeezy payment bridge
            "lemonsqueezy": BridgeConfig(
                name="lemonsqueezy",
                enabled=bool(os.environ.get("LEMONSQUEEZY_API_KEY")),
                rate_limit_per_minute=20,
                daily_cap=200,
                requires_approval=True,  # Payment actions
                cost_per_call=0.0,
            ),
        }'''

    if "lemonsqueezy" not in bm:
        if config_old in bm:
            bm = bm.replace(config_old, config_new)
        else:
            errors.append("Bridge config patch target not found")
            print("  ❌ Config target missing")
    else:
        print("  ⚠️ Config already present")

    # Init: add after WhatsApp bridge init
    init_old = '''        # P-9: WhatsApp bridge
        wa_provider = os.environ.get("WHATSAPP_PROVIDER", "twilio")
        wa_has_keys = bool(os.environ.get("WHATSAPP_ACCOUNT_SID") or os.environ.get("WHATSAPP_ACCESS_TOKEN"))
        if wa_has_keys:
            try:
                from app.services.bridges.whatsapp_bridge import WhatsAppBridge
                self._bridges["whatsapp"] = WhatsAppBridge(provider=wa_provider)
                logger.info("WhatsApp bridge loaded (provider=%s)", wa_provider)
            except Exception as e:
                logger.warning("Failed to load WhatsApp bridge: %s", e)

    async def execute('''

    init_new = '''        # P-9: WhatsApp bridge
        wa_provider = os.environ.get("WHATSAPP_PROVIDER", "twilio")
        wa_has_keys = bool(os.environ.get("WHATSAPP_ACCOUNT_SID") or os.environ.get("WHATSAPP_ACCESS_TOKEN"))
        if wa_has_keys:
            try:
                from app.services.bridges.whatsapp_bridge import WhatsAppBridge
                self._bridges["whatsapp"] = WhatsAppBridge(provider=wa_provider)
                logger.info("WhatsApp bridge loaded (provider=%s)", wa_provider)
            except Exception as e:
                logger.warning("Failed to load WhatsApp bridge: %s", e)

        # P-10: Lemon Squeezy payment bridge
        ls_key = os.environ.get("LEMONSQUEEZY_API_KEY", "")
        if ls_key:
            try:
                from app.services.bridges.lemonsqueezy_bridge import LemonSqueezyBridge
                self._bridges["lemonsqueezy"] = LemonSqueezyBridge(api_key=ls_key)
                logger.info("LemonSqueezy bridge loaded (key: %s...)", ls_key[:8])
            except Exception as e:
                logger.warning("Failed to load LemonSqueezy bridge: %s", e)

    async def execute('''

    if "LemonSqueezyBridge" not in bm:
        if init_old in bm:
            bm = bm.replace(init_old, init_new)
        else:
            errors.append("Bridge init patch target not found")
            print("  ❌ Init target missing")
    else:
        print("  ⚠️ Init already present")

    bm_path.write_text(bm)
    try:
        compile(bm_path.read_text(), str(bm_path), "exec")
        print("  ✅ Compiles")
    except SyntaxError as e:
        errors.append(f"bridge_manager.py: {e}")
        print(f"  ❌ {e}")

    # 3. Patch webhook_service.py — expand lemonsqueezy handlers
    print("3/3 Patching webhook_service.py handlers...")
    ws_path = BACKEND / "app" / "services" / "webhook_service.py"
    ws = ws_path.read_text()

    old_ls = '''    "lemonsqueezy": {
        "payment": {"agent": "client_success_lead", "task": "Onboard new client"},
        "cancellation": {"agent": "client_success_lead", "task": "Retain cancelling client"},
    },'''

    new_ls = '''    "lemonsqueezy": {
        "payment": {"agent": "client_success_lead", "task": "Onboard new client"},
        "cancellation": {"agent": "client_success_lead", "task": "Retain cancelling client"},
        # P-10: expanded payment lifecycle events
        "order_created": {"agent": "client_success_lead", "task": "Create client and start onboarding from payment"},
        "subscription_created": {"agent": "client_success_lead", "task": "Link subscription to client record"},
        "subscription_updated": {"agent": "client_success_lead", "task": "Update client subscription status"},
        "subscription_cancelled": {"agent": "client_success_lead", "task": "Flag churn risk — subscription cancelled"},
        "subscription_payment_success": {"agent": "client_success_lead", "task": "Record revenue event from subscription payment"},
        "subscription_payment_failed": {"agent": "client_success_lead", "task": "Alert — subscription payment failed, flag at-risk"},
    },'''

    if "order_created" not in ws:
        if old_ls in ws:
            ws = ws.replace(old_ls, new_ls)
        else:
            errors.append("Webhook handler patch target not found")
            print("  ❌ Handler target missing")
    else:
        print("  ⚠️ Handlers already present")

    ws_path.write_text(ws)
    try:
        compile(ws_path.read_text(), str(ws_path), "exec")
        print("  ✅ Compiles")
    except SyntaxError as e:
        errors.append(f"webhook_service.py: {e}")
        print(f"  ❌ {e}")

    # Summary
    print()
    if errors:
        print(f"⛔ {len(errors)} ERRORS:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("✅ P-10 deployed successfully")
        print()
        print("Restart backend, then validate:")
        print()
        print('  TOKEN=$(cat ~/.nemoclaw/cc-token)')
        print()
        print('  # Bridge list (should include lemonsqueezy)')
        print('  curl -s -H "Authorization: Bearer $TOKEN" \\')
        print('    http://127.0.0.1:8100/api/bridges/status | python3 -c "import json,sys; d=json.load(sys.stdin); print(\'Bridges:\', list(d.get(\'bridges\',{}).keys()))"')
        print()
        print('  # LemonSqueezy status (disabled — no key)')
        print('  curl -s -H "Authorization: Bearer $TOKEN" \\')
        print('    http://127.0.0.1:8100/api/bridges/lemonsqueezy/status | python3 -m json.tool')
        print()
        print('  # Webhook: simulate order_created')
        print('  curl -s -X POST -H "Authorization: Bearer $TOKEN" \\')
        print('    -H "Content-Type: application/json" \\')
        print("    -d '{\"event_type\":\"order_created\",\"data\":{\"customer_email\":\"test@example.com\",\"customer_name\":\"Test Client\",\"order_id\":\"ord_123\",\"total\":99.00}}' \\")
        print('    http://127.0.0.1:8100/api/webhooks/lemonsqueezy | python3 -m json.tool')
        print()
        print('  # Webhook: simulate subscription_cancelled')
        print('  curl -s -X POST -H "Authorization: Bearer $TOKEN" \\')
        print('    -H "Content-Type: application/json" \\')
        print("    -d '{\"event_type\":\"subscription_cancelled\",\"data\":{\"subscription_id\":\"sub_456\",\"customer_email\":\"test@example.com\"}}' \\")
        print('    http://127.0.0.1:8100/api/webhooks/lemonsqueezy | python3 -m json.tool')
        print()
        print('  # Webhook history')
        print('  curl -s -H "Authorization: Bearer $TOKEN" \\')
        print('    "http://127.0.0.1:8100/api/webhooks/history?source=lemonsqueezy" | python3 -m json.tool')
        print()
        print('  cd ~/nemoclaw-local-foundation && bash scripts/full_regression.sh')
        print()
        print('  git add -A && git status')
        print('  git commit -m "feat(engine): P-10 payment bridge — Lemon Squeezy checkout, subscriptions, webhook lifecycle"')
        print('  git push origin main')


if __name__ == "__main__":
    deploy()
