"""
NemoClaw Execution Engine — Skill Factory Router (E-5)

7 endpoints for skill generation, approval, patterns.

NEW FILE: command-center/backend/app/api/routers/skill_factory.py
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger("cc.api.factory")

router = APIRouter(prefix="/api/skill-factory", tags=["skill-factory"])


class GenerateRequest(BaseModel):
    concept: str
    language: str = "en"


class ApproveRequest(BaseModel):
    approved_by: str


class RejectRequest(BaseModel):
    rejected_by: str
    reason: str = ""


def _get_factory(request: Request):
    svc = getattr(request.app.state, "skill_factory_service", None)
    if svc is None:
        raise HTTPException(503, "SkillFactoryService not initialized")
    return svc


@router.post("/generate")
async def generate_skill(body: GenerateRequest, request: Request) -> dict[str, Any]:
    """Submit a skill concept for generation."""
    svc = _get_factory(request)
    job = await svc.generate(body.concept, body.language)
    return job.to_dict()


@router.get("/queue")
async def get_queue(request: Request) -> dict[str, Any]:
    """List all factory jobs."""
    svc = _get_factory(request)
    jobs = svc.get_queue()
    return {"jobs": jobs, "total": len(jobs)}


@router.get("/stats")
async def get_stats(request: Request) -> dict[str, Any]:
    """Factory statistics."""
    svc = _get_factory(request)
    return svc.get_stats()


@router.get("/patterns")
async def get_patterns(request: Request) -> dict[str, Any]:
    """Get loaded pattern library."""
    svc = _get_factory(request)
    patterns = svc.get_patterns()
    return {"patterns": patterns, "total": len(patterns)}


@router.get("/{job_id}")
async def get_job(job_id: str, request: Request) -> dict[str, Any]:
    """Get a specific factory job."""
    svc = _get_factory(request)
    job = svc.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job.to_dict()


@router.post("/{job_id}/approve")
async def approve_job(job_id: str, body: ApproveRequest, request: Request) -> dict[str, Any]:
    """Approve a generated skill."""
    svc = _get_factory(request)
    result = svc.approve(job_id, body.approved_by)
    if not result.get("success"):
        raise HTTPException(400, result)
    return result


@router.post("/{job_id}/reject")
async def reject_job(job_id: str, body: RejectRequest, request: Request) -> dict[str, Any]:
    """Reject a generated skill."""
    svc = _get_factory(request)
    result = svc.reject(job_id, body.rejected_by, body.reason)
    if not result.get("success"):
        raise HTTPException(400, result)
    return result
