#!/usr/bin/env python3
"""
NemoClaw ↔ Resend Bridge
Transactional email (receipts, notifications, alerts).

Usage:
    from resend_bridge import ResendClient
    rc = ResendClient()
    ok, result = rc.send_email("user@test.com", "Welcome!", "<h1>Hello</h1>")

    python3 scripts/resend_bridge.py --test
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
ACTION_LOG = LOG_DIR / "resend-actions.jsonl"
BASE_URL = "https://api.resend.com"


class ResendClient:
    """NemoClaw ↔ Resend bridge."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("RESEND_API_KEY", "")
        self.timeout = 30
        self.default_from = os.environ.get("RESEND_FROM_EMAIL", "onboarding@resend.dev")
        LOG_DIR.mkdir(parents=True, exist_ok=True)

    def _headers(self):
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def _log(self, action, params, success, error=None):
        entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "service": "resend",
                 "action": action, "params": params, "success": success}
        if error: entry["error"] = str(error)[:200]
        try:
            with open(ACTION_LOG, "a") as f: f.write(json.dumps(entry) + "\n")
        except Exception: pass

    def _post(self, path, data=None):
        try:
            r = requests.post(f"{BASE_URL}{path}", headers=self._headers(),
                            json=data or {}, timeout=self.timeout)
            if r.status_code >= 400:
                return (False, f"HTTP {r.status_code}: {r.text[:300]}")
            return (True, r.json())
        except requests.ConnectionError: return (False, "Resend API not reachable")
        except requests.Timeout: return (False, "Request timed out")
        except Exception as e: return (False, str(e))

    def _get(self, path, params=None):
        try:
            r = requests.get(f"{BASE_URL}{path}", headers=self._headers(),
                           params=params, timeout=self.timeout)
            if r.status_code >= 400:
                return (False, f"HTTP {r.status_code}: {r.text[:300]}")
            return (True, r.json())
        except requests.ConnectionError: return (False, "Resend API not reachable")
        except requests.Timeout: return (False, "Request timed out")
        except Exception as e: return (False, str(e))

    def health(self):
        """Check API connectivity."""
        ok, result = self._get("/domains")
        self._log("health", {}, ok, error=result if not ok else None)
        return (ok, result)

    def send_email(self, to, subject, html, from_email=None, text=None,
                   reply_to=None, cc=None, bcc=None, tags=None):
        """Send an email. Returns (ok, {id})."""
        data = {
            "from": from_email or self.default_from,
            "to": [to] if isinstance(to, str) else to,
            "subject": subject,
            "html": html,
        }
        if text: data["text"] = text
        if reply_to: data["reply_to"] = reply_to
        if cc: data["cc"] = cc if isinstance(cc, list) else [cc]
        if bcc: data["bcc"] = bcc if isinstance(bcc, list) else [bcc]
        if tags: data["tags"] = tags

        ok, result = self._post("/emails", data)
        self._log("send_email", {"to": to, "subject": subject}, ok)
        return (ok, result)

    def send_batch(self, emails):
        """Send batch emails. emails = [{to, subject, html, from}]. Returns (ok, [{id}])."""
        for e in emails:
            e.setdefault("from", self.default_from)
            if isinstance(e.get("to"), str): e["to"] = [e["to"]]
        ok, result = self._post("/emails/batch", emails)
        self._log("send_batch", {"count": len(emails)}, ok)
        return (ok, result)

    def get_email(self, email_id):
        """Get email status. Returns (ok, email)."""
        ok, result = self._get(f"/emails/{email_id}")
        self._log("get_email", {"id": email_id}, ok)
        return (ok, result)

    def list_domains(self):
        """List verified domains. Returns (ok, {data})."""
        ok, result = self._get("/domains")
        self._log("list_domains", {}, ok)
        return (ok, result)


def _run_tests():
    from unittest.mock import patch, MagicMock
    passed = total = 0

    def test(name, fn):
        nonlocal passed, total
        total += 1
        try: fn(); passed += 1; print(f"  ✅ {name}")
        except Exception as e: print(f"  ❌ {name}: {e}")

    print("=" * 60)
    print("  Resend Bridge Tests")
    print("=" * 60)

    def mr(status=200, data=None):
        r = MagicMock(); r.status_code = status; r.json.return_value = data or {}
        r.text = json.dumps(data) if data else ""; return r

    def t1():
        c = ResendClient(api_key="k"); assert c.api_key == "k"
    test("Constructor", t1)

    def t2():
        c = ResendClient(api_key="k")
        with patch("requests.get", return_value=mr(200, {"data": []})): ok, _ = c.health(); assert ok
    test("Health", t2)

    def t3():
        c = ResendClient(api_key="k")
        with patch("requests.post", return_value=mr(200, {"id": "e1"})) as mp:
            ok, r = c.send_email("u@t.com", "Hi", "<p>Hello</p>")
            assert ok and r["id"] == "e1"
            body = mp.call_args[1]["json"]
            assert body["to"] == ["u@t.com"] and body["subject"] == "Hi"
    test("Send email", t3)

    def t4():
        c = ResendClient(api_key="k")
        with patch("requests.post", return_value=mr(200, {"id": "e2"})) as mp:
            c.send_email("u@t.com", "Re", "<p>x</p>", reply_to="r@t.com", cc="c@t.com")
            body = mp.call_args[1]["json"]
            assert body["reply_to"] == "r@t.com" and body["cc"] == ["c@t.com"]
    test("Email with cc/reply_to", t4)

    def t5():
        c = ResendClient(api_key="k")
        with patch("requests.post", return_value=mr(200, [{"id": "b1"}, {"id": "b2"}])):
            ok, r = c.send_batch([{"to": "a@b.com", "subject": "A", "html": "x"},
                                  {"to": "c@d.com", "subject": "B", "html": "y"}])
            assert ok
    test("Batch send", t5)

    def t6():
        c = ResendClient(api_key="k")
        with patch("requests.get", return_value=mr(200, {"id": "e1", "status": "delivered"})):
            ok, r = c.get_email("e1"); assert ok
    test("Get email status", t6)

    def t7():
        c = ResendClient(api_key="k")
        with patch("requests.get", return_value=mr(200, {"data": []})):
            ok, _ = c.list_domains(); assert ok
    test("List domains", t7)

    def t8():
        c = ResendClient(api_key="k")
        with patch("requests.post", return_value=mr(200, {"id": "e3"})) as mp:
            c.send_email(["a@b.com", "c@d.com"], "Multi", "<p>x</p>")
            body = mp.call_args[1]["json"]
            assert body["to"] == ["a@b.com", "c@d.com"]
    test("Multiple recipients", t8)

    def t9():
        c = ResendClient(api_key="k")
        with patch("requests.post", return_value=mr(200, {"id": "e4"})) as mp:
            c.send_email("u@t.com", "Tags", "<p>x</p>", tags=[{"name": "campaign", "value": "launch"}])
            body = mp.call_args[1]["json"]
            assert body["tags"][0]["name"] == "campaign"
    test("Tags support", t9)

    def t10():
        c = ResendClient(api_key="k")
        with patch("requests.post", return_value=mr(403, {"message": "forbidden"})):
            ok, r = c.send_email("u@t.com", "X", "x"); assert not ok
    test("HTTP error", t10)

    def t11():
        c = ResendClient(api_key="k")
        with patch("requests.post", side_effect=requests.Timeout):
            ok, _ = c.send_email("u@t.com", "X", "x"); assert not ok
    test("Timeout", t11)

    def t12():
        c = ResendClient(api_key="k")
        with patch("requests.get", return_value=mr(200, {})):
            c.health()
        assert ACTION_LOG.exists()
    test("Action log", t12)

    print(f"\n  {'=' * 50}")
    print(f"  Resend Bridge: {'PASS' if passed == total else 'FAIL'}")
    print(f"  Passed: {passed}/{total}")
    print(f"  {'=' * 50}")
    return passed == total


if __name__ == "__main__":
    if "--test" in sys.argv: sys.exit(0 if _run_tests() else 1)
    elif "--health" in sys.argv:
        c = ResendClient(); ok, r = c.health()
        print(f"{'✅' if ok else '❌'} Resend: {r if not ok else 'connected'}")
    else: print("Usage: python3 scripts/resend_bridge.py --test|--health")
