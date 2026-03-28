#!/usr/bin/env python3
"""
NemoClaw ↔ Google Ads Bridge
Campaign management, keyword research, reporting via REST API.

    python3 scripts/google_ads_bridge.py --test
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
ACTION_LOG = LOG_DIR / "google-ads-actions.jsonl"
BASE_URL = "https://googleads.googleapis.com/v17"


class GoogleAdsClient:
    def __init__(self, developer_token: Optional[str] = None, client_id: Optional[str] = None,
                 client_secret: Optional[str] = None, refresh_token: Optional[str] = None,
                 customer_id: Optional[str] = None):
        self.developer_token = developer_token or os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN", "")
        self.client_id = client_id or os.environ.get("GOOGLE_ADS_CLIENT_ID", "")
        self.client_secret = client_secret or os.environ.get("GOOGLE_ADS_CLIENT_SECRET", "")
        self.refresh_token = refresh_token or os.environ.get("GOOGLE_ADS_REFRESH_TOKEN", "")
        self.customer_id = (customer_id or os.environ.get("GOOGLE_ADS_CUSTOMER_ID", "")).replace("-", "")
        self._access_token = None
        self._token_expiry = 0
        self.timeout = 30
        LOG_DIR.mkdir(parents=True, exist_ok=True)

    def _log(self, action, params, success, error=None):
        entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "service": "google_ads", "action": action, "params": params, "success": success}
        if error: entry["error"] = str(error)[:200]
        try:
            with open(ACTION_LOG, "a") as f: f.write(json.dumps(entry) + "\n")
        except Exception: pass

    def _get_access_token(self):
        if self._access_token and time.time() < self._token_expiry:
            return self._access_token
        try:
            r = requests.post("https://oauth2.googleapis.com/token", data={
                "client_id": self.client_id, "client_secret": self.client_secret,
                "refresh_token": self.refresh_token, "grant_type": "refresh_token"
            }, timeout=10)
            if r.status_code == 200:
                data = r.json()
                self._access_token = data["access_token"]
                self._token_expiry = time.time() + data.get("expires_in", 3600) - 60
                return self._access_token
        except Exception:
            pass
        return self._access_token or ""

    def _headers(self):
        return {
            "Authorization": f"Bearer {self._get_access_token()}",
            "developer-token": self.developer_token,
            "Content-Type": "application/json",
        }

    def _post(self, path, data=None):
        try:
            r = requests.post(f"{BASE_URL}/customers/{self.customer_id}{path}",
                            headers=self._headers(), json=data or {}, timeout=self.timeout)
            if r.status_code >= 400: return (False, f"HTTP {r.status_code}: {r.text[:300]}")
            return (True, r.json())
        except requests.ConnectionError: return (False, "Google Ads API not reachable")
        except requests.Timeout: return (False, "Timed out")
        except Exception as e: return (False, str(e))

    def _get(self, path, params=None):
        try:
            r = requests.get(f"{BASE_URL}/customers/{self.customer_id}{path}",
                           headers=self._headers(), params=params, timeout=self.timeout)
            if r.status_code >= 400: return (False, f"HTTP {r.status_code}: {r.text[:300]}")
            return (True, r.json())
        except requests.ConnectionError: return (False, "Google Ads API not reachable")
        except requests.Timeout: return (False, "Timed out")
        except Exception as e: return (False, str(e))

    def health(self):
        """Check API access by listing accessible customers."""
        try:
            r = requests.get(f"{BASE_URL}/customers:listAccessibleCustomers",
                           headers=self._headers(), timeout=10)
            ok = r.status_code < 400
            self._log("health", {}, ok)
            return (ok, r.json() if ok else f"HTTP {r.status_code}")
        except Exception as e:
            self._log("health", {}, False, str(e)); return (False, str(e))

    def query(self, gaql):
        """Execute a Google Ads Query Language (GAQL) query. Returns (ok, {results})."""
        ok, r = self._post("/googleAds:searchStream", {"query": gaql})
        self._log("query", {"gaql": gaql[:100]}, ok); return (ok, r)

    def list_campaigns(self, status=None):
        """List campaigns. Returns (ok, {results})."""
        gaql = "SELECT campaign.id, campaign.name, campaign.status, campaign.advertising_channel_type, metrics.impressions, metrics.clicks, metrics.cost_micros FROM campaign"
        if status: gaql += f" WHERE campaign.status = '{status}'"
        gaql += " ORDER BY campaign.name LIMIT 100"
        return self.query(gaql)

    def get_campaign_performance(self, campaign_id, date_range="LAST_30_DAYS"):
        """Get campaign performance metrics. Returns (ok, {results})."""
        gaql = f"SELECT campaign.name, metrics.impressions, metrics.clicks, metrics.conversions, metrics.cost_micros, metrics.ctr, metrics.average_cpc FROM campaign WHERE campaign.id = {campaign_id} AND segments.date DURING {date_range}"
        return self.query(gaql)

    def list_ad_groups(self, campaign_id):
        gaql = f"SELECT ad_group.id, ad_group.name, ad_group.status, metrics.impressions, metrics.clicks FROM ad_group WHERE campaign.id = {campaign_id} LIMIT 100"
        return self.query(gaql)

    def list_keywords(self, ad_group_id):
        gaql = f"SELECT ad_group_criterion.keyword.text, ad_group_criterion.keyword.match_type, metrics.impressions, metrics.clicks, metrics.cost_micros FROM ad_group_criterion WHERE ad_group.id = {ad_group_id} AND ad_group_criterion.type = 'KEYWORD' LIMIT 100"
        return self.query(gaql)

    def get_account_summary(self, date_range="LAST_30_DAYS"):
        gaql = f"SELECT metrics.impressions, metrics.clicks, metrics.conversions, metrics.cost_micros, metrics.ctr, metrics.average_cpc FROM customer WHERE segments.date DURING {date_range}"
        return self.query(gaql)

    def keyword_ideas(self, keywords, language_id="1000", location_id="2840"):
        """Get keyword suggestions. Returns (ok, {results})."""
        ok, r = self._post(":generateKeywordIdeas", {
            "keywordSeed": {"keywords": keywords if isinstance(keywords, list) else [keywords]},
            "language": f"languageConstants/{language_id}",
            "geoTargetConstants": [f"geoTargetConstants/{location_id}"],
        })
        self._log("keyword_ideas", {"keywords": keywords}, ok); return (ok, r)


def _run_tests():
    from unittest.mock import patch, MagicMock
    passed = total = 0
    def test(name, fn):
        nonlocal passed, total; total += 1
        try: fn(); passed += 1; print(f"  ✅ {name}")
        except Exception as e: print(f"  ❌ {name}: {e}")

    print("=" * 60); print("  Google Ads Bridge Tests"); print("=" * 60)

    def mr(s=200, d=None):
        r = MagicMock(); r.status_code = s; r.json.return_value = d or {}; r.text = json.dumps(d) if d else ""; return r

    def t1(): c = GoogleAdsClient(developer_token="dt", customer_id="123-456-7890"); assert c.customer_id == "1234567890"
    test("Constructor strips dashes", t1)

    def t2():
        c = GoogleAdsClient(developer_token="dt")
        with patch("requests.get", return_value=mr(200, {"resourceNames": ["customers/123"]})): ok, _ = c.health(); assert ok
    test("Health", t2)

    def t3():
        c = GoogleAdsClient(developer_token="dt"); c._access_token = "tok"; c._token_expiry = time.time() + 3600
        with patch("requests.post", return_value=mr(200, [{"results": []}])) as mp:
            ok, _ = c.list_campaigns()
            body = mp.call_args[1]["json"]; assert "campaign.id" in body["query"]
    test("List campaigns", t3)

    def t4():
        c = GoogleAdsClient(developer_token="dt"); c._access_token = "tok"; c._token_expiry = time.time() + 3600
        with patch("requests.post", return_value=mr(200, [{"results": []}])):
            ok, _ = c.list_campaigns(status="ENABLED"); assert ok
    test("List campaigns filtered", t4)

    def t5():
        c = GoogleAdsClient(developer_token="dt"); c._access_token = "tok"; c._token_expiry = time.time() + 3600
        with patch("requests.post", return_value=mr(200, [{"results": []}])):
            ok, _ = c.get_campaign_performance("12345"); assert ok
    test("Campaign performance", t5)

    def t6():
        c = GoogleAdsClient(developer_token="dt"); c._access_token = "tok"; c._token_expiry = time.time() + 3600
        with patch("requests.post", return_value=mr(200, [{"results": []}])):
            ok, _ = c.list_ad_groups("12345"); assert ok
    test("List ad groups", t6)

    def t7():
        c = GoogleAdsClient(developer_token="dt"); c._access_token = "tok"; c._token_expiry = time.time() + 3600
        with patch("requests.post", return_value=mr(200, [{"results": []}])):
            ok, _ = c.list_keywords("67890"); assert ok
    test("List keywords", t7)

    def t8():
        c = GoogleAdsClient(developer_token="dt"); c._access_token = "tok"; c._token_expiry = time.time() + 3600
        with patch("requests.post", return_value=mr(200, [{"results": []}])):
            ok, _ = c.get_account_summary(); assert ok
    test("Account summary", t8)

    def t9():
        c = GoogleAdsClient(developer_token="dt"); c._access_token = "tok"; c._token_expiry = time.time() + 3600
        with patch("requests.post", return_value=mr(200, {"results": []})) as mp:
            ok, _ = c.keyword_ideas(["ai saas", "automation tool"])
            body = mp.call_args[1]["json"]; assert body["keywordSeed"]["keywords"] == ["ai saas", "automation tool"]
    test("Keyword ideas", t9)

    def t10():
        c = GoogleAdsClient(developer_token="dt"); c._access_token = "tok"; c._token_expiry = time.time() + 3600
        with patch("requests.post", return_value=mr(200, [{"results": []}])) as mp:
            c.query("SELECT campaign.name FROM campaign LIMIT 5")
            body = mp.call_args[1]["json"]; assert body["query"] == "SELECT campaign.name FROM campaign LIMIT 5"
    test("Raw GAQL query", t10)

    def t11():
        c = GoogleAdsClient(developer_token="dt")
        with patch("requests.get", return_value=mr(403, {"error": "forbidden"})): ok, _ = c.health(); assert not ok
    test("HTTP error", t11)

    def t12():
        c = GoogleAdsClient(developer_token="dt")
        with patch("requests.get", side_effect=requests.Timeout): ok, _ = c.health(); assert not ok
    test("Timeout", t12)

    def t13():
        # Token refresh
        c = GoogleAdsClient(developer_token="dt", client_id="ci", client_secret="cs", refresh_token="rt")
        with patch("requests.post", return_value=mr(200, {"access_token": "new_tok", "expires_in": 3600})):
            tok = c._get_access_token(); assert tok == "new_tok"
    test("Token refresh", t13)

    def t14():
        c = GoogleAdsClient(developer_token="dt")
        with patch("requests.get", return_value=mr(200, {})): c.health()
        assert ACTION_LOG.exists()
    test("Action log", t14)

    print(f"\n  {'=' * 50}"); print(f"  Google Ads Bridge: {'PASS' if passed == total else 'FAIL'}"); print(f"  Passed: {passed}/{total}"); print(f"  {'=' * 50}")
    return passed == total

if __name__ == "__main__":
    if "--test" in sys.argv: sys.exit(0 if _run_tests() else 1)
    elif "--health" in sys.argv:
        c = GoogleAdsClient(); ok, r = c.health(); print(f"{'✅' if ok else '❌'} Google Ads: {r if not ok else 'connected'}")
    else: print("Usage: python3 scripts/google_ads_bridge.py --test|--health")
