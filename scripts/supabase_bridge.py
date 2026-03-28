#!/usr/bin/env python3
"""
NemoClaw ↔ Supabase Bridge
PostgreSQL database, auth, file storage via Supabase REST API.

Usage:
    from supabase_bridge import SupabaseClient
    sb = SupabaseClient()
    ok, rows = sb.select("leads", filters={"status": "eq.new"}, limit=10)
    ok, row = sb.insert("leads", {"email": "j@test.com", "name": "John"})

    python3 scripts/supabase_bridge.py --test
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
ACTION_LOG = LOG_DIR / "supabase-actions.jsonl"


class SupabaseClient:
    """NemoClaw ↔ Supabase bridge (REST API, no SDK dependency)."""

    def __init__(self, url: Optional[str] = None, anon_key: Optional[str] = None,
                 service_key: Optional[str] = None):
        self.url = (url or os.environ.get("SUPABASE_URL", "")).rstrip("/")
        self.anon_key = anon_key or os.environ.get("SUPABASE_ANON_KEY", "")
        self.service_key = service_key or os.environ.get("SUPABASE_SERVICE_KEY", "")
        self.timeout = 30
        LOG_DIR.mkdir(parents=True, exist_ok=True)

    def _headers(self, use_service_key=False):
        key = self.service_key if use_service_key else self.anon_key
        return {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    def _log(self, action, params, success, error=None):
        entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "service": "supabase",
                 "action": action, "params": params, "success": success}
        if error: entry["error"] = str(error)[:200]
        try:
            with open(ACTION_LOG, "a") as f: f.write(json.dumps(entry) + "\n")
        except Exception: pass

    def _rest(self, method, path, data=None, params=None, use_service_key=False):
        try:
            url = f"{self.url}/rest/v1{path}"
            r = getattr(requests, method)(url, headers=self._headers(use_service_key),
                                          json=data, params=params, timeout=self.timeout)
            if r.status_code >= 400:
                return (False, f"HTTP {r.status_code}: {r.text[:300]}")
            try:
                return (True, r.json())
            except Exception:
                return (True, {"status": r.status_code})
        except requests.ConnectionError: return (False, "Supabase not reachable")
        except requests.Timeout: return (False, "Request timed out")
        except Exception as e: return (False, str(e))

    # ── Health ──

    def health(self):
        """Check Supabase connectivity."""
        try:
            r = requests.get(f"{self.url}/rest/v1/", headers=self._headers(), timeout=10)
            ok = r.status_code < 400
            self._log("health", {}, ok)
            return (ok, {"status": r.status_code})
        except Exception as e:
            self._log("health", {}, False, str(e))
            return (False, str(e))

    # ── Database CRUD ──

    def select(self, table, columns="*", filters=None, order=None, limit=None, offset=None):
        """SELECT from table. filters = {"column": "eq.value"}. Returns (ok, [rows])."""
        params = {"select": columns}
        if filters:
            for col, val in filters.items():
                params[col] = val
        if order: params["order"] = order
        if limit: params["limit"] = limit
        if offset: params["offset"] = offset

        ok, result = self._rest("get", f"/{table}", params=params)
        self._log("select", {"table": table, "filters": filters}, ok)
        return (ok, result)

    def insert(self, table, data, upsert=False):
        """INSERT into table. Returns (ok, [inserted_rows])."""
        headers = self._headers(use_service_key=True)
        if upsert:
            headers["Prefer"] = "return=representation,resolution=merge-duplicates"
        try:
            r = requests.post(f"{self.url}/rest/v1/{table}", headers=headers,
                            json=data if isinstance(data, list) else [data], timeout=self.timeout)
            if r.status_code >= 400:
                self._log("insert", {"table": table}, False, r.text[:200])
                return (False, f"HTTP {r.status_code}: {r.text[:300]}")
            result = r.json()
            self._log("insert", {"table": table}, True)
            return (True, result)
        except Exception as e:
            self._log("insert", {"table": table}, False, str(e))
            return (False, str(e))

    def update(self, table, data, filters):
        """UPDATE table SET data WHERE filters. Returns (ok, [updated_rows])."""
        params = {}
        for col, val in filters.items():
            params[col] = val
        ok, result = self._rest("patch", f"/{table}", data=data, params=params, use_service_key=True)
        self._log("update", {"table": table, "filters": filters}, ok)
        return (ok, result)

    def delete(self, table, filters):
        """DELETE from table WHERE filters. Returns (ok, result)."""
        params = {}
        for col, val in filters.items():
            params[col] = val
        ok, result = self._rest("delete", f"/{table}", params=params, use_service_key=True)
        self._log("delete", {"table": table, "filters": filters}, ok)
        return (ok, result)

    def rpc(self, function_name, params=None):
        """Call a Supabase database function. Returns (ok, result)."""
        try:
            r = requests.post(f"{self.url}/rest/v1/rpc/{function_name}",
                            headers=self._headers(use_service_key=True),
                            json=params or {}, timeout=self.timeout)
            if r.status_code >= 400:
                return (False, f"HTTP {r.status_code}: {r.text[:300]}")
            return (True, r.json())
        except Exception as e:
            return (False, str(e))

    # ── Storage ──

    def upload_file(self, bucket, path, file_bytes, content_type="application/octet-stream"):
        """Upload file to storage. Returns (ok, {Key})."""
        try:
            headers = {
                "apikey": self.service_key,
                "Authorization": f"Bearer {self.service_key}",
                "Content-Type": content_type,
            }
            r = requests.post(f"{self.url}/storage/v1/object/{bucket}/{path}",
                            headers=headers, data=file_bytes, timeout=60)
            if r.status_code >= 400:
                return (False, f"HTTP {r.status_code}: {r.text[:300]}")
            return (True, r.json())
        except Exception as e:
            return (False, str(e))

    def get_public_url(self, bucket, path):
        """Get public URL for a file. Returns URL string."""
        return f"{self.url}/storage/v1/object/public/{bucket}/{path}"

    def list_files(self, bucket, path="", limit=100):
        """List files in bucket. Returns (ok, [files])."""
        try:
            r = requests.post(f"{self.url}/storage/v1/object/list/{bucket}",
                            headers=self._headers(use_service_key=True),
                            json={"prefix": path, "limit": limit}, timeout=self.timeout)
            if r.status_code >= 400:
                return (False, f"HTTP {r.status_code}: {r.text[:300]}")
            return (True, r.json())
        except Exception as e:
            return (False, str(e))


def _run_tests():
    from unittest.mock import patch, MagicMock
    passed = total = 0

    def test(name, fn):
        nonlocal passed, total
        total += 1
        try: fn(); passed += 1; print(f"  ✅ {name}")
        except Exception as e: print(f"  ❌ {name}: {e}")

    print("=" * 60)
    print("  Supabase Bridge Tests")
    print("=" * 60)

    def mr(status=200, data=None):
        r = MagicMock(); r.status_code = status; r.json.return_value = data or {}
        r.text = json.dumps(data) if data else ""; return r

    def t1():
        c = SupabaseClient(url="https://x.supabase.co", anon_key="k")
        assert c.url == "https://x.supabase.co"
    test("Constructor", t1)

    def t2():
        c = SupabaseClient(url="https://x.supabase.co", anon_key="k")
        with patch("requests.get", return_value=mr(200)): ok, _ = c.health(); assert ok
    test("Health", t2)

    def t3():
        c = SupabaseClient(url="https://x.supabase.co", anon_key="k")
        with patch("requests.get", return_value=mr(200, [{"id": 1, "email": "j@t.com"}])) as mg:
            ok, rows = c.select("leads", filters={"status": "eq.new"}, limit=5)
            assert ok
            params = mg.call_args[1]["params"]
            assert params["status"] == "eq.new"
    test("Select with filters", t3)

    def t4():
        c = SupabaseClient(url="https://x.supabase.co", service_key="sk")
        with patch("requests.post", return_value=mr(201, [{"id": 1}])):
            ok, r = c.insert("leads", {"email": "j@t.com"})
            assert ok
    test("Insert", t4)

    def t5():
        c = SupabaseClient(url="https://x.supabase.co", service_key="sk")
        with patch("requests.patch", return_value=mr(200, [{"id": 1}])):
            ok, _ = c.update("leads", {"status": "contacted"}, {"id": "eq.1"})
            assert ok
    test("Update", t5)

    def t6():
        c = SupabaseClient(url="https://x.supabase.co", service_key="sk")
        with patch("requests.delete", return_value=mr(200, [])):
            ok, _ = c.delete("leads", {"id": "eq.1"})
            assert ok
    test("Delete", t6)

    def t7():
        c = SupabaseClient(url="https://x.supabase.co", service_key="sk")
        with patch("requests.post", return_value=mr(200, {"result": 42})):
            ok, r = c.rpc("calculate_score", {"lead_id": 1})
            assert ok
    test("RPC function call", t7)

    def t8():
        c = SupabaseClient(url="https://x.supabase.co", service_key="sk")
        with patch("requests.post", return_value=mr(200, {"Key": "bucket/file.pdf"})):
            ok, r = c.upload_file("docs", "report.pdf", b"fake-pdf-bytes")
            assert ok
    test("Upload file", t8)

    def t9():
        c = SupabaseClient(url="https://x.supabase.co")
        url = c.get_public_url("docs", "report.pdf")
        assert "storage/v1/object/public/docs/report.pdf" in url
    test("Public URL", t9)

    def t10():
        c = SupabaseClient(url="https://x.supabase.co", service_key="sk")
        with patch("requests.post", return_value=mr(200, [{"name": "file.pdf"}])):
            ok, files = c.list_files("docs")
            assert ok
    test("List files", t10)

    def t11():
        c = SupabaseClient(url="https://x.supabase.co", anon_key="k")
        with patch("requests.get", return_value=mr(200, [{"id": 1}])) as mg:
            c.select("leads", order="created_at.desc", limit=10, offset=20)
            params = mg.call_args[1]["params"]
            assert params["order"] == "created_at.desc"
            assert params["limit"] == 10
    test("Select with order/limit/offset", t11)

    def t12():
        c = SupabaseClient(url="https://x.supabase.co", service_key="sk")
        with patch("requests.post", return_value=mr(201, [{"id": 1}, {"id": 2}])):
            ok, r = c.insert("leads", [{"email": "a@b.com"}, {"email": "c@d.com"}])
            assert ok
    test("Batch insert", t12)

    def t13():
        c = SupabaseClient(url="https://x.supabase.co", anon_key="k")
        with patch("requests.get", return_value=mr(401, {"message": "bad key"})):
            ok, _ = c.health(); assert not ok
    test("HTTP error", t13)

    def t14():
        c = SupabaseClient(url="https://x.supabase.co", anon_key="k")
        with patch("requests.get", side_effect=requests.ConnectionError):
            ok, _ = c.health(); assert not ok
    test("Connection error", t14)

    def t15():
        c = SupabaseClient(url="https://x.supabase.co", anon_key="k")
        with patch("requests.get", return_value=mr(200)): c.health()
        assert ACTION_LOG.exists()
    test("Action log", t15)

    print(f"\n  {'=' * 50}")
    print(f"  Supabase Bridge: {'PASS' if passed == total else 'FAIL'}")
    print(f"  Passed: {passed}/{total}")
    print(f"  {'=' * 50}")
    return passed == total

if __name__ == "__main__":
    if "--test" in sys.argv: sys.exit(0 if _run_tests() else 1)
    elif "--health" in sys.argv:
        c = SupabaseClient(); ok, r = c.health()
        print(f"{'✅' if ok else '❌'} Supabase: {r if not ok else 'connected'}")
    else: print("Usage: python3 scripts/supabase_bridge.py --test|--health")
