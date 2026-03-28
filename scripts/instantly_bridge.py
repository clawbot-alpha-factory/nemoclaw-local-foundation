#!/usr/bin/env python3
"""
NemoClaw ↔ Instantly.ai Bridge
Cold email campaigns, lead management, analytics.

    python3 scripts/instantly_bridge.py --test
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
ACTION_LOG = LOG_DIR / "instantly-actions.jsonl"
BASE_URL = "https://api.instantly.ai/api/v1"


class InstantlyClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("INSTANTLY_API_KEY", "")
        self.timeout = 30
        LOG_DIR.mkdir(parents=True, exist_ok=True)

    def _log(self, action, params, success, error=None):
        entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "service": "instantly", "action": action, "params": params, "success": success}
        if error: entry["error"] = str(error)[:200]
        try:
            with open(ACTION_LOG, "a") as f: f.write(json.dumps(entry) + "\n")
        except Exception: pass

    def _get(self, path, params=None):
        try:
            p = params or {}; p["api_key"] = self.api_key
            r = requests.get(f"{BASE_URL}{path}", params=p, timeout=self.timeout)
            if r.status_code >= 400: return (False, f"HTTP {r.status_code}: {r.text[:300]}")
            return (True, r.json())
        except requests.ConnectionError: return (False, "Instantly API not reachable")
        except requests.Timeout: return (False, "Timed out")
        except Exception as e: return (False, str(e))

    def _post(self, path, data=None):
        try:
            d = data or {}; d["api_key"] = self.api_key
            r = requests.post(f"{BASE_URL}{path}", json=d, headers={"Content-Type": "application/json"}, timeout=self.timeout)
            if r.status_code >= 400: return (False, f"HTTP {r.status_code}: {r.text[:300]}")
            return (True, r.json())
        except requests.ConnectionError: return (False, "Instantly API not reachable")
        except requests.Timeout: return (False, "Timed out")
        except Exception as e: return (False, str(e))

    def health(self):
        ok, r = self._get("/campaign/list", {"limit": 1}); self._log("health", {}, ok, error=r if not ok else None); return (ok, r)

    def list_campaigns(self, limit=10, skip=0):
        ok, r = self._get("/campaign/list", {"limit": limit, "skip": skip}); self._log("list_campaigns", {}, ok); return (ok, r)

    def get_campaign(self, campaign_id):
        ok, r = self._get("/campaign/get", {"campaign_id": campaign_id}); self._log("get_campaign", {"id": campaign_id}, ok); return (ok, r)

    def get_campaign_summary(self, campaign_id):
        ok, r = self._get("/analytics/campaign/summary", {"campaign_id": campaign_id}); self._log("campaign_summary", {"id": campaign_id}, ok); return (ok, r)

    def add_leads(self, campaign_id, leads):
        """Add leads to campaign. leads = [{email, first_name, last_name, company_name, ...}]."""
        ok, r = self._post("/lead/add", {"campaign_id": campaign_id, "leads": leads})
        self._log("add_leads", {"campaign": campaign_id, "count": len(leads)}, ok); return (ok, r)

    def get_lead_status(self, email, campaign_id=None):
        params = {"email": email}
        if campaign_id: params["campaign_id"] = campaign_id
        ok, r = self._get("/lead/get", params); self._log("get_lead", {"email": email}, ok); return (ok, r)

    def list_emails(self, campaign_id):
        ok, r = self._get("/campaign/emails", {"campaign_id": campaign_id}); self._log("list_emails", {"id": campaign_id}, ok); return (ok, r)

    def get_analytics(self, campaign_id, start_date=None, end_date=None):
        params = {"campaign_id": campaign_id}
        if start_date: params["start_date"] = start_date
        if end_date: params["end_date"] = end_date
        ok, r = self._get("/analytics/campaign/summary", params); self._log("analytics", {"id": campaign_id}, ok); return (ok, r)

    def list_accounts(self):
        ok, r = self._get("/account/list"); self._log("list_accounts", {}, ok); return (ok, r)

    def warmup_status(self, email):
        ok, r = self._get("/account/warmup/status", {"email": email}); self._log("warmup_status", {"email": email}, ok); return (ok, r)


def _run_tests():
    from unittest.mock import patch, MagicMock
    passed = total = 0
    def test(name, fn):
        nonlocal passed, total; total += 1
        try: fn(); passed += 1; print(f"  ✅ {name}")
        except Exception as e: print(f"  ❌ {name}: {e}")

    print("=" * 60); print("  Instantly.ai Bridge Tests"); print("=" * 60)

    def mr(s=200, d=None):
        r = MagicMock(); r.status_code = s; r.json.return_value = d or {}; r.text = json.dumps(d) if d else ""; return r

    def t1(): c = InstantlyClient(api_key="k"); assert c.api_key == "k"
    test("Constructor", t1)

    def t2():
        c = InstantlyClient(api_key="k")
        with patch("requests.get", return_value=mr(200, [])): ok, _ = c.health(); assert ok
    test("Health", t2)

    def t3():
        c = InstantlyClient(api_key="k")
        with patch("requests.get", return_value=mr(200, [{"id": "c1"}])): ok, _ = c.list_campaigns(); assert ok
    test("List campaigns", t3)

    def t4():
        c = InstantlyClient(api_key="k")
        with patch("requests.get", return_value=mr(200, {"id": "c1"})): ok, _ = c.get_campaign("c1"); assert ok
    test("Get campaign", t4)

    def t5():
        c = InstantlyClient(api_key="k")
        with patch("requests.get", return_value=mr(200, {"sent": 100, "opened": 40})): ok, _ = c.get_campaign_summary("c1"); assert ok
    test("Campaign summary", t5)

    def t6():
        c = InstantlyClient(api_key="k")
        leads = [{"email": "j@t.com", "first_name": "John"}]
        with patch("requests.post", return_value=mr(200, {"status": "success"})) as mp:
            ok, _ = c.add_leads("c1", leads); body = mp.call_args[1]["json"]; assert body["leads"] == leads
    test("Add leads", t6)

    def t7():
        c = InstantlyClient(api_key="k")
        with patch("requests.get", return_value=mr(200, {"email": "j@t.com", "status": "sent"})): ok, _ = c.get_lead_status("j@t.com"); assert ok
    test("Get lead status", t7)

    def t8():
        c = InstantlyClient(api_key="k")
        with patch("requests.get", return_value=mr(200, [])): ok, _ = c.list_accounts(); assert ok
    test("List accounts", t8)

    def t9():
        c = InstantlyClient(api_key="k")
        with patch("requests.get", return_value=mr(200, {"status": "warming"})): ok, _ = c.warmup_status("test@domain.com"); assert ok
    test("Warmup status", t9)

    def t10():
        c = InstantlyClient(api_key="k")
        with patch("requests.get", return_value=mr(401, {"error": "bad key"})): ok, _ = c.health(); assert not ok
    test("HTTP error", t10)

    def t11():
        c = InstantlyClient(api_key="k")
        with patch("requests.get", side_effect=requests.Timeout): ok, _ = c.health(); assert not ok
    test("Timeout", t11)

    def t12():
        c = InstantlyClient(api_key="k")
        with patch("requests.get", return_value=mr(200, {})): c.health()
        assert ACTION_LOG.exists()
    test("Action log", t12)

    print(f"\n  {'=' * 50}"); print(f"  Instantly Bridge: {'PASS' if passed == total else 'FAIL'}"); print(f"  Passed: {passed}/{total}"); print(f"  {'=' * 50}")
    return passed == total

if __name__ == "__main__":
    if "--test" in sys.argv: sys.exit(0 if _run_tests() else 1)
    elif "--health" in sys.argv:
        c = InstantlyClient(); ok, r = c.health(); print(f"{'✅' if ok else '❌'} Instantly: {r if not ok else 'connected'}")
    else: print("Usage: python3 scripts/instantly_bridge.py --test|--health")
