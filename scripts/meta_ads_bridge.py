#!/usr/bin/env python3
"""
NemoClaw ↔ Meta Ads Bridge (Facebook + Instagram)
Campaign management, audience targeting, creative upload, reporting.

    python3 scripts/meta_ads_bridge.py --test
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
ACTION_LOG = LOG_DIR / "meta-ads-actions.jsonl"
BASE_URL = "https://graph.facebook.com/v19.0"


class MetaAdsClient:
    def __init__(self, access_token: Optional[str] = None, app_id: Optional[str] = None,
                 app_secret: Optional[str] = None, ad_account_id: Optional[str] = None):
        self.access_token = access_token or os.environ.get("META_ACCESS_TOKEN", "")
        self.app_id = app_id or os.environ.get("META_APP_ID", "")
        self.app_secret = app_secret or os.environ.get("META_APP_SECRET", "")
        self.ad_account_id = ad_account_id or os.environ.get("META_AD_ACCOUNT_ID", "")
        if self.ad_account_id and not self.ad_account_id.startswith("act_"):
            self.ad_account_id = f"act_{self.ad_account_id}"
        self.timeout = 30
        LOG_DIR.mkdir(parents=True, exist_ok=True)

    def _log(self, action, params, success, error=None):
        entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "service": "meta_ads", "action": action, "params": params, "success": success}
        if error: entry["error"] = str(error)[:200]
        try:
            with open(ACTION_LOG, "a") as f: f.write(json.dumps(entry) + "\n")
        except Exception: pass

    def _get(self, path, params=None):
        try:
            p = params or {}; p["access_token"] = self.access_token
            r = requests.get(f"{BASE_URL}{path}", params=p, timeout=self.timeout)
            if r.status_code >= 400: return (False, f"HTTP {r.status_code}: {r.text[:300]}")
            return (True, r.json())
        except requests.ConnectionError: return (False, "Meta API not reachable")
        except requests.Timeout: return (False, "Timed out")
        except Exception as e: return (False, str(e))

    def _post(self, path, data=None):
        try:
            d = data or {}; d["access_token"] = self.access_token
            r = requests.post(f"{BASE_URL}{path}", json=d, timeout=self.timeout)
            if r.status_code >= 400: return (False, f"HTTP {r.status_code}: {r.text[:300]}")
            return (True, r.json())
        except requests.ConnectionError: return (False, "Meta API not reachable")
        except requests.Timeout: return (False, "Timed out")
        except Exception as e: return (False, str(e))

    def health(self):
        ok, r = self._get("/me", {"fields": "id,name"})
        self._log("health", {}, ok, error=r if not ok else None); return (ok, r)

    def list_campaigns(self, status=None):
        params = {"fields": "id,name,status,objective,daily_budget,lifetime_budget,created_time"}
        if status: params["effective_status"] = json.dumps([status])
        ok, r = self._get(f"/{self.ad_account_id}/campaigns", params)
        self._log("list_campaigns", {}, ok); return (ok, r)

    def create_campaign(self, name, objective="OUTCOME_LEADS", status="PAUSED", daily_budget=None, special_ad_categories=None):
        data = {"name": name, "objective": objective, "status": status, "special_ad_categories": special_ad_categories or []}
        if daily_budget: data["daily_budget"] = int(daily_budget * 100)  # cents
        ok, r = self._post(f"/{self.ad_account_id}/campaigns", data)
        self._log("create_campaign", {"name": name, "objective": objective}, ok); return (ok, r)

    def get_campaign(self, campaign_id):
        ok, r = self._get(f"/{campaign_id}", {"fields": "id,name,status,objective,insights{impressions,reach,clicks,spend,actions}"})
        self._log("get_campaign", {"id": campaign_id}, ok); return (ok, r)

    def get_campaign_insights(self, campaign_id, date_preset="last_30d"):
        ok, r = self._get(f"/{campaign_id}/insights", {"fields": "impressions,reach,clicks,spend,cpc,cpm,ctr,actions,cost_per_action_type", "date_preset": date_preset})
        self._log("campaign_insights", {"id": campaign_id}, ok); return (ok, r)

    def list_ad_sets(self, campaign_id):
        ok, r = self._get(f"/{campaign_id}/adsets", {"fields": "id,name,status,targeting,daily_budget,bid_amount"})
        self._log("list_ad_sets", {"campaign": campaign_id}, ok); return (ok, r)

    def create_ad_set(self, campaign_id, name, targeting, daily_budget, billing_event="IMPRESSIONS", optimization_goal="LEAD_GENERATION", status="PAUSED"):
        data = {"campaign_id": campaign_id, "name": name, "targeting": targeting, "daily_budget": int(daily_budget * 100), "billing_event": billing_event, "optimization_goal": optimization_goal, "status": status}
        ok, r = self._post(f"/{self.ad_account_id}/adsets", data)
        self._log("create_ad_set", {"name": name}, ok); return (ok, r)

    def list_ads(self, ad_set_id=None, campaign_id=None):
        parent_id = ad_set_id or campaign_id or self.ad_account_id
        ok, r = self._get(f"/{parent_id}/ads", {"fields": "id,name,status,creative{title,body}"})
        self._log("list_ads", {}, ok); return (ok, r)

    def list_custom_audiences(self):
        ok, r = self._get(f"/{self.ad_account_id}/customaudiences", {"fields": "id,name,approximate_count,data_source"})
        self._log("list_audiences", {}, ok); return (ok, r)

    def get_ad_account(self):
        ok, r = self._get(f"/{self.ad_account_id}", {"fields": "id,name,currency,timezone_name,amount_spent,balance"})
        self._log("get_account", {}, ok); return (ok, r)


def _run_tests():
    from unittest.mock import patch, MagicMock
    passed = total = 0
    def test(name, fn):
        nonlocal passed, total; total += 1
        try: fn(); passed += 1; print(f"  ✅ {name}")
        except Exception as e: print(f"  ❌ {name}: {e}")

    print("=" * 60); print("  Meta Ads Bridge Tests"); print("=" * 60)

    def mr(s=200, d=None):
        r = MagicMock(); r.status_code = s; r.json.return_value = d or {}; r.text = json.dumps(d) if d else ""; return r

    def t1(): c = MetaAdsClient(access_token="tok", ad_account_id="123"); assert c.ad_account_id == "act_123"
    test("Constructor adds act_ prefix", t1)

    def t2(): c = MetaAdsClient(ad_account_id="act_456"); assert c.ad_account_id == "act_456"
    test("Constructor keeps act_ prefix", t2)

    def t3():
        c = MetaAdsClient(access_token="tok")
        with patch("requests.get", return_value=mr(200, {"id": "123", "name": "Test"})): ok, _ = c.health(); assert ok
    test("Health", t3)

    def t4():
        c = MetaAdsClient(access_token="tok", ad_account_id="act_1")
        with patch("requests.get", return_value=mr(200, {"data": [{"id": "c1"}]})): ok, _ = c.list_campaigns(); assert ok
    test("List campaigns", t4)

    def t5():
        c = MetaAdsClient(access_token="tok", ad_account_id="act_1")
        with patch("requests.post", return_value=mr(200, {"id": "c_new"})) as mp:
            ok, r = c.create_campaign("Test Campaign", daily_budget=50.0)
            body = mp.call_args[1]["json"]; assert body["daily_budget"] == 5000  # cents
    test("Create campaign (budget in cents)", t5)

    def t6():
        c = MetaAdsClient(access_token="tok")
        with patch("requests.get", return_value=mr(200, {"id": "c1", "name": "Test"})): ok, _ = c.get_campaign("c1"); assert ok
    test("Get campaign", t6)

    def t7():
        c = MetaAdsClient(access_token="tok")
        with patch("requests.get", return_value=mr(200, {"data": [{"impressions": "1000"}]})): ok, _ = c.get_campaign_insights("c1"); assert ok
    test("Campaign insights", t7)

    def t8():
        c = MetaAdsClient(access_token="tok")
        with patch("requests.get", return_value=mr(200, {"data": []})): ok, _ = c.list_ad_sets("c1"); assert ok
    test("List ad sets", t8)

    def t9():
        c = MetaAdsClient(access_token="tok", ad_account_id="act_1")
        targeting = {"geo_locations": {"countries": ["US"]}, "age_min": 25, "age_max": 55}
        with patch("requests.post", return_value=mr(200, {"id": "as1"})) as mp:
            ok, _ = c.create_ad_set("c1", "Test AdSet", targeting, daily_budget=25.0)
            body = mp.call_args[1]["json"]; assert body["targeting"] == targeting
    test("Create ad set", t9)

    def t10():
        c = MetaAdsClient(access_token="tok", ad_account_id="act_1")
        with patch("requests.get", return_value=mr(200, {"data": []})): ok, _ = c.list_ads(); assert ok
    test("List ads", t10)

    def t11():
        c = MetaAdsClient(access_token="tok", ad_account_id="act_1")
        with patch("requests.get", return_value=mr(200, {"data": []})): ok, _ = c.list_custom_audiences(); assert ok
    test("List custom audiences", t11)

    def t12():
        c = MetaAdsClient(access_token="tok", ad_account_id="act_1")
        with patch("requests.get", return_value=mr(200, {"id": "act_1", "name": "Test"})): ok, _ = c.get_ad_account(); assert ok
    test("Get ad account", t12)

    def t13():
        c = MetaAdsClient(access_token="tok")
        with patch("requests.get", return_value=mr(401, {"error": {"message": "bad token"}})): ok, _ = c.health(); assert not ok
    test("HTTP error", t13)

    def t14():
        c = MetaAdsClient(access_token="tok")
        with patch("requests.get", side_effect=requests.Timeout): ok, _ = c.health(); assert not ok
    test("Timeout", t14)

    def t15():
        c = MetaAdsClient(access_token="tok")
        with patch("requests.get", return_value=mr(200, {})): c.health()
        assert ACTION_LOG.exists()
    test("Action log", t15)

    print(f"\n  {'=' * 50}"); print(f"  Meta Ads Bridge: {'PASS' if passed == total else 'FAIL'}"); print(f"  Passed: {passed}/{total}"); print(f"  {'=' * 50}")
    return passed == total

if __name__ == "__main__":
    if "--test" in sys.argv: sys.exit(0 if _run_tests() else 1)
    elif "--health" in sys.argv:
        c = MetaAdsClient(); ok, r = c.health(); print(f"{'✅' if ok else '❌'} Meta Ads: {r if not ok else 'connected'}")
    else: print("Usage: python3 scripts/meta_ads_bridge.py --test|--health")
