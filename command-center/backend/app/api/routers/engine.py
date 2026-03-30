"""
NemoClaw Execution Engine — Engine Router (E-4a)

10 endpoints for agent loops, memory, scheduling, checkpoints, shutdown.

NEW FILE: command-center/backend/app/api/routers/engine.py
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger("cc.api.engine")

router = APIRouter(tags=["engine"])


def _get_loop_service(request: Request):
    svc = getattr(request.app.state, "agent_loop_service", None)
    if svc is None:
        raise HTTPException(503, "AgentLoopService not initialized")
    return svc


def _get_memory(request: Request):
    svc = getattr(request.app.state, "agent_memory_service", None)
    if svc is None:
        raise HTTPException(503, "AgentMemoryService not initialized")
    return svc


def _get_scheduler(request: Request):
    svc = getattr(request.app.state, "scheduler_service", None)
    if svc is None:
        raise HTTPException(503, "SchedulerService not initialized")
    return svc


def _get_checkpoint(request: Request):
    svc = getattr(request.app.state, "checkpoint_service", None)
    if svc is None:
        raise HTTPException(503, "CheckpointService not initialized")
    return svc


# ── Agent Loop Control ─────────────────────────────────────────────────


@router.post("/api/agents/{agent_id}/start")
async def start_agent(agent_id: str, request: Request) -> dict[str, Any]:
    """Start an agent's execution loop."""
    svc = _get_loop_service(request)
    result = await svc.start_agent(agent_id)
    if not result.get("success"):
        raise HTTPException(400, result)
    return result


@router.post("/api/agents/{agent_id}/stop")
async def stop_agent(agent_id: str, request: Request) -> dict[str, Any]:
    """Stop an agent's execution loop."""
    svc = _get_loop_service(request)
    result = await svc.stop_agent(agent_id)
    if not result.get("success"):
        raise HTTPException(400, result)
    return result


@router.get("/api/agents/{agent_id}/loop-status")
async def get_loop_status(agent_id: str, request: Request) -> dict[str, Any]:
    """Get agent loop status."""
    svc = _get_loop_service(request)
    status = svc.get_loop_status(agent_id)
    if status is None:
        return {"agent_id": agent_id, "state": "not_started", "message": "Loop not initialized"}
    return status


@router.get("/api/agents/{agent_id}/memory")
async def get_agent_memory(agent_id: str, request: Request) -> dict[str, Any]:
    """Get agent's learned lessons."""
    svc = _get_memory(request)
    lessons = svc.get_top_lessons(agent_id, limit=20)
    return {"agent_id": agent_id, "lessons": lessons, "total": len(lessons)}


@router.get("/api/agents/{agent_id}/schedule")
async def get_agent_schedule(agent_id: str, request: Request) -> dict[str, Any]:
    """Get agent's scheduled tasks."""
    svc = _get_scheduler(request)
    schedule = svc.get_agent_schedule(agent_id)
    return {"agent_id": agent_id, "schedule": schedule, "total": len(schedule)}


# ── Bulk Operations ────────────────────────────────────────────────────


@router.post("/api/agents/start-all")
async def start_all_agents(request: Request) -> dict[str, Any]:
    """Start all eligible agent loops."""
    svc = _get_loop_service(request)
    results = await svc.start_all()
    return {"results": results}


@router.post("/api/agents/stop-all")
async def stop_all_agents(request: Request) -> dict[str, Any]:
    """Stop all running agent loops."""
    svc = _get_loop_service(request)
    results = await svc.stop_all()
    return {"results": results}


# ── Engine Status ──────────────────────────────────────────────────────


@router.get("/api/engine/status")
async def get_engine_status(request: Request) -> dict[str, Any]:
    """Full engine status: loops + execution."""
    svc = _get_loop_service(request)
    return svc.get_engine_status()


@router.get("/api/engine/checkpoints")
async def get_checkpoints(request: Request) -> dict[str, Any]:
    """List all saved checkpoints."""
    svc = _get_checkpoint(request)
    checkpoints = svc.list_checkpoints()
    return {"checkpoints": checkpoints, "total": len(checkpoints)}


@router.post("/api/engine/shutdown")
async def engine_shutdown(request: Request) -> dict[str, Any]:
    """Emergency shutdown — stop all agents and execution."""
    svc = _get_loop_service(request)
    result = await svc.shutdown()
    return result
