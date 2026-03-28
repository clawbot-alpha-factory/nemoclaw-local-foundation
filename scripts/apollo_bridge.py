#!/usr/bin/env python3
"""
NemoClaw ↔ Apollo.io Bridge
Lead search, company enrichment, people enrichment.

Usage:
    from apollo_bridge import ApolloClient
    ap = ApolloClient()
    ok, leads = ap.search_people(title="CTO", company_domain="stripe.com")

    python3 scripts/apollo_bridge.py --test
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    import requests
except ImportError:
    sys.exit("ERROR: requests required")

LOG_DIR = Path.home() / ".nemoclaw" / "integrations"
ACTION_LOG = LOG_DIR / "apollo-actions.jsonl"
BASE_URL = "https://api.apollo.io/api/v1"


class ApolloClient:
    """NemoClaw ↔ Apollo.io bridge."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("APOLLO_API_KEY", "")
        self.timeout = 30
        LOG_DIR.mkdir(parents=True, exist_ok=True)

    def _headers(self):
        return {"Content-Type": "application/json", "Cache-Control": "no-cache"}

    def _body_with_key(self, data=None):
        d = data or {}
        d["api_key"] = self.api_key
        return d

    def _log(self, action, params, success, error=None):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": "apollo", "action": action,
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

    def _post(self, path, data=None):
        try:
            r = requests.post(f"{BASE_URL}{path}", headers=self._headers(),
                            json=self._body_with_key(data), timeout=self.timeout)
            if r.status_code >= 400:
                return (False, f"HTTP {r.status_code}: {r.text[:300]}")
            return (True, r.json())
        except requests.ConnectionError:
            return (False, "Apollo API not reachable")
        except requests.Timeout:
            return (False, "Request timed out")
        except Exception as e:
            return (False, str(e))

    def _get(self, path, params=None):
        try:
            p = params or {}
            p["api_key"] = self.api_key
            r = requests.get(f"{BASE_URL}{path}", headers=self._headers(),
                           params=p, timeout=self.timeout)
            if r.status_code >= 400:
                return (False, f"HTTP {r.status_code}: {r.text[:300]}")
            return (True, r.json())
        except requests.ConnectionError:
            return (False, "Apollo API not reachable")
        except requests.Timeout:
            return (False, "Request timed out")
        except Exception as e:
            return (False, str(e))

    # ── Health ──

    def health(self):
        """Check Apollo API connectivity."""
        ok, result = self._post("/mixed_people/search", {"per_page": 1, "page": 1})
        self._log("health", {}, ok, error=result if not ok else None)
        return (ok, result)

    # ── People Search ──

    def search_people(self, title=None, company_domain=None, location=None,
                      seniority=None, industry=None, per_page=10, page=1):
        """Search for people/leads. Returns (ok, {people, pagination})."""
        data = {"per_page": per_page, "page": page}
        if title:
            data["person_titles"] = [title] if isinstance(title, str) else title
        if company_domain:
            data["q_organization_domains"] = company_domain
        if location:
            data["person_locations"] = [location] if isinstance(location, str) else location
        if seniority:
            data["person_seniorities"] = [seniority] if isinstance(seniority, str) else seniority
        if industry:
            data["organization_industry_tag_ids"] = [industry] if isinstance(industry, str) else industry

        ok, result = self._post("/mixed_people/search", data)
        self._log("search_people", {"title": title, "domain": company_domain}, ok)
        return (ok, result)

    # ── People Enrichment ──

    def enrich_person(self, email=None, first_name=None, last_name=None,
                      domain=None, linkedin_url=None):
        """Enrich a person by email or name+domain. Returns (ok, person)."""
        data = {}
        if email:
            data["email"] = email
        if first_name:
            data["first_name"] = first_name
        if last_name:
            data["last_name"] = last_name
        if domain:
            data["domain"] = domain
        if linkedin_url:
            data["linkedin_url"] = linkedin_url

        ok, result = self._post("/people/match", data)
        self._log("enrich_person", {"email": email, "name": f"{first_name} {last_name}"}, ok)
        return (ok, result)

    # ── Company Enrichment ──

    def enrich_company(self, domain):
        """Enrich company by domain. Returns (ok, company)."""
        ok, result = self._post("/organizations/enrich", {"domain": domain})
        self._log("enrich_company", {"domain": domain}, ok)
        return (ok, result)

    # ── Company Search ──

    def search_companies(self, keyword=None, industry=None, location=None,
                         employee_count_min=None, employee_count_max=None,
                         per_page=10, page=1):
        """Search companies. Returns (ok, {organizations, pagination})."""
        data = {"per_page": per_page, "page": page}
        if keyword:
            data["q_organization_keyword_tags"] = [keyword] if isinstance(keyword, str) else keyword
        if location:
            data["organization_locations"] = [location] if isinstance(location, str) else location
        if employee_count_min:
            data["organization_num_employees_ranges"] = [f"{employee_count_min},{employee_count_max or ''}"]

        ok, result = self._post("/mixed_companies/search", data)
        self._log("search_companies", {"keyword": keyword}, ok)
        return (ok, result)

    # ── Email Finder ──

    def find_email(self, first_name, last_name, domain):
        """Find email for a person at a company. Returns (ok, {email, confidence})."""
        data = {"first_name": first_name, "last_name": last_name, "domain": domain}
        ok, result = self._post("/people/match", data)
        self._log("find_email", {"name": f"{first_name} {last_name}", "domain": domain}, ok)
        return (ok, result)

    # ── Bulk Operations ──

    def bulk_enrich_people(self, details_list):
        """Bulk enrich people. details_list = [{email, first_name, last_name, domain}].
        Returns (ok, [results])."""
        ok, result = self._post("/people/bulk_match", {"details": details_list})
        self._log("bulk_enrich", {"count": len(details_list)}, ok)
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
    print("  Apollo.io Bridge Tests")
    print("=" * 60)

    def mock_resp(status=200, data=None):
        r = MagicMock()
        r.status_code = status
        r.json.return_value = data or {}
        r.text = json.dumps(data) if data else ""
        return r

    def t_constructor():
        c = ApolloClient(api_key="test")
        assert c.api_key == "test"
    test("Constructor", t_constructor)

    def t_health():
        c = ApolloClient(api_key="k")
        with patch("requests.post", return_value=mock_resp(200, {"people": []})):
            ok, _ = c.health()
            assert ok
    test("Health", t_health)

    def t_health_fail():
        c = ApolloClient(api_key="k")
        with patch("requests.post", side_effect=requests.ConnectionError):
            ok, _ = c.health()
            assert not ok
    test("Health failure", t_health_fail)

    def t_search_people():
        c = ApolloClient(api_key="k")
        with patch("requests.post", return_value=mock_resp(200, {"people": [{"id": "p1"}]})) as mp:
            ok, r = c.search_people(title="CTO", company_domain="stripe.com")
            assert ok
            body = mp.call_args[1]["json"]
            assert body["person_titles"] == ["CTO"]
            assert body["q_organization_domains"] == "stripe.com"
    test("Search people", t_search_people)

    def t_search_seniority():
        c = ApolloClient(api_key="k")
        with patch("requests.post", return_value=mock_resp(200, {"people": []})) as mp:
            c.search_people(seniority="c_suite", location="San Francisco")
            body = mp.call_args[1]["json"]
            assert body["person_seniorities"] == ["c_suite"]
            assert body["person_locations"] == ["San Francisco"]
    test("Search with seniority + location", t_search_seniority)

    def t_enrich_person():
        c = ApolloClient(api_key="k")
        with patch("requests.post", return_value=mock_resp(200, {"person": {"email": "j@t.com"}})) as mp:
            ok, r = c.enrich_person(email="j@t.com")
            body = mp.call_args[1]["json"]
            assert body["email"] == "j@t.com"
    test("Enrich person", t_enrich_person)

    def t_enrich_person_name():
        c = ApolloClient(api_key="k")
        with patch("requests.post", return_value=mock_resp(200, {})) as mp:
            c.enrich_person(first_name="John", last_name="Doe", domain="acme.com")
            body = mp.call_args[1]["json"]
            assert body["first_name"] == "John"
            assert body["domain"] == "acme.com"
    test("Enrich person by name+domain", t_enrich_person_name)

    def t_enrich_company():
        c = ApolloClient(api_key="k")
        with patch("requests.post", return_value=mock_resp(200, {"organization": {"name": "Stripe"}})):
            ok, r = c.enrich_company("stripe.com")
            assert ok
    test("Enrich company", t_enrich_company)

    def t_search_companies():
        c = ApolloClient(api_key="k")
        with patch("requests.post", return_value=mock_resp(200, {"organizations": []})) as mp:
            ok, _ = c.search_companies(keyword="AI", location="USA")
            body = mp.call_args[1]["json"]
            assert body["q_organization_keyword_tags"] == ["AI"]
    test("Search companies", t_search_companies)

    def t_find_email():
        c = ApolloClient(api_key="k")
        with patch("requests.post", return_value=mock_resp(200, {"person": {"email": "j@s.com"}})):
            ok, r = c.find_email("John", "Doe", "stripe.com")
            assert ok
    test("Find email", t_find_email)

    def t_bulk_enrich():
        c = ApolloClient(api_key="k")
        details = [{"email": "a@b.com"}, {"email": "c@d.com"}]
        with patch("requests.post", return_value=mock_resp(200, {"matches": []})) as mp:
            ok, _ = c.bulk_enrich_people(details)
            body = mp.call_args[1]["json"]
            assert body["details"] == details
    test("Bulk enrich", t_bulk_enrich)

    def t_pagination():
        c = ApolloClient(api_key="k")
        with patch("requests.post", return_value=mock_resp(200, {"people": []})) as mp:
            c.search_people(title="VP", per_page=25, page=3)
            body = mp.call_args[1]["json"]
            assert body["per_page"] == 25 and body["page"] == 3
    test("Pagination", t_pagination)

    def t_http_error():
        c = ApolloClient(api_key="k")
        with patch("requests.post", return_value=mock_resp(401, {"error": "bad key"})):
            ok, r = c.health()
            assert not ok and "401" in r
    test("HTTP error", t_http_error)

    def t_timeout():
        c = ApolloClient(api_key="k")
        with patch("requests.post", side_effect=requests.Timeout):
            ok, r = c.health()
            assert not ok
    test("Timeout", t_timeout)

    def t_log():
        c = ApolloClient(api_key="k")
        with patch("requests.post", return_value=mock_resp(200, {})):
            c.health()
        assert ACTION_LOG.exists()
    test("Action log", t_log)

    def t_linkedin():
        c = ApolloClient(api_key="k")
        with patch("requests.post", return_value=mock_resp(200, {})) as mp:
            c.enrich_person(linkedin_url="https://linkedin.com/in/johndoe")
            body = mp.call_args[1]["json"]
            assert body["linkedin_url"] == "https://linkedin.com/in/johndoe"
    test("LinkedIn URL enrichment", t_linkedin)

    print(f"\n  {'=' * 50}")
    print(f"  Apollo Bridge: {'PASS' if passed == total else 'FAIL'}")
    print(f"  Passed: {passed}/{total}")
    print(f"  {'=' * 50}")
    return passed == total


if __name__ == "__main__":
    if "--test" in sys.argv:
        sys.exit(0 if _run_tests() else 1)
    elif "--health" in sys.argv:
        c = ApolloClient()
        ok, r = c.health()
        print(f"{'✅' if ok else '❌'} Apollo: {r if not ok else 'connected'}")
    else:
        print("Usage: python3 scripts/apollo_bridge.py --test|--health")
