"""A2A Protocol Router — Google A2A v1.0 endpoints"""
import asyncio, json, logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.auth import require_auth

logger = logging.getLogger("cc.a2a")

# Discovery endpoints are PUBLIC (per A2A spec)
discovery_router = APIRouter(tags=["a2a-discovery"])

# Task endpoints require auth
task_router = APIRouter(tags=["a2a"], dependencies=[Depends(require_auth)])


class TaskSubmission(BaseModel):
    agent_id: str
    goal: str
    metadata: dict[str, Any] | None = None


def _get_a2a(request: Request):
    svc = getattr(request.app.state, "a2a_service", None)
    if not svc:
        raise HTTPException(503, "A2A service not initialized")
    return svc


@discovery_router.get("/.well-known/agent-card.json")
async def get_all_agent_cards(request: Request):
    svc = _get_a2a(request)
    return svc.get_all_cards()


@discovery_router.get("/.well-known/agent-card/{agent_id}.json")
async def get_agent_card(agent_id: str, request: Request):
    svc = _get_a2a(request)
    card = svc.get_card(agent_id)
    if not card:
        raise HTTPException(404, f"Agent {agent_id} not found")
    return card


@task_router.post("/api/a2a/tasks")
async def submit_task(body: TaskSubmission, request: Request):
    svc = _get_a2a(request)
    task = await svc.submit_task(body.agent_id, body.goal, body.metadata)
    return task


@task_router.get("/api/a2a/tasks/{task_id}")
async def get_task(task_id: str, request: Request):
    svc = _get_a2a(request)
    task = svc.get_task(task_id)
    if not task:
        raise HTTPException(404, f"Task {task_id} not found")
    return task


@task_router.delete("/api/a2a/tasks/{task_id}")
async def cancel_task(task_id: str, request: Request):
    svc = _get_a2a(request)
    ok = svc.cancel_task(task_id)
    if not ok:
        raise HTTPException(404, f"Task {task_id} not found")
    return {"task_id": task_id, "status": "CANCELED"}


@task_router.get("/api/a2a/tasks/{task_id}/stream")
async def stream_task(task_id: str, request: Request):
    svc = _get_a2a(request)
    task = svc.get_task(task_id)
    if not task:
        raise HTTPException(404, f"Task {task_id} not found")

    async def event_generator():
        last_status = None
        for _ in range(300):  # max 5 min polling
            t = svc.get_task(task_id)
            if not t:
                yield f"event: error\ndata: {json.dumps({'error': 'Task not found'})}\n\n"
                return
            if t["status"] != last_status:
                last_status = t["status"]
                yield f"event: status\ndata: {json.dumps(t)}\n\n"
            if t["status"] in ("COMPLETED", "FAILED", "CANCELED"):
                yield f"event: done\ndata: {json.dumps(t)}\n\n"
                return
            await asyncio.sleep(1)
        yield f"event: timeout\ndata: {json.dumps({'error': 'Stream timeout'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
