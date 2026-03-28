#!/usr/bin/env python3
"""
NemoClaw ↔ HubSpot CRM Bridge
Contacts, companies, deals CRUD with pipeline management.

Usage:
    from hubspot_bridge import HubSpotClient
    hs = HubSpotClient()
    ok, contact = hs.create_contact("john@example.com", "John", "Doe")

    python3 scripts/hubspot_bridge.py --test
    python3 scripts/hubspot_bridge.py --health
"""

import json
import os
import sys
import time
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    import requests
except ImportError:
    print("ERROR: requests required. pip install requests --break-system-packages")
    sys.exit(1)

REPO = Path(__file__).resolve().parent.parent
LOG_DIR = Path.home() / ".nemoclaw" / "integrations"
ACTION_LOG = LOG_DIR / "hubspot-actions.jsonl"
BASE_URL = "https://api.hubapi.com"


class HubSpotClient:
    """NemoClaw ↔ HubSpot CRM bridge."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("HUBSPOT_ACCESS_TOKEN", "")
        self.base_url = BASE_URL
        self.timeout = 30
        self._nav_count = 0
        self._hour_start = time.time()
        self.max_requests_per_hour = 100  # HubSpot free: 100/10sec burst
        LOG_DIR.mkdir(parents=True, exist_ok=True)

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _log(self, action, params, success, result=None, error=None):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": "hubspot",
            "action": action,
            "params": {k: v for k, v in params.items() if k != "api_key"},
            "success": success,
        }
        if error:
            entry["error"] = str(error)[:200]
        try:
            with open(ACTION_LOG, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

    def _get(self, path, params=None):
        try:
            r = requests.get(f"{self.base_url}{path}", headers=self._headers(),
                           params=params, timeout=self.timeout)
            if r.status_code >= 400:
                return (False, f"HTTP {r.status_code}: {r.text[:300]}")
            return (True, r.json())
        except requests.ConnectionError:
            return (False, "HubSpot API not reachable")
        except requests.Timeout:
            return (False, "Request timed out")
        except Exception as e:
            return (False, str(e))

    def _post(self, path, data=None):
        try:
            r = requests.post(f"{self.base_url}{path}", headers=self._headers(),
                            json=data or {}, timeout=self.timeout)
            if r.status_code >= 400:
                return (False, f"HTTP {r.status_code}: {r.text[:300]}")
            return (True, r.json())
        except requests.ConnectionError:
            return (False, "HubSpot API not reachable")
        except requests.Timeout:
            return (False, "Request timed out")
        except Exception as e:
            return (False, str(e))

    def _patch(self, path, data=None):
        try:
            r = requests.patch(f"{self.base_url}{path}", headers=self._headers(),
                             json=data or {}, timeout=self.timeout)
            if r.status_code >= 400:
                return (False, f"HTTP {r.status_code}: {r.text[:300]}")
            return (True, r.json())
        except requests.ConnectionError:
            return (False, "HubSpot API not reachable")
        except requests.Timeout:
            return (False, "Request timed out")
        except Exception as e:
            return (False, str(e))

    def _delete(self, path):
        try:
            r = requests.delete(f"{self.base_url}{path}", headers=self._headers(),
                              timeout=self.timeout)
            if r.status_code >= 400:
                return (False, f"HTTP {r.status_code}: {r.text[:300]}")
            return (True, {"deleted": True})
        except Exception as e:
            return (False, str(e))

    # ── Health ──

    def health(self):
        """Check HubSpot API connectivity. Returns (ok, result)."""
        ok, result = self._get("/crm/v3/objects/contacts", {"limit": 1})
        self._log("health", {}, ok, error=result if not ok else None)
        return (ok, result)

    # ── Contacts ──

    def create_contact(self, email, first_name=None, last_name=None, phone=None,
                       company=None, properties=None):
        """Create a contact. Returns (ok, contact)."""
        props = {"email": email}
        if first_name:
            props["firstname"] = first_name
        if last_name:
            props["lastname"] = last_name
        if phone:
            props["phone"] = phone
        if company:
            props["company"] = company
        if properties:
            props.update(properties)

        ok, result = self._post("/crm/v3/objects/contacts", {"properties": props})
        self._log("create_contact", {"email": email}, ok, error=result if not ok else None)
        return (ok, result)

    def get_contact(self, contact_id):
        """Get contact by ID. Returns (ok, contact)."""
        ok, result = self._get(f"/crm/v3/objects/contacts/{contact_id}")
        self._log("get_contact", {"id": contact_id}, ok)
        return (ok, result)

    def search_contacts(self, query, limit=10):
        """Search contacts. Returns (ok, {results})."""
        body = {
            "query": query,
            "limit": limit,
        }
        ok, result = self._post("/crm/v3/objects/contacts/search", body)
        self._log("search_contacts", {"query": query}, ok)
        return (ok, result)

    def update_contact(self, contact_id, properties):
        """Update contact properties. Returns (ok, contact)."""
        ok, result = self._patch(f"/crm/v3/objects/contacts/{contact_id}",
                                 {"properties": properties})
        self._log("update_contact", {"id": contact_id}, ok)
        return (ok, result)

    def list_contacts(self, limit=10, after=None):
        """List contacts with pagination. Returns (ok, {results, paging})."""
        params = {"limit": limit}
        if after:
            params["after"] = after
        ok, result = self._get("/crm/v3/objects/contacts", params)
        self._log("list_contacts", {"limit": limit}, ok)
        return (ok, result)

    # ── Companies ──

    def create_company(self, name, domain=None, industry=None, properties=None):
        """Create a company. Returns (ok, company)."""
        props = {"name": name}
        if domain:
            props["domain"] = domain
        if industry:
            props["industry"] = industry
        if properties:
            props.update(properties)

        ok, result = self._post("/crm/v3/objects/companies", {"properties": props})
        self._log("create_company", {"name": name}, ok)
        return (ok, result)

    def get_company(self, company_id):
        """Get company by ID. Returns (ok, company)."""
        ok, result = self._get(f"/crm/v3/objects/companies/{company_id}")
        self._log("get_company", {"id": company_id}, ok)
        return (ok, result)

    def search_companies(self, query, limit=10):
        """Search companies. Returns (ok, {results})."""
        body = {"query": query, "limit": limit}
        ok, result = self._post("/crm/v3/objects/companies/search", body)
        self._log("search_companies", {"query": query}, ok)
        return (ok, result)

    # ── Deals ──

    def create_deal(self, name, stage="appointmentscheduled", amount=None,
                    pipeline="default", properties=None):
        """Create a deal. Returns (ok, deal)."""
        props = {
            "dealname": name,
            "dealstage": stage,
            "pipeline": pipeline,
        }
        if amount is not None:
            props["amount"] = str(amount)
        if properties:
            props.update(properties)

        ok, result = self._post("/crm/v3/objects/deals", {"properties": props})
        self._log("create_deal", {"name": name, "stage": stage}, ok)
        return (ok, result)

    def get_deal(self, deal_id):
        """Get deal by ID. Returns (ok, deal)."""
        ok, result = self._get(f"/crm/v3/objects/deals/{deal_id}")
        self._log("get_deal", {"id": deal_id}, ok)
        return (ok, result)

    def update_deal(self, deal_id, properties):
        """Update deal properties (e.g., move stage). Returns (ok, deal)."""
        ok, result = self._patch(f"/crm/v3/objects/deals/{deal_id}",
                                 {"properties": properties})
        self._log("update_deal", {"id": deal_id}, ok)
        return (ok, result)

    def list_deals(self, limit=10, after=None):
        """List deals with pagination. Returns (ok, {results, paging})."""
        params = {"limit": limit}
        if after:
            params["after"] = after
        ok, result = self._get("/crm/v3/objects/deals", params)
        self._log("list_deals", {"limit": limit}, ok)
        return (ok, result)

    def search_deals(self, query, limit=10):
        """Search deals. Returns (ok, {results})."""
        body = {"query": query, "limit": limit}
        ok, result = self._post("/crm/v3/objects/deals/search", body)
        self._log("search_deals", {"query": query}, ok)
        return (ok, result)

    # ── Associations ──

    def associate(self, from_type, from_id, to_type, to_id, assoc_type=None):
        """Associate two objects (e.g., contact to deal). Returns (ok, result)."""
        # Default association type
        if not assoc_type:
            type_map = {
                ("contacts", "deals"): "contact_to_deal",
                ("contacts", "companies"): "contact_to_company",
                ("deals", "companies"): "deal_to_company",
            }
            assoc_type = type_map.get((from_type, to_type), f"{from_type}_to_{to_type}")

        path = f"/crm/v3/objects/{from_type}/{from_id}/associations/{to_type}/{to_id}/{assoc_type}"
        ok, result = self._post(path + "?associationType=" + assoc_type, {})
        # HubSpot v3 uses PUT for associations
        if not ok:
            try:
                r = requests.put(f"{self.base_url}{path}",
                               headers=self._headers(), timeout=self.timeout)
                if r.status_code < 400:
                    ok, result = True, {"associated": True}
            except Exception:
                pass
        self._log("associate", {"from": f"{from_type}/{from_id}", "to": f"{to_type}/{to_id}"}, ok)
        return (ok, result)

    # ── Pipelines ──

    def list_pipelines(self, object_type="deals"):
        """List pipelines. Returns (ok, {results})."""
        ok, result = self._get(f"/crm/v3/pipelines/{object_type}")
        self._log("list_pipelines", {"type": object_type}, ok)
        return (ok, result)


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS
# ═══════════════════════════════════════════════════════════════════════════════

def _run_tests():
    from unittest.mock import patch, MagicMock

    passed = 0
    total = 0

    def test(name, fn):
        nonlocal passed, total
        total += 1
        try:
            fn()
            passed += 1
            print(f"  ✅ {name}")
        except Exception as e:
            print(f"  ❌ {name}: {e}")

    print("=" * 60)
    print("  HubSpot Bridge Tests")
    print("=" * 60)

    def mock_resp(status=200, data=None):
        r = MagicMock()
        r.status_code = status
        r.json.return_value = data or {}
        r.text = json.dumps(data) if data else ""
        return r

    # 1: Constructor
    def t_constructor():
        c = HubSpotClient(api_key="test-key")
        assert c.api_key == "test-key"
        assert c.base_url == BASE_URL
    test("Constructor", t_constructor)

    # 2: Health success
    def t_health():
        c = HubSpotClient(api_key="k")
        with patch("requests.get", return_value=mock_resp(200, {"results": []})):
            ok, r = c.health()
            assert ok is True
    test("Health success", t_health)

    # 3: Health failure
    def t_health_fail():
        c = HubSpotClient(api_key="k")
        with patch("requests.get", side_effect=requests.ConnectionError):
            ok, r = c.health()
            assert ok is False
    test("Health failure", t_health_fail)

    # 4: Create contact
    def t_create_contact():
        c = HubSpotClient(api_key="k")
        resp = {"id": "123", "properties": {"email": "j@test.com"}}
        with patch("requests.post", return_value=mock_resp(200, resp)) as mp:
            ok, r = c.create_contact("j@test.com", "John", "Doe")
            assert ok and r["id"] == "123"
            body = mp.call_args[1]["json"]
            assert body["properties"]["email"] == "j@test.com"
            assert body["properties"]["firstname"] == "John"
    test("Create contact", t_create_contact)

    # 5: Get contact
    def t_get_contact():
        c = HubSpotClient(api_key="k")
        with patch("requests.get", return_value=mock_resp(200, {"id": "123"})):
            ok, r = c.get_contact("123")
            assert ok and r["id"] == "123"
    test("Get contact", t_get_contact)

    # 6: Search contacts
    def t_search_contacts():
        c = HubSpotClient(api_key="k")
        with patch("requests.post", return_value=mock_resp(200, {"results": [{"id": "1"}]})):
            ok, r = c.search_contacts("john")
            assert ok and len(r["results"]) == 1
    test("Search contacts", t_search_contacts)

    # 7: Update contact
    def t_update_contact():
        c = HubSpotClient(api_key="k")
        with patch("requests.patch", return_value=mock_resp(200, {"id": "123"})):
            ok, r = c.update_contact("123", {"phone": "+1234"})
            assert ok
    test("Update contact", t_update_contact)

    # 8: List contacts
    def t_list_contacts():
        c = HubSpotClient(api_key="k")
        with patch("requests.get", return_value=mock_resp(200, {"results": [], "paging": {}})):
            ok, r = c.list_contacts(limit=5)
            assert ok and "results" in r
    test("List contacts", t_list_contacts)

    # 9: Create company
    def t_create_company():
        c = HubSpotClient(api_key="k")
        with patch("requests.post", return_value=mock_resp(200, {"id": "c1"})) as mp:
            ok, r = c.create_company("Acme Inc", domain="acme.com", industry="tech")
            body = mp.call_args[1]["json"]
            assert body["properties"]["name"] == "Acme Inc"
            assert body["properties"]["domain"] == "acme.com"
    test("Create company", t_create_company)

    # 10: Get company
    def t_get_company():
        c = HubSpotClient(api_key="k")
        with patch("requests.get", return_value=mock_resp(200, {"id": "c1"})):
            ok, r = c.get_company("c1")
            assert ok
    test("Get company", t_get_company)

    # 11: Search companies
    def t_search_companies():
        c = HubSpotClient(api_key="k")
        with patch("requests.post", return_value=mock_resp(200, {"results": []})):
            ok, r = c.search_companies("acme")
            assert ok
    test("Search companies", t_search_companies)

    # 12: Create deal
    def t_create_deal():
        c = HubSpotClient(api_key="k")
        with patch("requests.post", return_value=mock_resp(200, {"id": "d1"})) as mp:
            ok, r = c.create_deal("Big Deal", stage="qualifiedtobuy", amount=50000)
            body = mp.call_args[1]["json"]
            assert body["properties"]["dealname"] == "Big Deal"
            assert body["properties"]["amount"] == "50000"
    test("Create deal", t_create_deal)

    # 13: Get deal
    def t_get_deal():
        c = HubSpotClient(api_key="k")
        with patch("requests.get", return_value=mock_resp(200, {"id": "d1"})):
            ok, r = c.get_deal("d1")
            assert ok
    test("Get deal", t_get_deal)

    # 14: Update deal
    def t_update_deal():
        c = HubSpotClient(api_key="k")
        with patch("requests.patch", return_value=mock_resp(200, {"id": "d1"})):
            ok, r = c.update_deal("d1", {"dealstage": "closedwon"})
            assert ok
    test("Update deal", t_update_deal)

    # 15: List deals
    def t_list_deals():
        c = HubSpotClient(api_key="k")
        with patch("requests.get", return_value=mock_resp(200, {"results": []})):
            ok, r = c.list_deals()
            assert ok
    test("List deals", t_list_deals)

    # 16: Search deals
    def t_search_deals():
        c = HubSpotClient(api_key="k")
        with patch("requests.post", return_value=mock_resp(200, {"results": []})):
            ok, r = c.search_deals("big")
            assert ok
    test("Search deals", t_search_deals)

    # 17: List pipelines
    def t_pipelines():
        c = HubSpotClient(api_key="k")
        with patch("requests.get", return_value=mock_resp(200, {"results": []})):
            ok, r = c.list_pipelines()
            assert ok
    test("List pipelines", t_pipelines)

    # 18: HTTP error handling
    def t_http_error():
        c = HubSpotClient(api_key="k")
        with patch("requests.get", return_value=mock_resp(401, {"message": "unauthorized"})):
            ok, r = c.health()
            assert ok is False and "401" in r
    test("HTTP error handling", t_http_error)

    # 19: Timeout
    def t_timeout():
        c = HubSpotClient(api_key="k")
        with patch("requests.get", side_effect=requests.Timeout):
            ok, r = c.health()
            assert ok is False and "timed out" in r.lower()
    test("Timeout handling", t_timeout)

    # 20: Action log created
    def t_log():
        c = HubSpotClient(api_key="k")
        with patch("requests.get", return_value=mock_resp(200, {"results": []})):
            c.health()
        assert ACTION_LOG.exists()
    test("Action log created", t_log)

    # 21: Contact with extra properties
    def t_extra_props():
        c = HubSpotClient(api_key="k")
        with patch("requests.post", return_value=mock_resp(200, {"id": "x"})) as mp:
            c.create_contact("a@b.com", properties={"jobtitle": "CEO"})
            body = mp.call_args[1]["json"]
            assert body["properties"]["jobtitle"] == "CEO"
    test("Contact with extra properties", t_extra_props)

    # 22: Pagination
    def t_pagination():
        c = HubSpotClient(api_key="k")
        with patch("requests.get", return_value=mock_resp(200, {"results": []})) as mg:
            c.list_contacts(limit=5, after="abc123")
            params = mg.call_args[1]["params"]
            assert params["after"] == "abc123"
    test("Pagination support", t_pagination)

    print(f"\n  {'=' * 50}")
    print(f"  HubSpot Bridge: {'PASS' if passed == total else 'FAIL'}")
    print(f"  Passed: {passed}/{total}")
    print(f"  {'=' * 50}")
    return passed == total


if __name__ == "__main__":
    if "--test" in sys.argv:
        success = _run_tests()
        sys.exit(0 if success else 1)
    elif "--health" in sys.argv:
        c = HubSpotClient()
        ok, r = c.health()
        print(f"{'✅' if ok else '❌'} HubSpot: {r if not ok else 'connected'}")
        sys.exit(0 if ok else 1)
    else:
        print("Usage: python3 scripts/hubspot_bridge.py --test|--health")
