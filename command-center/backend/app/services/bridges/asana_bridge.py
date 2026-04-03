"""
NemoClaw Execution Engine — Asana Bridge

Real Asana API bridge for mission lifecycle management.
Actions: get_workspaces, create_project, create_task, add_comment, complete_task, get_project_tasks

Rate limited: 60 requests/minute sliding window.
"""

from __future__ import annotations

import asyncio
import collections
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger("cc.bridge.asana")


class AsanaBridge:
    """Asana REST API bridge with sliding-window rate limiting."""

    BASE_URL = "https://app.asana.com/api/1.0"
    RATE_LIMIT = 60  # requests per minute

    def __init__(self, access_token: str):
        self.access_token = access_token
        self._client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        self._timestamps: collections.deque[float] = collections.deque(maxlen=self.RATE_LIMIT)
        logger.info("AsanaBridge initialized")

    # ── Rate Limiting ─────────────────────────────────────────────────

    async def _throttle(self) -> None:
        """Enforce 60 req/min sliding window."""
        now = time.monotonic()
        if len(self._timestamps) >= self.RATE_LIMIT:
            oldest = self._timestamps[0]
            wait = 60.0 - (now - oldest)
            if wait > 0:
                logger.debug("Rate limit: sleeping %.1fs", wait)
                await asyncio.sleep(wait)
        self._timestamps.append(time.monotonic())

    # ── HTTP Helpers ──────────────────────────────────────────────────

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        await self._throttle()
        resp = await self._client.get(f"{self.BASE_URL}{path}", params=params)
        resp.raise_for_status()
        return resp.json()

    async def _post(self, path: str, data: dict[str, Any]) -> dict[str, Any]:
        await self._throttle()
        resp = await self._client.post(f"{self.BASE_URL}{path}", json={"data": data})
        resp.raise_for_status()
        return resp.json()

    async def _put(self, path: str, data: dict[str, Any]) -> dict[str, Any]:
        await self._throttle()
        resp = await self._client.put(f"{self.BASE_URL}{path}", json={"data": data})
        resp.raise_for_status()
        return resp.json()

    # ── Public API ────────────────────────────────────────────────────

    async def get_workspaces(self) -> list[dict[str, Any]]:
        """List all workspaces the token can access."""
        result = await self._get("/workspaces")
        return result.get("data", [])

    async def create_project(
        self,
        workspace_gid: str,
        name: str,
        sections: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a project and optional sections. Returns {gid, sections: {name: gid}}."""
        result = await self._post("/projects", {
            "workspace": workspace_gid,
            "name": name,
        })
        project = result.get("data", {})
        project_gid = project["gid"]

        section_map: dict[str, str] = {}
        for section_name in (sections or []):
            sec_result = await self._post(f"/projects/{project_gid}/sections", {
                "name": section_name,
            })
            sec = sec_result.get("data", {})
            section_map[section_name] = sec["gid"]

        return {
            "gid": project_gid,
            "name": name,
            "url": f"https://app.asana.com/0/{project_gid}",
            "sections": section_map,
        }

    async def create_task(
        self,
        project_gid: str,
        section_gid: str | None,
        name: str,
        notes: str = "",
        assignee_name: str | None = None,
    ) -> dict[str, Any]:
        """Create a task in a project/section. Returns task data with gid."""
        payload: dict[str, Any] = {
            "name": name,
            "notes": notes,
            "projects": [project_gid],
        }
        if assignee_name:
            payload["notes"] = f"Assignee: {assignee_name}\n\n{notes}".strip()

        result = await self._post("/tasks", payload)
        task = result.get("data", {})

        # Move to section if specified
        if section_gid and task.get("gid"):
            await self._post(f"/sections/{section_gid}/addTask", {
                "task": task["gid"],
            })

        return task

    async def add_comment(self, task_gid: str, text: str) -> dict[str, Any]:
        """Post a comment (story) on a task. Returns story data with gid."""
        result = await self._post(f"/tasks/{task_gid}/stories", {
            "text": text,
        })
        return result.get("data", {})

    async def complete_task(self, task_gid: str) -> dict[str, Any]:
        """Mark a task as completed."""
        result = await self._put(f"/tasks/{task_gid}", {
            "completed": True,
        })
        return result.get("data", {})

    async def get_project_tasks(self, project_gid: str) -> list[dict[str, Any]]:
        """List all tasks in a project."""
        result = await self._get("/tasks", params={
            "project": project_gid,
            "opt_fields": "name,completed,assignee.name,notes,memberships.section.name",
        })
        return result.get("data", [])

    # ── BridgeManager Compatibility ───────────────────────────────────

    async def execute(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        """Dispatch action for BridgeManager integration."""
        actions = {
            "get_workspaces": lambda p: self.get_workspaces(),
            "create_project": lambda p: self.create_project(
                p["workspace_gid"], p["name"], p.get("sections"),
            ),
            "create_task": lambda p: self.create_task(
                p["project_gid"], p.get("section_gid"), p["name"],
                p.get("notes", ""), p.get("assignee_name"),
            ),
            "add_comment": lambda p: self.add_comment(p["task_gid"], p["text"]),
            "complete_task": lambda p: self.complete_task(p["task_gid"]),
            "get_project_tasks": lambda p: self.get_project_tasks(p["project_gid"]),
        }
        handler = actions.get(action)
        if not handler:
            raise ValueError(f"Unknown Asana action: {action}. Available: {list(actions.keys())}")
        return await handler(params)
