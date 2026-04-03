"""
NemoClaw Command Center — Brain API Router
Endpoints for AI Brain interaction and status.

Endpoints:
  POST /api/brain/ask      — Ask a question (auth required)
  POST /api/brain/analyze   — Trigger immediate system analysis (auth required)
  GET  /api/brain/status    — Brain availability status (no auth)
  GET  /api/brain/history   — Get conversation history (auth required)
  POST /api/brain/clear     — Clear conversation history (auth required)
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.auth import require_auth

router = APIRouter(prefix="/api/brain", tags=["brain"], dependencies=[Depends(require_auth)])

# Injected at startup via set_dependencies()
_brain_service = None
_state_aggregator = None
_auth_dependency = None


def set_dependencies(brain_service, state_aggregator, auth_dependency=None):
    """Called from main.py during app startup to inject dependencies."""
    global _brain_service, _state_aggregator, _auth_dependency
    _brain_service = brain_service
    _state_aggregator = state_aggregator
    _auth_dependency = auth_dependency


# ------------------------------------------------------------------
# Request / Response models
# ------------------------------------------------------------------

class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    role: str
    content: str
    timestamp: str
    type: str  # "response" | "error"


class InsightResponse(BaseModel):
    content: str
    timestamp: str
    type: str  # "insight"
    available: bool


class BrainStatusResponse(BaseModel):
    available: bool
    provider: str
    model: str
    alias: str
    history_length: int


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------

@router.post("/ask", response_model=AskResponse)
async def ask_brain(request: AskRequest):
    """Ask the AI Brain a question about system state."""
    if not _brain_service:
        raise HTTPException(status_code=503, detail="Brain service not initialized")
    if not _state_aggregator:
        raise HTTPException(status_code=503, detail="State aggregator not available")

    # Get current system state as dict
    state = _state_aggregator.state
    state_dict = state.model_dump() if hasattr(state, "model_dump") else state.dict()

    result = await _brain_service.ask(request.question, state_dict)
    return AskResponse(**result)


@router.post("/analyze", response_model=InsightResponse)
async def analyze_state():
    """Trigger an immediate strategic system analysis."""
    if not _brain_service:
        raise HTTPException(status_code=503, detail="Brain service not initialized")
    if not _state_aggregator:
        raise HTTPException(status_code=503, detail="State aggregator not available")

    state = _state_aggregator.state
    state_dict = state.model_dump() if hasattr(state, "model_dump") else state.dict()

    result = await _brain_service.generate_insight(state_dict)
    return InsightResponse(**result)


@router.get("/status", response_model=BrainStatusResponse)
async def brain_status():
    """Get Brain service status. No auth required (like health endpoints)."""
    if not _brain_service:
        return BrainStatusResponse(
            available=False,
            provider="not initialized",
            model="none",
            alias="none",
            history_length=0,
        )

    info = _brain_service.provider_info
    return BrainStatusResponse(
        available=info["available"],
        provider=info["provider"],
        model=info["model"],
        alias=info["alias"],
        history_length=len(_brain_service.get_history()),
    )


@router.get("/history")
async def get_history():
    """Get Brain conversation history for current session."""
    if not _brain_service:
        return {"messages": []}
    return {"messages": _brain_service.get_history()}


@router.post("/clear")
async def clear_history():
    """Clear Brain conversation history."""
    if _brain_service:
        _brain_service.clear_history()
    return {"status": "cleared", "message": "Conversation history cleared"}
