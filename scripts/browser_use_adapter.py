#!/usr/bin/env python3
"""
NemoClaw ↔ browser-use Adapter (browser_use_adapter.py)
Wraps browser-use's autonomous agent for NemoClaw skills and agents.

All LLM calls route through lib/routing.py (L-003 compliance).
Returns NemoClaw-standard tuples: (success: bool, data_or_error).

Usage:
    from browser_use_adapter import BrowserUseAdapter
    adapter = BrowserUseAdapter(agent_id="growth_revenue_lead")
    ok, result = await adapter.run_task("Go to example.com and extract the heading")
"""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any

REPO = Path(__file__).resolve().parent.parent
LOG_DIR = Path.home() / ".nemoclaw" / "browser"
ACTION_LOG = LOG_DIR / "browser-use-actions.jsonl"

sys.path.insert(0, str(REPO / "lib"))
sys.path.insert(0, str(REPO / "scripts"))

logger = logging.getLogger("nemoclaw.browser_use")


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

def _load_autonomy_config() -> dict:
    """Load browser-autonomy.yaml if it exists."""
    config_path = REPO / "config" / "browser-autonomy.yaml"
    if config_path.exists():
        try:
            import yaml
            with open(config_path) as f:
                return yaml.safe_load(f).get("autonomy", {})
        except Exception:
            pass
    return {}


def _load_web_permissions(agent_id: str) -> dict:
    """Load per-agent web permissions."""
    config_path = REPO / "config" / "web-permissions.yaml"
    if config_path.exists():
        try:
            import yaml
            with open(config_path) as f:
                data = yaml.safe_load(f)
            perms = data.get("agent_permissions", {})
            defaults = perms.get("defaults", {})
            agent_perms = perms.get(agent_id, {})
            merged = {**defaults, **agent_perms}
            return merged
        except Exception:
            pass
    return {}


# ---------------------------------------------------------------------------
# LangChain LLM wrapper for browser-use (routes through call_llm)
# ---------------------------------------------------------------------------

def _build_langchain_llm(task_class: str = "moderate", max_tokens: int = 4000):
    """Build a LangChain ChatModel that routes through NemoClaw's config.
    browser-use accepts any LangChain BaseChatModel as its llm parameter."""
    from routing import resolve_from_env_or_config, get_api_key, _build_llm
    provider, model, cost = resolve_from_env_or_config(task_class)
    api_key = get_api_key(provider)
    if not api_key:
        raise ValueError(f"{provider.upper()} API key not found for browser-use")
    return _build_llm(provider, model, api_key, max_tokens)


# ---------------------------------------------------------------------------
# BrowserUseAdapter
# ---------------------------------------------------------------------------

class BrowserUseAdapter:
    """NemoClaw adapter for browser-use autonomous browser agent."""

    def __init__(self, agent_id: str = None, llm_task_class: str = "moderate",
                 headless: bool = True, user_data_dir: str = None):
        self.agent_id = agent_id
        self.llm_task_class = llm_task_class
        self.headless = headless
        self.config = _load_autonomy_config()
        self.permissions = _load_web_permissions(agent_id) if agent_id else {}

        # Per-agent persistent profile directory
        if user_data_dir:
            self.user_data_dir = Path(user_data_dir)
        elif agent_id:
            self.user_data_dir = Path.home() / ".nemoclaw" / "browser" / "profiles" / agent_id
        else:
            self.user_data_dir = None

        # Concurrency
        self.max_steps = self.permissions.get("max_autonomous_steps", 50)
        self._session = None

        # Logging
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        if self.user_data_dir:
            self.user_data_dir.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------

    def _log_action(self, action: str, params: dict, success: bool,
                    result: Any = None, error: str = None):
        """Append action to JSONL log."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "engine": "browser_use",
            "agent_id": self.agent_id,
            "action": action,
            "params": {k: str(v)[:200] for k, v in params.items()},
            "success": success,
        }
        if error:
            entry["error"] = str(error)[:500]
        if result and isinstance(result, dict):
            entry["result_summary"] = {k: v for k, v in result.items()
                                       if k in ("url", "title", "steps", "cost", "is_done")}
        try:
            with open(ACTION_LOG, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

    def _check_permission(self, action: str) -> tuple:
        """Check if agent has permission for this action."""
        allowed = self.permissions.get("allowed_actions", [])
        if allowed and action not in allowed:
            return (False, f"Agent '{self.agent_id}' not permitted for action '{action}'")
        return (True, None)

    def _check_domain(self, url: str) -> tuple:
        """Check if URL domain is in agent's allowed domains."""
        allowed_domains = self.permissions.get("allowed_domains", [])
        if not allowed_domains:
            return (True, None)  # No restrictions
        # Wildcard "*" allows all
        if "*" in allowed_domains:
            return (True, None)
        try:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc.lower()
            # Strip port if present
            if ":" in domain:
                domain = domain.split(":")[0]
            for pattern in allowed_domains:
                # Convert glob "*.example.com" to proper domain match
                base = pattern.replace("*.", "").lstrip(".")
                if domain == base or domain.endswith("." + base):
                    return (True, None)
            return (False, f"Domain '{domain}' not in allowed domains for agent '{self.agent_id}'")
        except Exception:
            return (True, None)

    async def _get_session(self):
        """Lazy-init browser session with persistent profile."""
        if self._session is not None:
            return self._session
        try:
            from browser_use import BrowserSession

            session_kwargs = {
                "headless": self.headless,
                "disable_security": False,
                "keep_alive": True,
            }
            if self.user_data_dir:
                session_kwargs["user_data_dir"] = str(self.user_data_dir)

            # Apply allowed/blocked domains from permissions
            allowed = self.permissions.get("allowed_domains")
            if allowed:
                clean = [d.replace("*.", "").lstrip(".") for d in allowed]
                session_kwargs["allowed_domains"] = clean

            self._session = BrowserSession(**session_kwargs)
            return self._session
        except Exception as e:
            logger.error(f"Failed to create browser session: {e}")
            raise

    # -------------------------------------------------------------------
    # Autonomous task execution
    # -------------------------------------------------------------------

    async def run_task(self, goal: str, start_url: str = None,
                       max_steps: int = None,
                       sensitive_data: dict = None) -> tuple:
        """Execute an autonomous browser task using browser-use Agent.

        Args:
            goal: Natural language task description
            start_url: Optional starting URL
            max_steps: Max reasoning steps (default: agent's configured limit)
            sensitive_data: Dict of placeholder->value for credential injection

        Returns:
            (success, {result, steps_taken, is_done, errors})
        """
        ok, err = self._check_permission("autonomous_task")
        if not ok:
            return (False, err)

        if start_url:
            ok, err = self._check_domain(start_url)
            if not ok:
                return (False, err)

        steps = max_steps or self.max_steps
        start_time = time.time()

        try:
            from browser_use import Agent

            llm = _build_langchain_llm(self.llm_task_class)
            session = await self._get_session()

            agent_kwargs = {
                "task": goal,
                "llm": llm,
                "browser_session": session,
                "use_vision": True,
                "max_failures": 3,
                "max_actions_per_step": 5,
            }
            if sensitive_data:
                agent_kwargs["sensitive_data"] = sensitive_data
            if start_url:
                agent_kwargs["initial_actions"] = [
                    {"go_to_url": {"url": start_url}}
                ]

            agent = Agent(**agent_kwargs)
            history = await agent.run(max_steps=steps)

            elapsed = time.time() - start_time
            result = {
                "is_done": history.is_done(),
                "result": history.final_result() if history.is_done() else None,
                "steps_taken": len(history.history),
                "errors": [str(e) for e in history.errors()] if history.errors() else [],
                "elapsed_seconds": round(elapsed, 2),
            }

            self._log_action("run_task", {"goal": goal[:200], "start_url": start_url},
                             history.is_done(), result)
            return (history.is_done(), result)

        except Exception as e:
            self._log_action("run_task", {"goal": goal[:200]}, False, error=str(e))
            return (False, str(e))

    # -------------------------------------------------------------------
    # Direct Playwright actions (for non-autonomous use)
    # -------------------------------------------------------------------

    async def drag_drop(self, source_selector: str, target_selector: str) -> tuple:
        """Drag element from source to target using Playwright."""
        ok, err = self._check_permission("drag_drop")
        if not ok:
            return (False, err)
        try:
            session = await self._get_session()
            page = await session.get_current_page()
            source = page.locator(source_selector)
            target = page.locator(target_selector)
            await source.drag_to(target)
            self._log_action("drag_drop", {"source": source_selector, "target": target_selector}, True)
            return (True, {"success": True})
        except Exception as e:
            self._log_action("drag_drop", {"source": source_selector, "target": target_selector}, False, error=str(e))
            return (False, str(e))

    async def upload_file(self, input_selector: str, file_path: str) -> tuple:
        """Upload file to a file input element."""
        ok, err = self._check_permission("upload_file")
        if not ok:
            return (False, err)
        # Block executable uploads (check before existence for safety)
        ext = Path(file_path).suffix.lower()
        blocked_exts = {".exe", ".bat", ".cmd", ".sh", ".ps1", ".msi", ".dll", ".so"}
        if ext in blocked_exts:
            return (False, f"Executable file upload blocked: {ext}")
        if not Path(file_path).exists():
            return (False, f"File not found: {file_path}")
        try:
            session = await self._get_session()
            page = await session.get_current_page()
            await page.set_input_files(input_selector, file_path)
            self._log_action("upload_file", {"selector": input_selector, "file": file_path}, True)
            return (True, {"uploaded": file_path})
        except Exception as e:
            self._log_action("upload_file", {"selector": input_selector}, False, error=str(e))
            return (False, str(e))

    async def keyboard_shortcut(self, keys: str) -> tuple:
        """Execute keyboard shortcut (e.g. 'Control+a', 'Meta+c')."""
        ok, err = self._check_permission("keyboard_shortcut")
        if not ok:
            return (False, err)
        try:
            session = await self._get_session()
            page = await session.get_current_page()
            await page.keyboard.press(keys)
            self._log_action("keyboard_shortcut", {"keys": keys}, True)
            return (True, {"keys": keys})
        except Exception as e:
            self._log_action("keyboard_shortcut", {"keys": keys}, False, error=str(e))
            return (False, str(e))

    async def right_click(self, selector: str) -> tuple:
        """Right-click on an element."""
        try:
            session = await self._get_session()
            page = await session.get_current_page()
            await page.click(selector, button="right")
            self._log_action("right_click", {"selector": selector}, True)
            return (True, {"clicked": True})
        except Exception as e:
            self._log_action("right_click", {"selector": selector}, False, error=str(e))
            return (False, str(e))

    async def wait_for_element(self, selector: str, timeout: int = 10000) -> tuple:
        """Wait for element to appear. Timeout in ms."""
        try:
            session = await self._get_session()
            page = await session.get_current_page()
            await page.wait_for_selector(selector, timeout=timeout)
            self._log_action("wait_for_element", {"selector": selector}, True)
            return (True, {"found": True})
        except Exception as e:
            self._log_action("wait_for_element", {"selector": selector}, False, error=str(e))
            return (False, str(e))

    async def handle_iframe(self, iframe_selector: str, inner_selector: str,
                            action: str = "click") -> tuple:
        """Interact with content inside an iframe."""
        try:
            session = await self._get_session()
            page = await session.get_current_page()
            frame = page.frame_locator(iframe_selector)
            element = frame.locator(inner_selector)
            if action == "click":
                await element.click()
            elif action == "text":
                text = await element.text_content()
                self._log_action("handle_iframe", {"iframe": iframe_selector, "action": "text"}, True)
                return (True, {"text": text})
            self._log_action("handle_iframe", {"iframe": iframe_selector, "action": action}, True)
            return (True, {"success": True})
        except Exception as e:
            self._log_action("handle_iframe", {"iframe": iframe_selector}, False, error=str(e))
            return (False, str(e))

    async def navigate(self, url: str) -> tuple:
        """Navigate to URL using Playwright directly."""
        ok, err = self._check_domain(url)
        if not ok:
            return (False, err)
        try:
            session = await self._get_session()
            page = await session.get_current_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            title = await page.title()
            self._log_action("navigate", {"url": url}, True)
            return (True, {"url": url, "title": title})
        except Exception as e:
            self._log_action("navigate", {"url": url}, False, error=str(e))
            return (False, str(e))

    async def screenshot(self, save_path: str = None) -> tuple:
        """Take screenshot."""
        try:
            session = await self._get_session()
            page = await session.get_current_page()
            if save_path:
                Path(save_path).parent.mkdir(parents=True, exist_ok=True)
                await page.screenshot(path=save_path)
                self._log_action("screenshot", {"path": save_path}, True)
                return (True, save_path)
            else:
                data = await page.screenshot()
                self._log_action("screenshot", {}, True)
                return (True, data)
        except Exception as e:
            self._log_action("screenshot", {}, False, error=str(e))
            return (False, str(e))

    # -------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------

    async def close(self):
        """Close browser session."""
        if self._session:
            try:
                await self._session.close()
            except Exception:
                pass
            self._session = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def _run_tests():
    """Run adapter tests with mocks."""
    from unittest.mock import patch, MagicMock, AsyncMock
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
    print("  browser-use Adapter Tests")
    print("=" * 60)

    # Test 1: Constructor
    def test_constructor():
        adapter = BrowserUseAdapter(agent_id="test_agent")
        assert adapter.agent_id == "test_agent"
        assert adapter.headless is True
        assert adapter.max_steps == 50
    test("Constructor defaults", test_constructor)

    # Test 2: Permission check
    def test_permission_check():
        adapter = BrowserUseAdapter(agent_id="test")
        adapter.permissions = {"allowed_actions": ["navigate", "click"]}
        ok, err = adapter._check_permission("navigate")
        assert ok is True
        ok, err = adapter._check_permission("drag_drop")
        assert ok is False
    test("Permission check", test_permission_check)

    # Test 3: Domain check
    def test_domain_check():
        adapter = BrowserUseAdapter(agent_id="test")
        adapter.permissions = {"allowed_domains": ["*.example.com"]}
        ok, _ = adapter._check_domain("https://www.example.com/page")
        assert ok is True
        ok, _ = adapter._check_domain("https://example.com/page")
        assert ok is True
        ok, _ = adapter._check_domain("https://evil.com/hack")
        assert ok is False
        # Ensure subdomain bypass is blocked
        ok, _ = adapter._check_domain("https://myexample.com.attacker.com")
        assert ok is False, "Should block subdomain bypass"
    test("Domain check", test_domain_check)

    # Test 4: No domain restriction
    def test_no_domain_restriction():
        adapter = BrowserUseAdapter(agent_id="test")
        adapter.permissions = {}
        ok, _ = adapter._check_domain("https://anything.com")
        assert ok is True
    test("No domain restriction allows all", test_no_domain_restriction)

    # Test 5: Executable upload blocked
    def test_exe_blocked():
        adapter = BrowserUseAdapter(agent_id="test")
        adapter.permissions = {"allowed_actions": ["upload_file"]}
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(adapter.upload_file("input", "/tmp/virus.exe"))
        loop.close()
        assert result[0] is False
        assert "blocked" in result[1].lower()
    test("Executable upload blocked", test_exe_blocked)

    # Test 6: File not found
    def test_file_not_found():
        adapter = BrowserUseAdapter(agent_id="test")
        adapter.permissions = {"allowed_actions": ["upload_file"]}
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(adapter.upload_file("input", "/nonexistent/file.pdf"))
        loop.close()
        assert result[0] is False
        assert "not found" in result[1].lower()
    test("File not found error", test_file_not_found)

    # Test 7: Action log created
    def test_action_log():
        adapter = BrowserUseAdapter(agent_id="test")
        adapter._log_action("test_action", {"key": "val"}, True)
        assert ACTION_LOG.exists()
    test("Action log file created", test_action_log)

    # Test 8: Profile directory created
    def test_profile_dir():
        adapter = BrowserUseAdapter(agent_id="test_profile_agent")
        assert adapter.user_data_dir.exists()
    test("Profile directory created", test_profile_dir)

    # Test 9: LLM builder
    def test_llm_builder():
        with patch("routing.resolve_from_env_or_config", return_value=("openai", "gpt-4o", 0.01)):
            with patch("routing.get_api_key", return_value="test-key"):
                with patch("routing._build_llm") as mock_build:
                    mock_build.return_value = MagicMock()
                    llm = _build_langchain_llm("moderate")
                    assert llm is not None
    test("LLM builder routes through routing.py", test_llm_builder)

    # Test 10: Custom user_data_dir
    def test_custom_data_dir():
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = BrowserUseAdapter(agent_id="test", user_data_dir=tmpdir)
            assert str(adapter.user_data_dir) == tmpdir
    test("Custom user_data_dir", test_custom_data_dir)

    print()
    print(f"  {'=' * 50}")
    print(f"  Adapter Tests: {'PASS' if failed == 0 else 'FAIL'}")
    print(f"  Passed: {passed}/{total}")
    if failed > 0:
        print(f"  Failed: {failed}/{total}")
    print(f"  {'=' * 50}")

    return failed == 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        success = _run_tests()
        sys.exit(0 if success else 1)
    else:
        print("browser-use adapter loaded. Use --test to run tests.")
