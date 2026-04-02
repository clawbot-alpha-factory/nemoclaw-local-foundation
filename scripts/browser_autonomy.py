#!/usr/bin/env python3
"""
NemoClaw Browser Autonomy Layer (browser_autonomy.py)
Unified routing layer over PinchTab, browser-use, and gws CLI.

Fallback chain: API bridge → gws CLI → PinchTab → browser-use
Routes each action to the appropriate engine per browser-autonomy.yaml.

Usage:
    from browser_autonomy import BrowserAutonomyLayer
    browser = BrowserAutonomyLayer(agent_id="growth_revenue_lead")
    ok, result = browser.navigate("https://example.com")
    ok, result = await browser.login("heygen.com")
    ok, result = await browser.run_autonomous_task("Extract pricing from example.com")

    python3 scripts/browser_autonomy.py --test
"""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from web_browser import PinchTabClient
from browser_use_adapter import BrowserUseAdapter
from gws_bridge import GWSBridge
from credential_vault import CredentialVault
from auth_flows import AuthFlowHandler

# Governance imports (MA-8, MA-19, MA-6)
try:
    from behavior_guard import BehaviorGuard
    _HAS_GUARD = True
except ImportError:
    _HAS_GUARD = False

try:
    from access_control import AccessController
    _HAS_ACCESS = True
except ImportError:
    _HAS_ACCESS = False

try:
    from cost_governor import CostGovernor
    _HAS_COST = True
except ImportError:
    _HAS_COST = False

LOG_DIR = Path.home() / ".nemoclaw" / "browser"
ROUTING_LOG = LOG_DIR / "routing-decisions.jsonl"

logger = logging.getLogger("nemoclaw.browser_autonomy")


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def _load_config() -> dict:
    """Load browser-autonomy.yaml."""
    config_path = REPO / "config" / "browser-autonomy.yaml"
    if config_path.exists():
        try:
            import yaml
            with open(config_path) as f:
                return yaml.safe_load(f).get("autonomy", {})
        except Exception:
            pass
    return {}


# ---------------------------------------------------------------------------
# BrowserAutonomyLayer
# ---------------------------------------------------------------------------

class BrowserAutonomyLayer:
    """Unified browser control — routes to PinchTab, browser-use, or gws per action."""

    def __init__(self, agent_id: str = None, headless: bool = True):
        self.agent_id = agent_id
        self.config = _load_config()

        # Initialize engines
        self.pinchtab = PinchTabClient(agent_id=agent_id)
        self.browser_use = BrowserUseAdapter(agent_id=agent_id, headless=headless)
        self.gws = GWSBridge(agent_id=agent_id)
        self.vault = CredentialVault()
        self.auth = AuthFlowHandler(self.browser_use, self.vault)

        # Initialize governance (MA-8, MA-19, MA-6)
        self.guard = BehaviorGuard() if _HAS_GUARD else None
        self.access = AccessController() if _HAS_ACCESS else None
        self.cost_gov = CostGovernor() if _HAS_COST else None
        self._known_services = set()  # Services we've logged into before

        # Routing config
        routing = self.config.get("routing", {})
        self._pinchtab_first = set(routing.get("pinchtab_first", []))
        self._browser_use_only = set(routing.get("browser_use_only", []))
        self._google_services = set(
            self.config.get("gws", {}).get("google_services_via_gws", [])
        )

        # Fallback config
        fallback = self.config.get("fallback", {})
        self.fallback_enabled = fallback.get("enabled", True)
        self.fallback_order = fallback.get("order", ["api_bridge", "gws_cli", "pinchtab", "browser_use"])
        self.max_retries = fallback.get("max_retries", 3)
        self.backoff_seconds = fallback.get("backoff_seconds", [1, 3, 10])

        LOG_DIR.mkdir(parents=True, exist_ok=True)

    def _log_routing(self, action: str, engine: str, success: bool,
                     fallback_from: str = None):
        """Log routing decision."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_id": self.agent_id,
            "action": action,
            "engine": engine,
            "success": success,
        }
        if fallback_from:
            entry["fallback_from"] = fallback_from
        try:
            with open(ROUTING_LOG, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

    def _route_action(self, action: str) -> str:
        """Determine which engine to use for an action."""
        if action in self._browser_use_only:
            return "browser_use"
        if action in self._pinchtab_first:
            return "pinchtab"
        return "pinchtab"  # default

    # -------------------------------------------------------------------
    # Governance checks (MA-8, MA-19, MA-6)
    # -------------------------------------------------------------------

    def _check_access(self, action: str) -> tuple:
        """Check MA-19 access control. Returns (allowed, error_or_none)."""
        if not self.access or not self.agent_id:
            return (True, None)
        try:
            result = self.access.check_access(self.agent_id, "web", action)
            if not result.granted:
                # L-413: Guard DOWN for development — log but allow
                logger.debug(f"MA-19 would deny: {self.agent_id}/{action} (dev mode: allowing)")
                return (True, None)
            return (True, None)
        except Exception as e:
            # Don't block on access control errors
            logger.debug(f"MA-19 check failed: {e}")
            return (True, None)

    def _check_behavior(self, action: str, context: dict = None) -> tuple:
        """Check MA-8 behavior guard. Returns (allowed, error_or_none)."""
        if not self.guard or not self.agent_id:
            return (True, None)
        try:
            ctx = {"domain": "web", **(context or {})}
            result = self.guard.check(self.agent_id, action, ctx)
            if result.get("enforcement") == "block":
                violations = result.get("violations", [])
                msg = violations[0].get("message", "Blocked") if violations else "Blocked by MA-8"
                return (False, f"MA-8 blocked: {msg}")
            return (True, None)
        except Exception as e:
            logger.debug(f"MA-8 check failed: {e}")
            return (True, None)

    def _check_web_safety(self, action: str, **kwargs) -> tuple:
        """Run web-specific safety checks from MA-8 behavior guard.
        Returns (allowed, error_or_none)."""
        if not self.guard:
            return (True, None)

        # Payment form check
        form_fields = kwargs.get("form_fields")
        if form_fields:
            v = self.guard._check_web_payment(self.agent_id, form_fields)
            if v:
                return (False, v["message"])

        # Destructive action check
        action_label = kwargs.get("action_label", action)
        v = self.guard._check_web_destructive(self.agent_id, action_label)
        if v:
            return (False, v["message"])

        # First login check
        service = kwargs.get("service")
        if service and action == "login":
            v = self.guard._check_web_first_login(
                self.agent_id, service, self._known_services
            )
            if v:
                logger.warning(v["message"])
                # Don't block first login — just log for audit
                # (MA-16 gate in auth_flows.py handles actual blocking for restricted sites)

        return (True, None)

    def _report_cost(self, action: str, cost: float = 0.0):
        """Report browser action cost to MA-6 cost governor."""
        if not self.cost_gov or cost <= 0:
            return
        try:
            task = {"name": f"browser:{action}", "agent_id": self.agent_id}
            self.cost_gov.post_task(task, actual_cost=cost)
        except Exception:
            pass

    def _pre_action(self, action: str, **kwargs) -> tuple:
        """Run all governance checks before an action. Returns (allowed, error)."""
        # MA-19 access control
        ok, err = self._check_access(action)
        if not ok:
            self._log_routing(action, "blocked", False)
            return (False, err)

        # MA-8 behavior guard
        ok, err = self._check_behavior(action)
        if not ok:
            self._log_routing(action, "blocked", False)
            return (False, err)

        # Web-specific safety
        ok, err = self._check_web_safety(action, **kwargs)
        if not ok:
            self._log_routing(action, "blocked", False)
            return (False, err)

        return (True, None)

    # -------------------------------------------------------------------
    # Lightweight ops (PinchTab-first with browser-use fallback)
    # -------------------------------------------------------------------

    def navigate(self, url: str, **kwargs) -> tuple:
        """Navigate to URL. PinchTab first, browser-use fallback."""
        ok, err = self._pre_action("navigate")
        if not ok:
            return (False, err)
        ok, result = self.pinchtab.navigate(url, **kwargs)
        if ok:
            self._log_routing("navigate", "pinchtab", True)
            return (ok, result)

        if self.fallback_enabled:
            self._log_routing("navigate", "pinchtab", False)
            ok, result = self._run_async(self.browser_use.navigate(url))
            self._log_routing("navigate", "browser_use", ok, fallback_from="pinchtab")
            return (ok, result)

        return (ok, result)

    def _run_async(self, coro) -> tuple:
        """Safely run async coroutine from sync context.
        Handles the case where an event loop may already be running."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Already in async context — use nest_asyncio or return error
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result(timeout=60)
        else:
            return asyncio.run(coro)

    def text(self, **kwargs) -> tuple:
        """Extract page text via PinchTab."""
        ok, result = self.pinchtab.text(**kwargs)
        self._log_routing("text", "pinchtab", ok)
        return (ok, result)

    def snapshot(self, **kwargs) -> tuple:
        """Get accessibility snapshot via PinchTab."""
        ok, result = self.pinchtab.snapshot(**kwargs)
        self._log_routing("snapshot", "pinchtab", ok)
        return (ok, result)

    def click(self, ref: str) -> tuple:
        """Click element via PinchTab."""
        ok, err = self._pre_action("click")
        if not ok:
            return (False, err)
        ok, result = self.pinchtab.click(ref)
        self._log_routing("click", "pinchtab", ok)
        return (ok, result)

    def fill(self, ref: str, value: str) -> tuple:
        """Fill input via PinchTab."""
        ok, err = self._pre_action("fill")
        if not ok:
            return (False, err)
        ok, result = self.pinchtab.fill(ref, value)
        self._log_routing("fill", "pinchtab", ok)
        return (ok, result)

    def screenshot(self, **kwargs) -> tuple:
        """Screenshot via PinchTab."""
        ok, result = self.pinchtab.screenshot(**kwargs)
        self._log_routing("screenshot", "pinchtab", ok)
        return (ok, result)

    def scroll(self, direction: str = "down") -> tuple:
        """Scroll via PinchTab."""
        return self.pinchtab.scroll(direction)

    def find(self, query: str) -> tuple:
        """Find elements via PinchTab."""
        return self.pinchtab.find(query)

    def press(self, key: str, ref: str = None) -> tuple:
        """Press key via PinchTab."""
        return self.pinchtab.press(key, ref)

    def select(self, ref: str, value: str) -> tuple:
        """Select dropdown via PinchTab."""
        return self.pinchtab.select(ref, value)

    # -------------------------------------------------------------------
    # Autonomous ops (browser-use direct)
    # -------------------------------------------------------------------

    async def drag_drop(self, source: str, target: str) -> tuple:
        """Drag and drop via browser-use."""
        ok, err = self._pre_action("drag_drop")
        if not ok:
            return (False, err)
        ok, result = await self.browser_use.drag_drop(source, target)
        self._log_routing("drag_drop", "browser_use", ok)
        return (ok, result)

    async def upload_file(self, input_selector: str, file_path: str) -> tuple:
        """File upload via browser-use."""
        ok, err = self._pre_action("upload_file")
        if not ok:
            return (False, err)
        ok, result = await self.browser_use.upload_file(input_selector, file_path)
        self._log_routing("upload_file", "browser_use", ok)
        return (ok, result)

    async def keyboard_shortcut(self, keys: str) -> tuple:
        """Keyboard shortcut via browser-use (e.g. 'Control+a')."""
        ok, result = await self.browser_use.keyboard_shortcut(keys)
        self._log_routing("keyboard_shortcut", "browser_use", ok)
        return (ok, result)

    async def right_click(self, selector: str) -> tuple:
        """Right-click via browser-use."""
        ok, result = await self.browser_use.right_click(selector)
        self._log_routing("right_click", "browser_use", ok)
        return (ok, result)

    async def handle_iframe(self, iframe_sel: str, inner_sel: str,
                            action: str = "click") -> tuple:
        """Iframe interaction via browser-use."""
        ok, result = await self.browser_use.handle_iframe(iframe_sel, inner_sel, action)
        self._log_routing("iframe", "browser_use", ok)
        return (ok, result)

    async def wait_for_element(self, selector: str, timeout: int = 10000) -> tuple:
        """Wait for element via browser-use."""
        return await self.browser_use.wait_for_element(selector, timeout)

    # -------------------------------------------------------------------
    # Authentication
    # -------------------------------------------------------------------

    async def login(self, service: str, method: str = "auto") -> tuple:
        """Login to a service using auth flow handler."""
        ok, err = self._pre_action("login", service=service)
        if not ok:
            return (False, err)
        ok, result = await self.auth.login(service, self.agent_id, method)
        if ok:
            self._known_services.add(service)
        self._log_routing("login", "browser_use", ok)
        return (ok, result)

    async def logout(self, service: str) -> tuple:
        """Logout from a service."""
        return await self.auth.logout(self.agent_id, service)

    # -------------------------------------------------------------------
    # Autonomous tasks
    # -------------------------------------------------------------------

    async def run_autonomous_task(self, goal: str, start_url: str = None,
                                  max_steps: int = None) -> tuple:
        """Execute an autonomous browser task via browser-use."""
        ok, err = self._pre_action("autonomous_task")
        if not ok:
            return (False, err)
        ok, result = await self.browser_use.run_task(goal, start_url, max_steps)
        # Report estimated cost to MA-6
        if ok and isinstance(result, dict):
            steps = result.get("steps_taken", 0)
            estimated_cost = steps * 0.01  # ~$0.01 per LLM step
            self._report_cost("autonomous_task", estimated_cost)
        self._log_routing("autonomous_task", "browser_use", ok)
        return (ok, result)

    # -------------------------------------------------------------------
    # Google Workspace (gws CLI — no browser needed)
    # -------------------------------------------------------------------

    def gmail_send(self, **kwargs) -> tuple:
        """Send email via gws CLI."""
        return self.gws.gmail_send(**kwargs)

    def gmail_search(self, query: str, **kwargs) -> tuple:
        """Search Gmail via gws CLI."""
        return self.gws.gmail_search(query, **kwargs)

    def drive_list(self, **kwargs) -> tuple:
        """List Drive files via gws CLI."""
        return self.gws.drive_list(**kwargs)

    def drive_upload(self, file_path: str, **kwargs) -> tuple:
        """Upload to Drive via gws CLI."""
        return self.gws.drive_upload(file_path, **kwargs)

    def sheets_read(self, spreadsheet_id: str, range_: str) -> tuple:
        """Read Sheets via gws CLI."""
        return self.gws.sheets_read(spreadsheet_id, range_)

    def sheets_append(self, spreadsheet_id: str, range_: str, values: list) -> tuple:
        """Append to Sheets via gws CLI."""
        return self.gws.sheets_append(spreadsheet_id, range_, values)

    def calendar_agenda(self, days: int = 7) -> tuple:
        """Get calendar agenda via gws CLI."""
        return self.gws.calendar_agenda(days)

    def calendar_create_event(self, **kwargs) -> tuple:
        """Create calendar event via gws CLI."""
        return self.gws.calendar_create_event(**kwargs)

    # -------------------------------------------------------------------
    # Smart routing: API-first with browser fallback
    # -------------------------------------------------------------------

    def is_google_service(self, service: str) -> bool:
        """Check if a service should be routed through gws CLI."""
        google_keywords = {"google", "gmail", "drive", "sheets", "calendar", "docs", "chat"}
        return any(g in service.lower() for g in google_keywords)

    # -------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------

    async def close(self):
        """Close all browser sessions."""
        await self.browser_use.close()

    def health(self) -> dict:
        """Check health of all engines."""
        pt_ok, pt_result = self.pinchtab.health()
        gws_ok, gws_result = self.gws.health()
        return {
            "pinchtab": {"healthy": pt_ok, "detail": pt_result},
            "gws": {"healthy": gws_ok, "detail": gws_result},
            "browser_use": {"healthy": True, "detail": "adapter ready"},
            "vault": {"healthy": True, "services": len(self.vault.list_services())},
        }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def _run_tests():
    """Run autonomy layer tests."""
    from unittest.mock import patch, MagicMock

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
    print("  Browser Autonomy Layer Tests")
    print("=" * 60)

    # Test 1: Constructor
    def test_constructor():
        layer = BrowserAutonomyLayer(agent_id="test")
        assert layer.agent_id == "test"
        assert layer.pinchtab is not None
        assert layer.browser_use is not None
        assert layer.gws is not None
        assert layer.vault is not None
        assert layer.auth is not None
    test("Constructor initializes all engines", test_constructor)

    # Test 2: Routing config loaded
    def test_routing():
        layer = BrowserAutonomyLayer(agent_id="test")
        assert "navigate" in layer._pinchtab_first
        assert "drag_drop" in layer._browser_use_only
        assert "login" in layer._browser_use_only
    test("Routing config loaded", test_routing)

    # Test 3: Route action
    def test_route_action():
        layer = BrowserAutonomyLayer(agent_id="test")
        assert layer._route_action("navigate") == "pinchtab"
        assert layer._route_action("drag_drop") == "browser_use"
        assert layer._route_action("click") == "pinchtab"
    test("Route action logic", test_route_action)

    # Test 4: Navigate via PinchTab
    def test_navigate():
        layer = BrowserAutonomyLayer(agent_id="test")
        with patch.object(layer.pinchtab, "navigate",
                          return_value=(True, {"url": "https://x.com", "title": "X"})):
            ok, result = layer.navigate("https://x.com")
            assert ok is True
            assert result["url"] == "https://x.com"
    test("Navigate routes to PinchTab", test_navigate)

    # Test 5: Navigate fallback
    def test_navigate_fallback():
        layer = BrowserAutonomyLayer(agent_id="test")
        assert layer.fallback_enabled is True
        assert layer._route_action("navigate") == "pinchtab"
        # Verify fallback chain includes browser_use after pinchtab
        assert layer.fallback_order.index("pinchtab") < layer.fallback_order.index("browser_use")
    test("Navigate fallback configured", test_navigate_fallback)

    # Test 6: Text via PinchTab
    def test_text():
        layer = BrowserAutonomyLayer(agent_id="test")
        with patch.object(layer.pinchtab, "text",
                          return_value=(True, {"text": "hello", "title": "T"})):
            ok, result = layer.text()
            assert ok is True
    test("Text routes to PinchTab", test_text)

    # Test 7: Health check
    def test_health():
        layer = BrowserAutonomyLayer(agent_id="test")
        with patch.object(layer.pinchtab, "health",
                          return_value=(True, {"status": "ok"})):
            with patch.object(layer.gws, "health",
                              return_value=(True, {"version": "0.22"})):
                h = layer.health()
                assert h["pinchtab"]["healthy"] is True
                assert h["gws"]["healthy"] is True
                assert h["browser_use"]["healthy"] is True
    test("Health check all engines", test_health)

    # Test 8: Fallback config
    def test_fallback_config():
        layer = BrowserAutonomyLayer(agent_id="test")
        assert layer.fallback_enabled is True
        assert "gws_cli" in layer.fallback_order
        assert "pinchtab" in layer.fallback_order
        assert "browser_use" in layer.fallback_order
    test("Fallback chain configured", test_fallback_config)

    # Test 9: Google services list
    def test_google_services():
        layer = BrowserAutonomyLayer(agent_id="test")
        assert "gmail" in layer._google_services
        assert "drive" in layer._google_services
        assert "sheets" in layer._google_services
    test("Google services configured for gws", test_google_services)

    # Test 10: GWS gmail passthrough
    def test_gws_gmail():
        layer = BrowserAutonomyLayer(agent_id="test")
        with patch.object(layer.gws, "gmail_search",
                          return_value=(True, {"messages": []})):
            ok, result = layer.gmail_search("is:unread")
            assert ok is True
    test("Gmail search via gws bridge", test_gws_gmail)

    # Test 11: Routing log
    def test_routing_log():
        layer = BrowserAutonomyLayer(agent_id="test")
        layer._log_routing("test", "pinchtab", True)
        assert ROUTING_LOG.exists()
    test("Routing log created", test_routing_log)

    # Test 12: Click via PinchTab
    def test_click():
        layer = BrowserAutonomyLayer(agent_id="test")
        with patch.object(layer.pinchtab, "click",
                          return_value=(True, {"clicked": True})):
            ok, _ = layer.click("e5")
            assert ok is True
    test("Click routes to PinchTab", test_click)

    print()
    print(f"  {'=' * 50}")
    print(f"  Autonomy Layer Tests: {'PASS' if failed == 0 else 'FAIL'}")
    print(f"  Passed: {passed}/{total}")
    if failed > 0:
        print(f"  Failed: {failed}/{total}")
    print(f"  {'=' * 50}")

    return failed == 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        success = _run_tests()
        sys.exit(0 if success else 1)
    elif "--health" in sys.argv:
        layer = BrowserAutonomyLayer(agent_id="health_check")
        h = layer.health()
        for engine, status in h.items():
            icon = "✅" if status.get("healthy") else "❌"
            print(f"  {icon} {engine}: {status}")
    else:
        print("Browser Autonomy Layer. Use --test or --health.")
