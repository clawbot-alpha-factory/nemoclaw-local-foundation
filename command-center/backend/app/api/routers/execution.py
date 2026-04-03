"""
NemoClaw Execution Engine — Execution Router (E-2)

9 endpoints for skill execution, chains, and dead letter queue.

NEW FILE: command-center/backend/app/api/routers/execution.py
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from app.auth import require_auth

from app.domain.engine_models import (
    ChainRequest,
    ExecutionRequest,
    LLMTier,
)

logger = logging.getLogger("cc.api.execution")

router = APIRouter(prefix="/api/execution", tags=["execution"], dependencies=[Depends(require_auth)])


def _get_execution_service(request: Request):
    svc = getattr(request.app.state, "execution_service", None)
    if svc is None:
        raise HTTPException(503, "ExecutionService not initialized")
    return svc


def _get_chain_runner(request: Request):
    runner = getattr(request.app.state, "chain_runner", None)
    if runner is None:
        raise HTTPException(503, "SkillChainRunner not initialized")
    return runner


# ── Skill Execution ───────────────────────────────────────────────────


@router.post("/run")
async def submit_execution(body: ExecutionRequest, request: Request) -> dict[str, Any]:
    """Submit a skill for execution."""
    svc = _get_execution_service(request)
    execution = svc.submit(body)
    return {
        "execution_id": execution.execution_id,
        "skill_id": execution.skill_id,
        "status": execution.status.value,
        "tier": execution.tier.value,
        "queued_at": execution.queued_at.isoformat(),
    }


@router.get("/queue")
async def get_queue(request: Request) -> dict[str, Any]:
    """Get current execution queue."""
    svc = _get_execution_service(request)
    queue = svc.get_queue()
    active = svc.get_active()
    return {
        "queued": [e.model_dump() for e in queue],
        "active": [e.model_dump() for e in active],
        "total_queued": len(queue),
        "total_active": len(active),
    }


@router.get("/history")
async def get_history(request: Request, limit: int = 50) -> dict[str, Any]:
    """Get execution history."""
    svc = _get_execution_service(request)
    history = svc.get_history(limit=limit)
    return {
        "executions": [e.model_dump() for e in history],
        "total": len(history),
    }


@router.get("/status")
async def get_engine_status(request: Request) -> dict[str, Any]:
    """Get overall engine status."""
    svc = _get_execution_service(request)
    state = svc.get_state()
    return state.model_dump()




# ── Observability ─────────────────────────────────────────────────────


def _get_circuit_breaker(request: Request):
    cb = getattr(request.app.state, "circuit_breaker", None)
    if cb is None:
        raise HTTPException(503, "CircuitBreaker not initialized")
    return cb


def _get_skill_metrics(request: Request):
    sm = getattr(request.app.state, "skill_metrics", None)
    if sm is None:
        raise HTTPException(503, "SkillMetrics not initialized")
    return sm


@router.get("/circuit-breakers")
async def get_circuit_breakers(request: Request) -> dict[str, Any]:
    """Get circuit breaker states for all tracked skills."""
    cb = _get_circuit_breaker(request)
    return {"states": cb.get_all_states(), "stats": cb.get_stats()}


@router.get("/skill-metrics")
async def get_skill_metrics(request: Request) -> dict[str, Any]:
    """Get aggregated skill execution metrics."""
    sm = _get_skill_metrics(request)
    return sm.get_all_stats()


# ── Dead Letter Queue ─────────────────────────────────────────────────


@router.get("/dead-letter")
async def get_dead_letter(request: Request) -> dict[str, Any]:
    """Get dead letter queue — executions that failed after max retries."""
    svc = _get_execution_service(request)
    entries = svc.get_dead_letter()
    return {
        "entries": [e.model_dump() for e in entries],
        "total": len(entries),
    }


@router.get("/{execution_id}")
async def get_execution(execution_id: str, request: Request) -> dict[str, Any]:
    """Get a specific execution by ID."""
    svc = _get_execution_service(request)
    execution = svc.get_execution(execution_id)
    if execution is None:
        raise HTTPException(404, f"Execution {execution_id} not found")
    return execution.model_dump()


@router.post("/{execution_id}/cancel")
async def cancel_execution(execution_id: str, request: Request) -> dict[str, Any]:
    """Cancel a queued execution."""
    svc = _get_execution_service(request)
    success = svc.cancel(execution_id)
    if not success:
        raise HTTPException(404, "Execution not found or not cancellable")
    return {"cancelled": True, "execution_id": execution_id}


# ── Skill Chains ──────────────────────────────────────────────────────


@router.post("/chain/run")
async def submit_chain(body: ChainRequest, request: Request) -> dict[str, Any]:
    """Submit a skill chain for execution."""
    runner = _get_chain_runner(request)
    chain = runner.submit_chain(body)
    return {
        "chain_id": chain.chain_id,
        "steps": len(chain.steps),
        "status": chain.status.value,
        "skills": [s.skill_id for s in chain.steps],
    }


@router.get("/chain/{chain_id}")
async def get_chain(chain_id: str, request: Request) -> dict[str, Any]:
    """Get chain execution status."""
    runner = _get_chain_runner(request)
    chain = runner.get_chain(chain_id)
    if chain is None:
        raise HTTPException(404, f"Chain {chain_id} not found")
    return chain.model_dump()

