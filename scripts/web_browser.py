#!/usr/bin/env python3
"""
NemoClaw ↔ PinchTab Bridge (web_browser.py)
Wraps PinchTab's HTTP API for use by any NemoClaw skill or agent.

All browser actions go through this bridge — never raw HTTP from skills.
Follows NemoClaw patterns: tuple returns, structured logging, rate limiting.

Usage:
    from web_browser import PinchTabClient
    browser = PinchTabClient()
    ok, result = browser.navigate("https://example.com")
"""

import json
import os
import sys
import time
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Any

try:
    import requests
except ImportError:
    print("ERROR: requests library required. Install: pip install requests --break-system-packages")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_BASE_URL = "http://localhost:9867"
DEFAULT_TIMEOUT = 30
LOG_DIR = Path.home() / ".nemoclaw" / "browser"
ACTION_LOG_FILE = LOG_DIR / "action-log.jsonl"
REPO = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

def _load_config() -> dict:
    """Load pinchtab-config.yaml if it exists."""
    config_path = REPO / "config" / "pinchtab-config.yaml"
    if config_path.exists():
        try:
            import yaml
            with open(config_path) as f:
                return yaml.safe_load(f).get("pinchtab", {})
        except Exception:
            pass
    return {}


# ---------------------------------------------------------------------------
# PinchTabClient
# ---------------------------------------------------------------------------

class PinchTabClient:
    """NemoClaw ↔ PinchTab bridge. Any skill can use this to control Chrome."""

    def __init__(self, base_url: Optional[str] = None, agent_id: Optional[str] = None):
        config = _load_config()
        self.base_url = (base_url or config.get("server_url", DEFAULT_BASE_URL)).rstrip("/")
        self.agent_id = agent_id
        self.timeout = DEFAULT_TIMEOUT

        # Rate limiting
        rate_limits = config.get("rate_limits", {})
        self.max_navigations_per_hour = rate_limits.get("navigations_per_hour", 100)
        self.max_clicks_per_task = rate_limits.get("clicks_per_task", 50)
        self.max_text_extractions_per_hour = rate_limits.get("text_extractions_per_hour", 200)
        self.max_screenshots_per_hour = rate_limits.get("screenshots_per_hour", 50)

        # Counters (reset hourly)
        self._nav_count = 0
        self._text_count = 0
        self._screenshot_count = 0
        self._click_count = 0
        self._hour_start = time.time()

        # Safety config
        safety = config.get("safety", {})
        self.blocked_domains = safety.get("blocked_domains", [])
        self.require_screenshot_before_submit = safety.get("require_screenshot_before_submit", True)
        self.max_eval_js_per_task = safety.get("max_eval_js_per_task", 5)
        self._eval_count = 0

        # Auth token from PinchTab config
        self._token = None
        try:
            import json as _json
            pt_config = Path.home() / ".pinchtab" / "config.json"
            if pt_config.exists():
                self._token = _json.load(open(pt_config)).get("server", {}).get("token", "")
        except Exception:
            pass

        # Ensure log directory
        LOG_DIR.mkdir(parents=True, exist_ok=True)

        self.logger = logging.getLogger("pinchtab_bridge")

    # -------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------

    def _reset_counters_if_needed(self):
        """Reset hourly counters if an hour has passed."""
        now = time.time()
        if now - self._hour_start >= 3600:
            self._nav_count = 0
            self._text_count = 0
            self._screenshot_count = 0
            self._click_count = 0
            self._eval_count = 0
            self._hour_start = now

    def _log_action(self, action: str, params: dict, success: bool, result: Any = None, error: str = None):
        """Append action to JSONL log."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_id": self.agent_id,
            "action": action,
            "params": params,
            "success": success,
        }
        if error:
            entry["error"] = error
        if result and action in ("navigate", "text", "snapshot"):
            # Log lightweight summary, not full content
            if isinstance(result, dict):
                entry["result_summary"] = {k: v for k, v in result.items()
                                           if k in ("url", "title", "count", "truncated", "tabId")}
        try:
            with open(ACTION_LOG_FILE, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass  # Never crash on logging failure

    def _headers(self) -> dict:
        """Auth headers for PinchTab API."""
        h = {}
        if self._token:
            h["Authorization"] = f"Bearer {self._token}"
        return h

    def _get(self, path: str, params: dict = None) -> tuple:
        """HTTP GET, returns (success: bool, data_or_error)."""
        try:
            r = requests.get(f"{self.base_url}{path}", params=params, headers=self._headers(), timeout=self.timeout)
            if r.status_code >= 400:
                return (False, f"HTTP {r.status_code}: {r.text[:500]}")
            return (True, r.json())
        except requests.ConnectionError:
            return (False, "PinchTab server not reachable")
        except requests.Timeout:
            return (False, "Request timed out")
        except Exception as e:
            return (False, str(e))

    def _post(self, path: str, data: dict = None) -> tuple:
        """HTTP POST, returns (success: bool, data_or_error)."""
        try:
            r = requests.post(
                f"{self.base_url}{path}",
                json=data or {},
                headers={**self._headers(), "Content-Type": "application/json"},
                timeout=self.timeout,
            )
            if r.status_code >= 400:
                return (False, f"HTTP {r.status_code}: {r.text[:500]}")
            return (True, r.json())
        except requests.ConnectionError:
            return (False, "PinchTab server not reachable")
        except requests.Timeout:
            return (False, "Request timed out")
        except Exception as e:
            return (False, str(e))

    def _get_binary(self, path: str, params: dict = None) -> tuple:
        """HTTP GET returning binary content, returns (success, bytes_or_error)."""
        try:
            r = requests.get(f"{self.base_url}{path}", params=params, headers=self._headers(), timeout=self.timeout)
            if r.status_code >= 400:
                return (False, f"HTTP {r.status_code}: {r.text[:500]}")
            return (True, r.content)
        except requests.ConnectionError:
            return (False, "PinchTab server not reachable")
        except requests.Timeout:
            return (False, "Request timed out")
        except Exception as e:
            return (False, str(e))

    def _check_domain(self, url: str) -> tuple:
        """Check if URL domain is blocked. Returns (allowed: bool, error_or_none)."""
        if not self.blocked_domains:
            return (True, None)
        try:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc.lower()
            for pattern in self.blocked_domains:
                p = pattern.replace("*.", "").replace(".*", "")
                if p in domain:
                    return (False, f"Domain blocked by safety config: {domain} matches {pattern}")
        except Exception:
            pass
        return (True, None)

    # -------------------------------------------------------------------
    # Health
    # -------------------------------------------------------------------

    def health(self) -> tuple:
        """Check PinchTab server health. Returns (is_healthy: bool, data_or_error)."""
        ok, result = self._get("/health")
        self._log_action("health", {}, ok, result, result if not ok else None)
        return (ok, result)

    def is_running(self) -> bool:
        """Quick check if PinchTab is reachable."""
        ok, _ = self.health()
        return ok

    # -------------------------------------------------------------------
    # Navigation
    # -------------------------------------------------------------------

    def navigate(self, url: str, tab_id: str = None, new_tab: bool = False,
                 block_images: bool = False, wait_for: int = None) -> tuple:
        """Navigate to URL. Returns (success, {tabId, title, url})."""
        self._reset_counters_if_needed()

        # Rate limit check
        if self._nav_count >= self.max_navigations_per_hour:
            err = f"Rate limit exceeded: {self.max_navigations_per_hour} navigations/hour"
            self._log_action("navigate", {"url": url}, False, error=err)
            return (False, err)

        # Domain safety check
        allowed, err = self._check_domain(url)
        if not allowed:
            self._log_action("navigate", {"url": url}, False, error=err)
            return (False, err)

        body = {"url": url}
        if tab_id:
            body["tabId"] = tab_id
        if new_tab:
            body["newTab"] = True
        if block_images:
            body["blockImages"] = True
        if wait_for:
            body["waitFor"] = wait_for

        ok, result = self._post("/navigate", body)
        if ok:
            self._nav_count += 1
        self._log_action("navigate", {"url": url}, ok, result, result if not ok else None)
        return (ok, result)

    # -------------------------------------------------------------------
    # Content extraction
    # -------------------------------------------------------------------

    def snapshot(self, interactive: bool = True, max_tokens: int = None) -> tuple:
        """Get accessibility snapshot. Returns (success, {nodes: [{ref, role, name}], count})."""
        params = {}
        if interactive:
            params["filter"] = "interactive"
        if max_tokens:
            params["maxTokens"] = max_tokens

        ok, result = self._get("/snapshot", params)
        self._log_action("snapshot", params, ok, result, result if not ok else None)
        return (ok, result)

    def text(self, raw: bool = False, max_chars: int = None) -> tuple:
        """Extract page text. Returns (success, {text, title, url, truncated})."""
        self._reset_counters_if_needed()

        if self._text_count >= self.max_text_extractions_per_hour:
            err = f"Rate limit exceeded: {self.max_text_extractions_per_hour} text extractions/hour"
            self._log_action("text", {}, False, error=err)
            return (False, err)

        params = {}
        if raw:
            params["mode"] = "raw"
        if max_chars:
            params["maxChars"] = max_chars

        ok, result = self._get("/text", params)
        if ok:
            self._text_count += 1
        self._log_action("text", params, ok, result, result if not ok else None)
        return (ok, result)

    # -------------------------------------------------------------------
    # Actions (click, fill, press, scroll, hover, focus, select, type)
    # -------------------------------------------------------------------

    def _action(self, kind: str, ref: str = None, extra: dict = None) -> tuple:
        """Generic action dispatch via POST /action."""
        body = {"kind": kind}
        if ref:
            body["ref"] = ref
        if extra:
            body.update(extra)

        ok, result = self._post("/action", body)
        self._log_action(kind, {"ref": ref, **(extra or {})}, ok, result, result if not ok else None)
        return (ok, result)

    def click(self, ref: str) -> tuple:
        """Click element by ref. Returns (success, result)."""
        self._reset_counters_if_needed()

        if self._click_count >= self.max_clicks_per_task:
            err = f"Rate limit exceeded: {self.max_clicks_per_task} clicks/task"
            self._log_action("click", {"ref": ref}, False, error=err)
            return (False, err)

        ok, result = self._action("click", ref)
        if ok:
            self._click_count += 1
        return (ok, result)

    def fill(self, ref: str, value: str) -> tuple:
        """Fill input field by ref. Returns (success, result)."""
        return self._action("fill", ref, {"value": value})

    def press(self, key: str, ref: str = None) -> tuple:
        """Press key, optionally on a specific element. Returns (success, result)."""
        return self._action("press", ref, {"key": key})

    def type_text(self, ref: str, text: str) -> tuple:
        """Type text into element (with keystroke timing). Returns (success, result)."""
        return self._action("type", ref, {"text": text})

    def scroll(self, direction: str = "down") -> tuple:
        """Scroll page. Direction: up, down, left, right. Returns (success, result)."""
        return self._action("scroll", extra={"direction": direction})

    def hover(self, ref: str) -> tuple:
        """Hover over element. Returns (success, result)."""
        return self._action("hover", ref)

    def focus(self, ref: str) -> tuple:
        """Focus element. Returns (success, result)."""
        return self._action("focus", ref)

    def select(self, ref: str, value: str) -> tuple:
        """Select option in dropdown. Returns (success, result)."""
        return self._action("select", ref, {"value": value})

    # -------------------------------------------------------------------
    # Find
    # -------------------------------------------------------------------

    def find(self, query: str) -> tuple:
        """Find elements by text or selector. Returns (success, {best_ref, matches, confidence})."""
        ok, result = self._post("/find", {"query": query})
        self._log_action("find", {"query": query}, ok, result, result if not ok else None)
        return (ok, result)

    # -------------------------------------------------------------------
    # Screenshots and PDF
    # -------------------------------------------------------------------

    def screenshot(self, save_path: str = None) -> tuple:
        """Take screenshot. Returns (success, filepath_or_bytes_or_error)."""
        self._reset_counters_if_needed()

        if self._screenshot_count >= self.max_screenshots_per_hour:
            err = f"Rate limit exceeded: {self.max_screenshots_per_hour} screenshots/hour"
            self._log_action("screenshot", {}, False, error=err)
            return (False, err)

        ok, result = self._get_binary("/screenshot")
        if ok and save_path:
            try:
                Path(save_path).parent.mkdir(parents=True, exist_ok=True)
                with open(save_path, "wb") as f:
                    f.write(result)
                self._screenshot_count += 1
                self._log_action("screenshot", {"path": save_path}, True)
                return (True, save_path)
            except Exception as e:
                self._log_action("screenshot", {"path": save_path}, False, error=str(e))
                return (False, str(e))
        elif ok:
            self._screenshot_count += 1
            self._log_action("screenshot", {}, True)
            return (True, result)
        else:
            self._log_action("screenshot", {}, False, error=result)
            return (False, result)

    def pdf(self, save_path: str = None) -> tuple:
        """Export page as PDF. Returns (success, filepath_or_bytes_or_error)."""
        ok, result = self._get_binary("/pdf")
        if ok and save_path:
            try:
                Path(save_path).parent.mkdir(parents=True, exist_ok=True)
                with open(save_path, "wb") as f:
                    f.write(result)
                self._log_action("pdf", {"path": save_path}, True)
                return (True, save_path)
            except Exception as e:
                self._log_action("pdf", {"path": save_path}, False, error=str(e))
                return (False, str(e))
        elif ok:
            self._log_action("pdf", {}, True)
            return (True, result)
        else:
            self._log_action("pdf", {}, False, error=result)
            return (False, result)

    # -------------------------------------------------------------------
    # JavaScript evaluation
    # -------------------------------------------------------------------

    def eval_js(self, expression: str) -> tuple:
        """Execute JavaScript in current tab. Returns (success, result)."""
        if self._eval_count >= self.max_eval_js_per_task:
            err = f"Rate limit exceeded: {self.max_eval_js_per_task} eval_js/task"
            self._log_action("eval_js", {}, False, error=err)
            return (False, err)

        ok, result = self._post("/evaluate", {"expression": expression})
        if ok:
            self._eval_count += 1
        self._log_action("eval_js", {"expression": expression[:100]}, ok, result, result if not ok else None)
        return (ok, result)

    # -------------------------------------------------------------------
    # Instance management
    # -------------------------------------------------------------------

    def start_instance(self, profile_id: str = None, headless: bool = True, port: str = None) -> tuple:
        """Start a Chrome instance. Returns (success, instance_object)."""
        body = {"mode": "headless" if headless else "headed"}
        if profile_id:
            body["profileId"] = profile_id
        if port:
            body["port"] = port

        ok, result = self._post("/instances/start", body)
        self._log_action("start_instance", body, ok, result, result if not ok else None)
        return (ok, result)

    def stop_instance(self, instance_id: str) -> tuple:
        """Stop a Chrome instance. Returns (success, result)."""
        ok, result = self._post(f"/instances/{instance_id}/stop")
        self._log_action("stop_instance", {"instance_id": instance_id}, ok, result, result if not ok else None)
        return (ok, result)

    def list_instances(self) -> tuple:
        """List all running instances. Returns (success, [instance])."""
        ok, result = self._get("/instances")
        self._log_action("list_instances", {}, ok, result, result if not ok else None)
        return (ok, result)

    def instance_metrics(self) -> tuple:
        """Get per-instance memory metrics. Returns (success, metrics)."""
        return self._get("/instances/metrics")

    # -------------------------------------------------------------------
    # Tab management
    # -------------------------------------------------------------------

    def list_tabs(self, instance_id: str = None) -> tuple:
        """List tabs. Returns (success, [tab])."""
        if instance_id:
            return self._get(f"/instances/{instance_id}/tabs")
        return self._get("/tabs")

    # -------------------------------------------------------------------
    # Scheduler / task queue
    # -------------------------------------------------------------------

    def schedule_task(self, action: str, tab_id: str, ref: str = None,
                      params: dict = None, priority: int = 5) -> tuple:
        """Submit task to scheduler. Returns (success, {taskId, state, position})."""
        body = {
            "agentId": self.agent_id or "nemoclaw-default",
            "action": action,
            "tabId": tab_id,
            "priority": priority,
        }
        if ref:
            body["ref"] = ref
        if params:
            body["params"] = params

        ok, result = self._post("/tasks", body)
        self._log_action("schedule_task", body, ok, result, result if not ok else None)
        return (ok, result)

    def get_task_result(self, task_id: str) -> tuple:
        """Get task result. Returns (success, task_object)."""
        return self._get(f"/tasks/{task_id}")

    def list_tasks(self, agent_id: str = None, state: str = None) -> tuple:
        """List tasks. Returns (success, {tasks, count})."""
        params = {}
        if agent_id:
            params["agentId"] = agent_id
        if state:
            params["state"] = state
        return self._get("/tasks", params)

    # -------------------------------------------------------------------
    # Convenience / composite methods
    # -------------------------------------------------------------------

    def navigate_and_extract(self, url: str, raw: bool = False) -> tuple:
        """Navigate to URL and extract text in one call. Returns (success, {url, title, text})."""
        ok, nav_result = self.navigate(url)
        if not ok:
            return (False, nav_result)

        # Brief pause for page load
        time.sleep(1)

        ok, text_result = self.text(raw=raw)
        if not ok:
            return (False, text_result)

        return (True, {
            "url": nav_result.get("url", url),
            "title": text_result.get("title", ""),
            "text": text_result.get("text", ""),
        })

    def reset_task_counters(self):
        """Reset per-task counters (clicks, eval_js). Call at start of each skill run."""
        self._click_count = 0
        self._eval_count = 0

    def restart_default_instance(self, headless: bool = True) -> tuple:
        """Stop the default instance (if any) and start a fresh one.
        Useful for recovering from stale/crashed Chrome contexts.
        Returns (success, new_instance_object)."""
        # Find and stop current default instance
        ok, instances = self.list_instances()
        if ok and isinstance(instances, list):
            for inst in instances:
                if inst.get("status") == "running":
                    self.stop_instance(inst["id"])
                    time.sleep(1)

        # Start fresh
        ok, result = self.start_instance(headless=headless)
        if ok:
            # Wait for instance to be ready
            time.sleep(3)
            self._log_action("restart_default_instance", {"headless": headless}, True, result)
        else:
            self._log_action("restart_default_instance", {"headless": headless}, False, error=result)
        return (ok, result)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def _run_tests():
    """Run 30+ tests with mocked HTTP when PinchTab is not running."""
    from unittest.mock import patch, MagicMock
    import tempfile

    passed = 0
    failed = 0
    total = 0

    def test(name, fn):
        nonlocal passed, failed, total
        total += 1
        try:
            fn()
            passed += 1
            print(f"  ✅ {name}")
        except Exception as e:
            failed += 1
            print(f"  ❌ {name}: {e}")

    print("=" * 60)
    print("  PinchTab Bridge Tests")
    print("=" * 60)

    # --- Mock setup ---
    def mock_response(status=200, json_data=None, content=b""):
        resp = MagicMock()
        resp.status_code = status
        resp.json.return_value = json_data or {}
        resp.text = json.dumps(json_data) if json_data else ""
        resp.content = content
        return resp

    # --- Test 1: Constructor defaults ---
    def test_constructor_defaults():
        client = PinchTabClient()
        assert client.base_url == DEFAULT_BASE_URL
        assert client.agent_id is None
        assert client.max_navigations_per_hour == 100
    test("Constructor defaults", test_constructor_defaults)

    # --- Test 2: Constructor with custom params ---
    def test_constructor_custom():
        client = PinchTabClient(base_url="http://custom:1234", agent_id="test-agent")
        assert client.base_url == "http://custom:1234"
        assert client.agent_id == "test-agent"
    test("Constructor custom params", test_constructor_custom)

    # --- Test 3: Health success ---
    def test_health_success():
        client = PinchTabClient()
        with patch("requests.get", return_value=mock_response(200, {"status": "ok", "tabs": 1})):
            ok, result = client.health()
            assert ok is True
            assert result["status"] == "ok"
    test("Health success", test_health_success)

    # --- Test 4: Health failure (server down) ---
    def test_health_failure():
        client = PinchTabClient()
        with patch("requests.get", side_effect=requests.ConnectionError):
            ok, result = client.health()
            assert ok is False
            assert "not reachable" in result
    test("Health failure (server down)", test_health_failure)

    # --- Test 5: is_running ---
    def test_is_running():
        client = PinchTabClient()
        with patch("requests.get", return_value=mock_response(200, {"status": "ok", "tabs": 0})):
            assert client.is_running() is True
        with patch("requests.get", side_effect=requests.ConnectionError):
            assert client.is_running() is False
    test("is_running", test_is_running)

    # --- Test 6: Navigate success ---
    def test_navigate_success():
        client = PinchTabClient()
        nav_resp = {"tabId": "abc123", "url": "https://example.com", "title": "Example"}
        with patch("requests.post", return_value=mock_response(200, nav_resp)):
            ok, result = client.navigate("https://example.com")
            assert ok is True
            assert result["tabId"] == "abc123"
    test("Navigate success", test_navigate_success)

    # --- Test 7: Navigate with options ---
    def test_navigate_options():
        client = PinchTabClient()
        with patch("requests.post", return_value=mock_response(200, {"tabId": "t1"})) as mock_post:
            client.navigate("https://test.com", new_tab=True, block_images=True)
            call_body = mock_post.call_args[1]["json"]
            assert call_body["newTab"] is True
            assert call_body["blockImages"] is True
    test("Navigate with options", test_navigate_options)

    # --- Test 8: Navigate blocked domain ---
    def test_navigate_blocked_domain():
        client = PinchTabClient()
        client.blocked_domains = ["*.bank.*"]
        ok, result = client.navigate("https://www.bank.com/login")
        assert ok is False
        assert "blocked" in result.lower()
    test("Navigate blocked domain", test_navigate_blocked_domain)

    # --- Test 9: Navigate rate limit ---
    def test_navigate_rate_limit():
        client = PinchTabClient()
        client.max_navigations_per_hour = 2
        client._nav_count = 2
        ok, result = client.navigate("https://example.com")
        assert ok is False
        assert "rate limit" in result.lower()
    test("Navigate rate limit", test_navigate_rate_limit)

    # --- Test 10: Snapshot success ---
    def test_snapshot_success():
        client = PinchTabClient()
        snap_resp = {"nodes": [{"ref": "e0", "role": "link", "name": "Docs"}], "count": 1}
        with patch("requests.get", return_value=mock_response(200, snap_resp)):
            ok, result = client.snapshot()
            assert ok is True
            assert len(result["nodes"]) == 1
            assert result["nodes"][0]["ref"] == "e0"
    test("Snapshot success", test_snapshot_success)

    # --- Test 11: Snapshot with filter ---
    def test_snapshot_filter():
        client = PinchTabClient()
        with patch("requests.get", return_value=mock_response(200, {"nodes": [], "count": 0})) as mock_get:
            client.snapshot(interactive=True, max_tokens=500)
            call_params = mock_get.call_args[1]["params"]
            assert call_params["filter"] == "interactive"
            assert call_params["maxTokens"] == 500
    test("Snapshot with filter params", test_snapshot_filter)

    # --- Test 12: Text extraction ---
    def test_text_extraction():
        client = PinchTabClient()
        text_resp = {"text": "Hello world", "title": "Test", "url": "https://test.com", "truncated": False}
        with patch("requests.get", return_value=mock_response(200, text_resp)):
            ok, result = client.text()
            assert ok is True
            assert result["text"] == "Hello world"
    test("Text extraction", test_text_extraction)

    # --- Test 13: Text rate limit ---
    def test_text_rate_limit():
        client = PinchTabClient()
        client.max_text_extractions_per_hour = 1
        client._text_count = 1
        ok, result = client.text()
        assert ok is False
        assert "rate limit" in result.lower()
    test("Text rate limit", test_text_rate_limit)

    # --- Test 14: Click success ---
    def test_click_success():
        client = PinchTabClient()
        click_resp = {"success": True, "result": {"success": True}}
        with patch("requests.post", return_value=mock_response(200, click_resp)):
            ok, result = client.click("e5")
            assert ok is True
    test("Click success", test_click_success)

    # --- Test 15: Click rate limit ---
    def test_click_rate_limit():
        client = PinchTabClient()
        client.max_clicks_per_task = 3
        client._click_count = 3
        ok, result = client.click("e0")
        assert ok is False
        assert "rate limit" in result.lower()
    test("Click rate limit", test_click_rate_limit)

    # --- Test 16: Fill ---
    def test_fill():
        client = PinchTabClient()
        with patch("requests.post", return_value=mock_response(200, {"success": True})) as mock_post:
            ok, result = client.fill("e3", "user@test.com")
            call_body = mock_post.call_args[1]["json"]
            assert call_body["kind"] == "fill"
            assert call_body["ref"] == "e3"
            assert call_body["value"] == "user@test.com"
    test("Fill", test_fill)

    # --- Test 17: Press ---
    def test_press():
        client = PinchTabClient()
        with patch("requests.post", return_value=mock_response(200, {"success": True})) as mock_post:
            ok, result = client.press("Enter", ref="e7")
            call_body = mock_post.call_args[1]["json"]
            assert call_body["kind"] == "press"
            assert call_body["key"] == "Enter"
            assert call_body["ref"] == "e7"
    test("Press", test_press)

    # --- Test 18: Type text ---
    def test_type_text():
        client = PinchTabClient()
        with patch("requests.post", return_value=mock_response(200, {"success": True})) as mock_post:
            client.type_text("e4", "Hello")
            call_body = mock_post.call_args[1]["json"]
            assert call_body["kind"] == "type"
            assert call_body["text"] == "Hello"
    test("Type text", test_type_text)

    # --- Test 19: Scroll ---
    def test_scroll():
        client = PinchTabClient()
        with patch("requests.post", return_value=mock_response(200, {"success": True})) as mock_post:
            client.scroll("up")
            call_body = mock_post.call_args[1]["json"]
            assert call_body["kind"] == "scroll"
            assert call_body["direction"] == "up"
    test("Scroll", test_scroll)

    # --- Test 20: Hover ---
    def test_hover():
        client = PinchTabClient()
        with patch("requests.post", return_value=mock_response(200, {"success": True})):
            ok, _ = client.hover("e2")
            assert ok is True
    test("Hover", test_hover)

    # --- Test 21: Focus ---
    def test_focus():
        client = PinchTabClient()
        with patch("requests.post", return_value=mock_response(200, {"success": True})):
            ok, _ = client.focus("e1")
            assert ok is True
    test("Focus", test_focus)

    # --- Test 22: Select ---
    def test_select():
        client = PinchTabClient()
        with patch("requests.post", return_value=mock_response(200, {"success": True})) as mock_post:
            client.select("e6", "option2")
            call_body = mock_post.call_args[1]["json"]
            assert call_body["kind"] == "select"
            assert call_body["value"] == "option2"
    test("Select", test_select)

    # --- Test 23: Find ---
    def test_find():
        client = PinchTabClient()
        find_resp = {"best_ref": "e10", "matches": [{"ref": "e10", "role": "link", "name": "Contact"}], "confidence": "high"}
        with patch("requests.post", return_value=mock_response(200, find_resp)):
            ok, result = client.find("Contact")
            assert ok is True
            assert result["best_ref"] == "e10"
    test("Find", test_find)

    # --- Test 24: Screenshot to file ---
    def test_screenshot_to_file():
        client = PinchTabClient()
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp_path = tmp.name
        with patch("requests.get", return_value=mock_response(200, content=b"\xff\xd8\xff")):
            ok, result = client.screenshot(save_path=tmp_path)
            assert ok is True
            assert result == tmp_path
            assert os.path.exists(tmp_path)
        os.unlink(tmp_path)
    test("Screenshot to file", test_screenshot_to_file)

    # --- Test 25: Screenshot rate limit ---
    def test_screenshot_rate_limit():
        client = PinchTabClient()
        client.max_screenshots_per_hour = 1
        client._screenshot_count = 1
        ok, result = client.screenshot()
        assert ok is False
        assert "rate limit" in result.lower()
    test("Screenshot rate limit", test_screenshot_rate_limit)

    # --- Test 26: PDF ---
    def test_pdf():
        client = PinchTabClient()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name
        with patch("requests.get", return_value=mock_response(200, content=b"%PDF-1.4")):
            ok, result = client.pdf(save_path=tmp_path)
            assert ok is True
        os.unlink(tmp_path)
    test("PDF export", test_pdf)

    # --- Test 27: Eval JS (endpoint: /evaluate) ---
    def test_eval_js():
        client = PinchTabClient()
        with patch("requests.post", return_value=mock_response(200, {"result": "42"})) as mock_post:
            ok, result = client.eval_js("document.title")
            assert ok is True
            assert "/evaluate" in mock_post.call_args[0][0]
    test("Eval JS", test_eval_js)

    # --- Test 28: Eval JS rate limit ---
    def test_eval_js_rate_limit():
        client = PinchTabClient()
        client.max_eval_js_per_task = 2
        client._eval_count = 2
        ok, result = client.eval_js("1+1")
        assert ok is False
        assert "rate limit" in result.lower()
    test("Eval JS rate limit", test_eval_js_rate_limit)

    # --- Test 29: Start instance ---
    def test_start_instance():
        client = PinchTabClient()
        inst_resp = {"id": "inst_abc", "status": "starting", "port": "9868", "headless": True}
        with patch("requests.post", return_value=mock_response(200, inst_resp)):
            ok, result = client.start_instance(profile_id="test-profile")
            assert ok is True
            assert result["id"] == "inst_abc"
    test("Start instance", test_start_instance)

    # --- Test 30: Stop instance ---
    def test_stop_instance():
        client = PinchTabClient()
        with patch("requests.post", return_value=mock_response(200, {"id": "inst_abc", "status": "stopped"})):
            ok, result = client.stop_instance("inst_abc")
            assert ok is True
            assert result["status"] == "stopped"
    test("Stop instance", test_stop_instance)

    # --- Test 31: List instances ---
    def test_list_instances():
        client = PinchTabClient()
        with patch("requests.get", return_value=mock_response(200, [{"id": "inst_1"}, {"id": "inst_2"}])):
            ok, result = client.list_instances()
            assert ok is True
            assert len(result) == 2
    test("List instances", test_list_instances)

    # --- Test 32: List tabs ---
    def test_list_tabs():
        client = PinchTabClient()
        with patch("requests.get", return_value=mock_response(200, [{"id": "tab1", "url": "https://x.com"}])):
            ok, result = client.list_tabs()
            assert ok is True
    test("List tabs", test_list_tabs)

    # --- Test 33: Schedule task ---
    def test_schedule_task():
        client = PinchTabClient(agent_id="growth_revenue_lead")
        task_resp = {"taskId": "tsk_abc", "state": "queued", "position": 1}
        with patch("requests.post", return_value=mock_response(202, task_resp)) as mock_post:
            ok, result = client.schedule_task("click", "tab123", ref="e5", priority=3)
            call_body = mock_post.call_args[1]["json"]
            assert call_body["agentId"] == "growth_revenue_lead"
            assert call_body["priority"] == 3
    test("Schedule task", test_schedule_task)

    # --- Test 34: Get task result ---
    def test_get_task_result():
        client = PinchTabClient()
        with patch("requests.get", return_value=mock_response(200, {"taskId": "tsk_abc", "state": "done"})):
            ok, result = client.get_task_result("tsk_abc")
            assert ok is True
            assert result["state"] == "done"
    test("Get task result", test_get_task_result)

    # --- Test 35: Navigate and extract ---
    def test_navigate_and_extract():
        client = PinchTabClient()
        nav_resp = {"tabId": "t1", "url": "https://example.com", "title": "Example"}
        text_resp = {"text": "content here", "title": "Example", "url": "https://example.com", "truncated": False}
        with patch("requests.post", return_value=mock_response(200, nav_resp)):
            with patch("requests.get", return_value=mock_response(200, text_resp)):
                with patch("time.sleep"):
                    ok, result = client.navigate_and_extract("https://example.com")
                    assert ok is True
                    assert result["text"] == "content here"
    test("Navigate and extract (composite)", test_navigate_and_extract)

    # --- Test 36: Reset task counters ---
    def test_reset_task_counters():
        client = PinchTabClient()
        client._click_count = 50
        client._eval_count = 5
        client.reset_task_counters()
        assert client._click_count == 0
        assert client._eval_count == 0
    test("Reset task counters", test_reset_task_counters)

    # --- Test 37: HTTP error handling ---
    def test_http_error():
        client = PinchTabClient()
        with patch("requests.get", return_value=mock_response(503, {"error": "server error"})):
            ok, result = client.health()
            assert ok is False
            assert "503" in result
    test("HTTP error handling", test_http_error)

    # --- Test 38: Timeout handling ---
    def test_timeout():
        client = PinchTabClient()
        with patch("requests.get", side_effect=requests.Timeout):
            ok, result = client.health()
            assert ok is False
            assert "timed out" in result.lower()
    test("Timeout handling", test_timeout)

    # --- Test 39: Action log file created ---
    def test_action_log():
        client = PinchTabClient()
        with patch("requests.get", return_value=mock_response(200, {"status": "ok", "tabs": 0})):
            client.health()
        assert ACTION_LOG_FILE.exists()
    test("Action log file created", test_action_log)

    # --- Test 40: Hourly counter reset ---
    def test_hourly_reset():
        client = PinchTabClient()
        client._nav_count = 99
        client._hour_start = time.time() - 3601  # Over an hour ago
        client._reset_counters_if_needed()
        assert client._nav_count == 0
    test("Hourly counter reset", test_hourly_reset)

    print()
    print(f"  {'=' * 50}")
    print(f"  Bridge Tests: {'PASS' if failed == 0 else 'FAIL'}")
    print(f"  Passed: {passed}/{total}")
    if failed > 0:
        print(f"  Failed: {failed}/{total}")
    print(f"  {'=' * 50}")

    return failed == 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if "--test" in sys.argv:
        success = _run_tests()
        sys.exit(0 if success else 1)
    else:
        # Quick health check
        client = PinchTabClient()
        ok, result = client.health()
        if ok:
            print(f"✅ PinchTab is running: {result}")
        else:
            print(f"❌ PinchTab not reachable: {result}")
            print("   Start PinchTab with: pinchtab")
        sys.exit(0 if ok else 1)
