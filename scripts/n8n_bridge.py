#!/usr/bin/env python3
"""
NemoClaw ↔ n8n Bridge
Trigger workflows, manage executions, create webhooks.

    python3 scripts/n8n_bridge.py --test
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
ACTION_LOG = LOG_DIR / "n8n-actions.jsonl"


class N8nClient:
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        self.base_url = (base_url or os.environ.get("N8N_BASE_URL", "http://localhost:5678")).rstrip("/")
        self.api_key = api_key or os.environ.get("N8N_API_KEY", "")
        self.timeout = 30
        LOG_DIR.mkdir(parents=True, exist_ok=True)

    def _headers(self):
        return {"X-N8N-API-KEY": self.api_key, "Content-Type": "application/json"}

    def _log(self, action, params, success, error=None):
        entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "service": "n8n", "action": action, "params": params, "success": success}
        if error: entry["error"] = str(error)[:200]
        try:
            with open(ACTION_LOG, "a") as f: f.write(json.dumps(entry) + "\n")
        except Exception: pass

    def _get(self, path, params=None):
        try:
            r = requests.get(f"{self.base_url}/api/v1{path}", headers=self._headers(), params=params, timeout=self.timeout)
            if r.status_code >= 400: return (False, f"HTTP {r.status_code}: {r.text[:300]}")
            return (True, r.json())
        except requests.ConnectionError: return (False, "n8n not reachable")
        except requests.Timeout: return (False, "Timed out")
        except Exception as e: return (False, str(e))

    def _post(self, path, data=None):
        try:
            r = requests.post(f"{self.base_url}/api/v1{path}", headers=self._headers(), json=data or {}, timeout=self.timeout)
            if r.status_code >= 400: return (False, f"HTTP {r.status_code}: {r.text[:300]}")
            return (True, r.json())
        except requests.ConnectionError: return (False, "n8n not reachable")
        except requests.Timeout: return (False, "Timed out")
        except Exception as e: return (False, str(e))

    def health(self):
        try:
            r = requests.get(f"{self.base_url}/healthz", timeout=10)
            ok = r.status_code == 200
            self._log("health", {}, ok)
            return (ok, {"status": "healthy" if ok else r.status_code})
        except Exception as e:
            self._log("health", {}, False, str(e)); return (False, str(e))

    def list_workflows(self, active=None):
        params = {"active": str(active).lower()} if active is not None else None
        ok, r = self._get("/workflows", params); self._log("list_workflows", {}, ok); return (ok, r)

    def get_workflow(self, workflow_id):
        ok, r = self._get(f"/workflows/{workflow_id}"); self._log("get_workflow", {"id": workflow_id}, ok); return (ok, r)

    def activate_workflow(self, workflow_id):
        ok, r = self._post(f"/workflows/{workflow_id}/activate"); self._log("activate", {"id": workflow_id}, ok); return (ok, r)

    def deactivate_workflow(self, workflow_id):
        ok, r = self._post(f"/workflows/{workflow_id}/deactivate"); self._log("deactivate", {"id": workflow_id}, ok); return (ok, r)

    def execute_workflow(self, workflow_id, data=None):
        """Execute a workflow with optional input data. Returns (ok, execution)."""
        ok, r = self._post(f"/workflows/{workflow_id}/run", data or {})
        self._log("execute", {"id": workflow_id}, ok); return (ok, r)

    def list_executions(self, workflow_id=None, status=None, limit=20):
        params = {"limit": limit}
        if workflow_id: params["workflowId"] = workflow_id
        if status: params["status"] = status
        ok, r = self._get("/executions", params); self._log("list_executions", params, ok); return (ok, r)

    def get_execution(self, execution_id):
        ok, r = self._get(f"/executions/{execution_id}"); self._log("get_execution", {"id": execution_id}, ok); return (ok, r)

    def trigger_webhook(self, webhook_path, data=None, method="POST"):
        """Trigger a webhook-triggered workflow. Returns (ok, result)."""
        try:
            url = f"{self.base_url}/webhook/{webhook_path}"
            if method.upper() == "GET":
                r = requests.get(url, params=data, timeout=self.timeout)
            else:
                r = requests.post(url, json=data or {}, timeout=self.timeout)
            if r.status_code >= 400: return (False, f"HTTP {r.status_code}: {r.text[:300]}")
            try: return (True, r.json())
            except: return (True, {"status": r.status_code, "text": r.text[:200]})
        except Exception as e: return (False, str(e))

    def list_credentials(self):
        ok, r = self._get("/credentials"); self._log("list_credentials", {}, ok); return (ok, r)


def _run_tests():
    from unittest.mock import patch, MagicMock
    passed = total = 0
    def test(name, fn):
        nonlocal passed, total; total += 1
        try: fn(); passed += 1; print(f"  ✅ {name}")
        except Exception as e: print(f"  ❌ {name}: {e}")

    print("=" * 60); print("  n8n Bridge Tests"); print("=" * 60)

    def mr(s=200, d=None):
        r = MagicMock(); r.status_code = s; r.json.return_value = d or {}; r.text = json.dumps(d) if d else ""; return r

    def t1(): c = N8nClient(base_url="http://localhost:5678", api_key="k"); assert c.base_url == "http://localhost:5678"
    test("Constructor", t1)

    def t2():
        c = N8nClient(api_key="k")
        with patch("requests.get", return_value=mr(200)): ok, _ = c.health(); assert ok
    test("Health", t2)

    def t3():
        c = N8nClient(api_key="k")
        with patch("requests.get", return_value=mr(200, {"data": []})): ok, _ = c.list_workflows(); assert ok
    test("List workflows", t3)

    def t4():
        c = N8nClient(api_key="k")
        with patch("requests.get", return_value=mr(200, {"id": "w1"})): ok, _ = c.get_workflow("w1"); assert ok
    test("Get workflow", t4)

    def t5():
        c = N8nClient(api_key="k")
        with patch("requests.post", return_value=mr(200, {"active": True})): ok, _ = c.activate_workflow("w1"); assert ok
    test("Activate workflow", t5)

    def t6():
        c = N8nClient(api_key="k")
        with patch("requests.post", return_value=mr(200, {"active": False})): ok, _ = c.deactivate_workflow("w1"); assert ok
    test("Deactivate workflow", t6)

    def t7():
        c = N8nClient(api_key="k")
        with patch("requests.post", return_value=mr(200, {"id": "e1", "finished": True})) as mp:
            ok, r = c.execute_workflow("w1", {"input": "test"})
            assert ok
    test("Execute workflow", t7)

    def t8():
        c = N8nClient(api_key="k")
        with patch("requests.get", return_value=mr(200, {"data": []})): ok, _ = c.list_executions(workflow_id="w1", status="success"); assert ok
    test("List executions", t8)

    def t9():
        c = N8nClient(api_key="k")
        with patch("requests.get", return_value=mr(200, {"id": "e1"})): ok, _ = c.get_execution("e1"); assert ok
    test("Get execution", t9)

    def t10():
        c = N8nClient(api_key="k")
        with patch("requests.post", return_value=mr(200, {"success": True})): ok, _ = c.trigger_webhook("nemoclaw-hook", {"event": "test"}); assert ok
    test("Trigger webhook", t10)

    def t11():
        c = N8nClient(api_key="k")
        with patch("requests.get", return_value=mr(200, {"data": []})): ok, _ = c.list_credentials(); assert ok
    test("List credentials", t11)

    def t12():
        c = N8nClient(api_key="k")
        with patch("requests.get", side_effect=requests.ConnectionError): ok, _ = c.health(); assert not ok
    test("Connection error", t12)

    def t13():
        c = N8nClient(api_key="k")
        with patch("requests.get", return_value=mr(200, {})): c.health()
        assert ACTION_LOG.exists()
    test("Action log", t13)

    print(f"\n  {'=' * 50}"); print(f"  n8n Bridge: {'PASS' if passed == total else 'FAIL'}"); print(f"  Passed: {passed}/{total}"); print(f"  {'=' * 50}")
    return passed == total

if __name__ == "__main__":
    if "--test" in sys.argv: sys.exit(0 if _run_tests() else 1)
    elif "--health" in sys.argv:
        c = N8nClient(); ok, r = c.health(); print(f"{'✅' if ok else '❌'} n8n: {r if not ok else 'connected'}")
    else: print("Usage: python3 scripts/n8n_bridge.py --test|--health")
