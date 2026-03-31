"""
NemoClaw Execution Engine — Bridges Router (E-8)

8 endpoints for bridge management and execution.

NEW FILE: command-center/backend/app/api/routers/bridges.py
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger("cc.api.bridges")

router = APIRouter(prefix="/api/bridges", tags=["bridges"])


class BridgeExecuteRequest(BaseModel):
    bridge: str
    action: str
    params: dict[str, Any] = {}


def _get_manager(request: Request):
    svc = getattr(request.app.state, "bridge_manager", None)
    if svc is None:
        raise HTTPException(503, "BridgeManager not initialized")
    return svc


@router.get("/status")
async def get_bridges_status(request: Request) -> dict[str, Any]:
    """Get status of all bridges."""
    mgr = _get_manager(request)
    return mgr.get_status()


@router.get("/{bridge}/status")
async def get_bridge_status(bridge: str, request: Request) -> dict[str, Any]:
    """Get status of a specific bridge."""
    mgr = _get_manager(request)
    status = mgr.get_bridge_status(bridge)
    if not status:
        raise HTTPException(404, f"Bridge '{bridge}' not found")
    return status


@router.post("/execute")
async def execute_bridge(body: BridgeExecuteRequest, request: Request) -> dict[str, Any]:
    """Execute a bridge action."""
    mgr = _get_manager(request)
    result = await mgr.execute(body.bridge, body.action, body.params)
    return result


@router.get("/history")
async def get_call_history(request: Request, limit: int = 50) -> dict[str, Any]:
    """Get bridge call history."""
    mgr = _get_manager(request)
    history = mgr.get_call_history(limit)
    return {"calls": history, "total": len(history)}


@router.post("/{bridge}/health")
async def check_bridge_health(bridge: str, request: Request) -> dict[str, Any]:
    """Run health check on a bridge."""
    mgr = _get_manager(request)
    result = await mgr.execute(bridge, "health", {})
    return result


@router.get("/enabled")
async def get_enabled_bridges(request: Request) -> dict[str, Any]:
    """List enabled bridges."""
    mgr = _get_manager(request)
    status = mgr.get_status()
    enabled = {k: v for k, v in status["bridges"].items() if v["enabled"]}
    return {"enabled": enabled, "total": len(enabled)}


@router.post("/resend/send")
async def send_email(request: Request, body: dict[str, Any]) -> dict[str, Any]:
    """Convenience: Send email via Resend."""
    mgr = _get_manager(request)
    result = await mgr.execute("resend", "send_email", body)
    return result


@router.post("/instantly/campaigns")
async def list_instantly_campaigns(request: Request) -> dict[str, Any]:
    """Convenience: List Instantly campaigns."""
    mgr = _get_manager(request)
    result = await mgr.execute("instantly", "list_campaigns", {"limit": 20})
    return result
