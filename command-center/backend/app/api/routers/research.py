"""
NemoClaw Command Center — Research Router (E-14)

2 endpoints for pre-built research workflow templates.

POST /api/research/run       — run a research template
GET  /api/research/templates — list available templates

NEW FILE: command-center/backend/app/api/routers/research.py
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.domain.engine_models import LLMTier

logger = logging.getLogger("cc.api.research")

router = APIRouter(prefix="/api/research", tags=["research"])


# ── Request Models ───────────────────────────────────────────────────


class RunResearchRequest(BaseModel):
    """Body for POST /api/research/run."""

    template: str = Field(..., description="Template ID (e.g. social_intelligence)")
    inputs: dict[str, str] = Field(
        default_factory=dict,
        description="Key-value inputs for the template",
    )
    agent_id: str = Field(default="", description="Agent identity for tracing")
    tier: LLMTier | None = Field(
        default=None,
        description="Override default LLM tier",
    )


# ── Helpers ──────────────────────────────────────────────────────────


def _get_research_service(request: Request):
    svc = getattr(request.app.state, "research_service", None)
    if svc is None:
        raise HTTPException(503, "ResearchService not initialized")
    return svc


# ── Endpoints ────────────────────────────────────────────────────────


@router.get("/templates")
async def list_templates(request: Request) -> dict[str, Any]:
    """List all available research templates."""
    svc = _get_research_service(request)
    templates = svc.list_templates()
    return {"templates": templates, "count": len(templates)}


@router.post("/run")
async def run_research(body: RunResearchRequest, request: Request) -> dict[str, Any]:
    """Execute a research template as a skill chain."""
    svc = _get_research_service(request)
    try:
        result = svc.run(
            template_id=body.template,
            inputs=body.inputs,
            agent_id=body.agent_id,
            tier=body.tier,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return result
