"""
NemoClaw Execution Engine — Infrastructure Router

Endpoints for task queue and rate limiter management.

NEW FILE: command-center/backend/app/api/routers/infrastructure.py
"""
from __future__ import annotations
import logging
from typing import Any
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger("cc.api.infra")
router = APIRouter(prefix="/api/infra", tags=["infrastructure"])

def _svc(request, attr):
    svc = getattr(request.app.state, attr, None)
    if svc is None:
        raise HTTPException(503, f"{attr} not initialized")
    return svc

class EnqueueRequest(BaseModel):
    task_id: str
    task_type: str
    payload: dict[str, Any] = {}
    priority: int = 0

@router.get("/queue/status")
async def get_queue_status(request: Request) -> dict[str, Any]:
    return _svc(request, "task_queue").get_status()

@router.post("/queue/enqueue")
async def enqueue_task(body: EnqueueRequest, request: Request) -> dict[str, Any]:
    return _svc(request, "task_queue").enqueue(body.task_id, body.task_type, body.payload, body.priority)

@router.get("/queue/dead-letter")
async def get_dead_letter(request: Request) -> dict[str, Any]:
    return {"tasks": _svc(request, "task_queue").get_dead_letter()}

@router.post("/queue/dead-letter/{task_id}/retry")
async def retry_dead_letter(task_id: str, request: Request) -> dict[str, Any]:
    return _svc(request, "task_queue").retry_dead_letter(task_id)

@router.get("/rate-limits")
async def get_rate_limits(request: Request) -> dict[str, Any]:
    return _svc(request, "rate_limiter").get_stats()
