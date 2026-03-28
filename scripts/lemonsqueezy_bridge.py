#!/usr/bin/env python3
"""
NemoClaw ↔ Lemon Squeezy Bridge
Products, checkouts, subscriptions, orders.

    python3 scripts/lemonsqueezy_bridge.py --test
"""

import json, os, sys, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
try:
    import requests
except ImportError:
    sys.exit("ERROR: requests required")

LOG_DIR = Path.home() / ".nemoclaw" / "integrations"
ACTION_LOG = LOG_DIR / "lemonsqueezy-actions.jsonl"
BASE_URL = "https://api.lemonsqueezy.com/v1"


class LemonSqueezyClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("LEMONSQUEEZY_API_KEY", "")
        self.timeout = 30
        LOG_DIR.mkdir(parents=True, exist_ok=True)

    def _headers(self):
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/vnd.api+json", "Accept": "application/vnd.api+json"}

    def _log(self, action, params, success, error=None):
        entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "service": "lemonsqueezy", "action": action, "params": params, "success": success}
        if error: entry["error"] = str(error)[:200]
        try:
            with open(ACTION_LOG, "a") as f: f.write(json.dumps(entry) + "\n")
        except Exception: pass

    def _get(self, path, params=None):
        try:
            r = requests.get(f"{BASE_URL}{path}", headers=self._headers(), params=params, timeout=self.timeout)
            if r.status_code >= 400: return (False, f"HTTP {r.status_code}: {r.text[:300]}")
            return (True, r.json())
        except requests.ConnectionError: return (False, "API not reachable")
        except requests.Timeout: return (False, "Timed out")
        except Exception as e: return (False, str(e))

    def _post(self, path, data=None):
        try:
            r = requests.post(f"{BASE_URL}{path}", headers=self._headers(), json=data or {}, timeout=self.timeout)
            if r.status_code >= 400: return (False, f"HTTP {r.status_code}: {r.text[:300]}")
            return (True, r.json())
        except requests.ConnectionError: return (False, "API not reachable")
        except requests.Timeout: return (False, "Timed out")
        except Exception as e: return (False, str(e))

    def _patch(self, path, data=None):
        try:
            r = requests.patch(f"{BASE_URL}{path}", headers=self._headers(), json=data or {}, timeout=self.timeout)
            if r.status_code >= 400: return (False, f"HTTP {r.status_code}: {r.text[:300]}")
            return (True, r.json())
        except Exception as e: return (False, str(e))

    def health(self):
        ok, result = self._get("/users/me")
        self._log("health", {}, ok, error=result if not ok else None)
        return (ok, result)

    def list_stores(self):
        ok, r = self._get("/stores"); self._log("list_stores", {}, ok); return (ok, r)

    def list_products(self, store_id=None):
        params = {"filter[store_id]": store_id} if store_id else None
        ok, r = self._get("/products", params); self._log("list_products", {}, ok); return (ok, r)

    def get_product(self, product_id):
        ok, r = self._get(f"/products/{product_id}"); self._log("get_product", {"id": product_id}, ok); return (ok, r)

    def list_variants(self, product_id=None):
        params = {"filter[product_id]": product_id} if product_id else None
        ok, r = self._get("/variants", params); self._log("list_variants", {}, ok); return (ok, r)

    def create_checkout(self, store_id, variant_id, custom_data=None):
        """Create a checkout URL. Returns (ok, {data: {attributes: {url}}})."""
        body = {"data": {"type": "checkouts", "attributes": {"checkout_data": custom_data or {}},
                "relationships": {"store": {"data": {"type": "stores", "id": str(store_id)}},
                                  "variant": {"data": {"type": "variants", "id": str(variant_id)}}}}}
        ok, r = self._post("/checkouts", body); self._log("create_checkout", {"variant": variant_id}, ok); return (ok, r)

    def list_orders(self, store_id=None):
        params = {"filter[store_id]": store_id} if store_id else None
        ok, r = self._get("/orders", params); self._log("list_orders", {}, ok); return (ok, r)

    def get_order(self, order_id):
        ok, r = self._get(f"/orders/{order_id}"); self._log("get_order", {"id": order_id}, ok); return (ok, r)

    def list_subscriptions(self, store_id=None):
        params = {"filter[store_id]": store_id} if store_id else None
        ok, r = self._get("/subscriptions", params); self._log("list_subscriptions", {}, ok); return (ok, r)

    def cancel_subscription(self, subscription_id):
        ok, r = self._patch(f"/subscriptions/{subscription_id}", {"data": {"type": "subscriptions", "id": str(subscription_id), "attributes": {"cancelled": True}}})
        self._log("cancel_subscription", {"id": subscription_id}, ok); return (ok, r)

    def list_customers(self, store_id=None):
        params = {"filter[store_id]": store_id} if store_id else None
        ok, r = self._get("/customers", params); self._log("list_customers", {}, ok); return (ok, r)


def _run_tests():
    from unittest.mock import patch, MagicMock
    passed = total = 0
    def test(name, fn):
        nonlocal passed, total; total += 1
        try: fn(); passed += 1; print(f"  ✅ {name}")
        except Exception as e: print(f"  ❌ {name}: {e}")

    print("=" * 60); print("  Lemon Squeezy Bridge Tests"); print("=" * 60)

    def mr(s=200, d=None):
        r = MagicMock(); r.status_code = s; r.json.return_value = d or {}; r.text = json.dumps(d) if d else ""; return r

    def t1(): c = LemonSqueezyClient(api_key="k"); assert c.api_key == "k"
    test("Constructor", t1)

    def t2():
        c = LemonSqueezyClient(api_key="k")
        with patch("requests.get", return_value=mr(200, {"data": {"id": "1"}})): ok, _ = c.health(); assert ok
    test("Health", t2)

    def t3():
        c = LemonSqueezyClient(api_key="k")
        with patch("requests.get", return_value=mr(200, {"data": []})): ok, _ = c.list_stores(); assert ok
    test("List stores", t3)

    def t4():
        c = LemonSqueezyClient(api_key="k")
        with patch("requests.get", return_value=mr(200, {"data": [{"id": "p1"}]})): ok, _ = c.list_products(); assert ok
    test("List products", t4)

    def t5():
        c = LemonSqueezyClient(api_key="k")
        with patch("requests.get", return_value=mr(200, {"data": {"id": "p1"}})): ok, _ = c.get_product("p1"); assert ok
    test("Get product", t5)

    def t6():
        c = LemonSqueezyClient(api_key="k")
        with patch("requests.get", return_value=mr(200, {"data": []})): ok, _ = c.list_variants("p1"); assert ok
    test("List variants", t6)

    def t7():
        c = LemonSqueezyClient(api_key="k")
        with patch("requests.post", return_value=mr(201, {"data": {"attributes": {"url": "https://checkout.lemonsqueezy.com/x"}}})) as mp:
            ok, r = c.create_checkout("s1", "v1", {"email": "j@t.com"})
            assert ok; body = mp.call_args[1]["json"]; assert body["data"]["type"] == "checkouts"
    test("Create checkout", t7)

    def t8():
        c = LemonSqueezyClient(api_key="k")
        with patch("requests.get", return_value=mr(200, {"data": []})): ok, _ = c.list_orders(); assert ok
    test("List orders", t8)

    def t9():
        c = LemonSqueezyClient(api_key="k")
        with patch("requests.get", return_value=mr(200, {"data": {"id": "o1"}})): ok, _ = c.get_order("o1"); assert ok
    test("Get order", t9)

    def t10():
        c = LemonSqueezyClient(api_key="k")
        with patch("requests.get", return_value=mr(200, {"data": []})): ok, _ = c.list_subscriptions(); assert ok
    test("List subscriptions", t10)

    def t11():
        c = LemonSqueezyClient(api_key="k")
        with patch("requests.patch", return_value=mr(200, {"data": {"attributes": {"cancelled": True}}})): ok, _ = c.cancel_subscription("sub1"); assert ok
    test("Cancel subscription", t11)

    def t12():
        c = LemonSqueezyClient(api_key="k")
        with patch("requests.get", return_value=mr(200, {"data": []})): ok, _ = c.list_customers(); assert ok
    test("List customers", t12)

    def t13():
        c = LemonSqueezyClient(api_key="k")
        with patch("requests.get", return_value=mr(401, {"errors": [{"detail": "unauthorized"}]})): ok, r = c.health(); assert not ok
    test("HTTP error", t13)

    def t14():
        c = LemonSqueezyClient(api_key="k")
        with patch("requests.get", side_effect=requests.Timeout): ok, _ = c.health(); assert not ok
    test("Timeout", t14)

    def t15():
        c = LemonSqueezyClient(api_key="k")
        with patch("requests.get", return_value=mr(200, {})): c.health()
        assert ACTION_LOG.exists()
    test("Action log", t15)

    print(f"\n  {'=' * 50}"); print(f"  Lemon Squeezy Bridge: {'PASS' if passed == total else 'FAIL'}"); print(f"  Passed: {passed}/{total}"); print(f"  {'=' * 50}")
    return passed == total

if __name__ == "__main__":
    if "--test" in sys.argv: sys.exit(0 if _run_tests() else 1)
    elif "--health" in sys.argv:
        c = LemonSqueezyClient(); ok, r = c.health(); print(f"{'✅' if ok else '❌'} LemonSqueezy: {r if not ok else 'connected'}")
    else: print("Usage: python3 scripts/lemonsqueezy_bridge.py --test|--health")
