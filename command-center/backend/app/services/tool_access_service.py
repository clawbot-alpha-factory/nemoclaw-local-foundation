"""
NemoClaw Tool Access Service — Direct tool access from agent loops.

Provides agent-level access to external tools (PinchTab browser, Apify scraping,
GWS) via subprocess invocation of existing bridge scripts.

Each method returns (result, error) tuple with 3-attempt retry logic.

NEW FILE: command-center/backend/app/services/tool_access_service.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger("cc.tool_access")

_MAX_RETRIES = 3
_SUBPROCESS_TIMEOUT = 300  # 5 minutes


class ToolAccessService:
    """
    Direct tool access for agent loops.

    Tools:
    - PinchTab browser (via scripts/web_browser.py)
    - Apify scraping (via scripts/apify_bridge.py)
    - GWS Google Workspace CLI (via scripts/gws_bridge.py)
    """

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.python = str(repo_root / ".venv313" / "bin" / "python3")
        self._scripts = {
            "browser": repo_root / "scripts" / "web_browser.py",
            "apify": repo_root / "scripts" / "apify_bridge.py",
            "gws": repo_root / "scripts" / "gws_bridge.py",
        }
        logger.info(
            "ToolAccessService initialized (tools: %s)",
            ", ".join(k for k, v in self._scripts.items() if v.exists()),
        )

    # ── Browser (PinchTab) ────────────────────────────────────────────

    async def run_browser_task(
        self,
        agent_id: str,
        url: str,
        actions: list[dict[str, Any]] | None = None,
    ) -> tuple[dict[str, Any] | None, str | None]:
        """
        Execute a browser task via PinchTab bridge.

        Args:
            agent_id: Agent requesting the action (for audit/budget).
            url: Target URL to navigate to.
            actions: Optional list of actions, e.g. [{"kind": "click", "ref": "e5"}].

        Returns:
            (result_dict, None) on success or (None, error_string) on failure.
        """
        payload = {
            "agent_id": agent_id,
            "url": url,
            "actions": actions or [],
        }
        return await self._run_script("browser", payload)

    # ── Apify Scraping ────────────────────────────────────────────────

    async def run_apify_scrape(
        self,
        agent_id: str,
        platform: str,
        target: str,
        max_results: int = 50,
    ) -> tuple[dict[str, Any] | None, str | None]:
        """
        Run an Apify scraping task via the bridge.

        Args:
            agent_id: Agent requesting the scrape.
            platform: Platform key (tiktok, instagram, linkedin, twitter, web).
            target: Username, hashtag, or URL to scrape.
            max_results: Maximum results to return.

        Returns:
            (result_dict, None) on success or (None, error_string) on failure.
        """
        payload = {
            "agent_id": agent_id,
            "platform": platform,
            "target": target,
            "max_results": max_results,
        }
        return await self._run_script("apify", payload)

    # ── Health Check ──────────────────────────────────────────────────

    async def check_tool_health(self) -> dict[str, dict[str, Any]]:
        """
        Check health of all external tools.

        Returns dict keyed by tool name with status info:
            {"pinchtab": {"available": True, "script_exists": True}, ...}
        """
        health: dict[str, dict[str, Any]] = {}

        for name, script_path in self._scripts.items():
            entry: dict[str, Any] = {"script_exists": script_path.exists()}

            if name == "pinchtab" or name == "browser":
                # Quick PinchTab health: check if server responds
                try:
                    proc = await asyncio.create_subprocess_exec(
                        "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                        "http://localhost:9867/health",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
                    code = stdout.decode().strip()
                    entry["available"] = code == "200"
                    entry["http_status"] = code
                except Exception:
                    entry["available"] = False

            elif name == "apify":
                # Apify available if APIFY_TOKEN is set
                entry["available"] = bool(os.environ.get("APIFY_TOKEN"))

            elif name == "gws":
                # GWS available if script exists (uses service account)
                entry["available"] = script_path.exists()

            health[name] = entry

        return health

    # ── Internal: subprocess runner with retries ──────────────────────

    async def _run_script(
        self,
        tool_name: str,
        payload: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, str | None]:
        """
        Run a tool script as subprocess with retry logic.

        Passes payload as JSON via --json stdin arg.
        Returns (result, None) or (None, error).
        """
        script = self._scripts.get(tool_name)
        if not script or not script.exists():
            return None, f"Script not found: {tool_name}"

        cmd = [self.python, str(script), "--json", json.dumps(payload)]
        env = {**os.environ, "PYTHONPATH": str(self.repo_root)}

        last_error = ""
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(self.repo_root),
                    env=env,
                )
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=_SUBPROCESS_TIMEOUT
                )

                stdout_str = stdout.decode("utf-8", errors="replace")
                stderr_str = stderr.decode("utf-8", errors="replace")

                if proc.returncode == 0:
                    # Try to parse JSON from stdout
                    try:
                        result = json.loads(stdout_str)
                    except json.JSONDecodeError:
                        result = {"raw_output": stdout_str.strip()}

                    logger.info(
                        "Tool %s succeeded (agent=%s, attempt=%d)",
                        tool_name, payload.get("agent_id", "?"), attempt,
                    )
                    return result, None

                last_error = stderr_str[:500] or stdout_str[:500] or f"Exit code {proc.returncode}"
                logger.warning(
                    "Tool %s attempt %d/%d failed: %s",
                    tool_name, attempt, _MAX_RETRIES, last_error[:100],
                )

            except asyncio.TimeoutError:
                last_error = f"Timeout after {_SUBPROCESS_TIMEOUT}s"
                logger.warning("Tool %s attempt %d/%d timed out", tool_name, attempt, _MAX_RETRIES)

            except Exception as e:
                last_error = str(e)
                logger.warning("Tool %s attempt %d/%d error: %s", tool_name, attempt, _MAX_RETRIES, e)

            # Brief backoff before retry
            if attempt < _MAX_RETRIES:
                await asyncio.sleep(1.0 * attempt)

        logger.error("Tool %s failed after %d attempts: %s", tool_name, _MAX_RETRIES, last_error[:200])
        return None, last_error
