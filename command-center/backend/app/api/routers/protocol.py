"""
NemoClaw Execution Engine — Protocol Router (E-4b)

10 endpoints for protocol messaging, workspace, debate, knowledge base.

NEW FILE: command-center/backend/app/api/routers/protocol.py
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger("cc.api.protocol")

router = APIRouter(tags=["protocol"])


# ── Request Models ─────────────────────────────────────────────────────

class SendMessageRequest(BaseModel):
    sender: str
    receiver: str
    intent: str
    content: str
    data: dict[str, Any] | None = None
    evidence: str | None = None
    trace_id: str = ""

class WorkspaceWriteRequest(BaseModel):
    key: str
    value: Any
    agent_id: str = ""

class DebateStartRequest(BaseModel):
    topic: str
    agent_a: str
    agent_b: str
    trace_id: str = ""

class KBAddRequest(BaseModel):
    key: str
    value: str
    category: str = "general"
    added_by: str = ""


# ── Helpers ────────────────────────────────────────────────────────────

def _get_protocol(request: Request):
    svc = getattr(request.app.state, "protocol_service", None)
    if svc is None:
        raise HTTPException(503, "AgentProtocolService not initialized")
    return svc

def _get_workspace(request: Request):
    svc = getattr(request.app.state, "workspace_service", None)
    if svc is None:
        raise HTTPException(503, "WorkspaceService not initialized")
    return svc

def _get_debate(request: Request):
    svc = getattr(request.app.state, "debate_service", None)
    if svc is None:
        raise HTTPException(503, "DebateService not initialized")
    return svc

def _get_kb(request: Request):
    svc = getattr(request.app.state, "knowledge_base_service", None)
    if svc is None:
        raise HTTPException(503, "KnowledgeBaseService not initialized")
    return svc

def _get_feedback(request: Request):
    svc = getattr(request.app.state, "feedback_loop_service", None)
    if svc is None:
        raise HTTPException(503, "FeedbackLoopService not initialized")
    return svc


# ── Protocol Messaging ─────────────────────────────────────────────────

@router.post("/api/protocol/send")
async def send_message(body: SendMessageRequest, request: Request) -> dict[str, Any]:
    """Send a protocol message between agents."""
    svc = _get_protocol(request)
    result = svc.send(**body.model_dump())
    if not result.get("success"):
        raise HTTPException(400, result)
    return result

@router.get("/api/protocol/inbox/{agent_id}")
async def get_inbox(agent_id: str, request: Request) -> dict[str, Any]:
    """Get protocol inbox for an agent."""
    svc = _get_protocol(request)
    msgs = svc.get_inbox(agent_id)
    return {"agent_id": agent_id, "messages": msgs, "total": len(msgs)}

@router.get("/api/protocol/history")
async def get_protocol_history(request: Request) -> dict[str, Any]:
    """Get all protocol message history."""
    svc = _get_protocol(request)
    history = svc.get_history()
    return {"messages": history, "total": len(history)}

@router.get("/api/protocol/feedback-loops")
async def get_feedback_loops(request: Request) -> dict[str, Any]:
    """Get all defined feedback loops."""
    svc = _get_feedback(request)
    loops = svc.get_loops()
    return {"loops": loops, "total": len(loops)}


# ── Workspace ──────────────────────────────────────────────────────────

@router.post("/api/workspace/{workflow_id}/write")
async def workspace_write(
    workflow_id: str, body: WorkspaceWriteRequest, request: Request
) -> dict[str, Any]:
    """Write to a workflow workspace."""
    svc = _get_workspace(request)
    return svc.write(workflow_id, body.key, body.value, body.agent_id)

@router.get("/api/workspace/{workflow_id}/read")
async def workspace_read(workflow_id: str, request: Request, namespace: str = "") -> dict[str, Any]:
    """Read from a workflow workspace. Optional namespace filter."""
    svc = _get_workspace(request)
    data = svc.read_all(workflow_id, namespace=namespace)
    return {"workflow_id": workflow_id, "data": data, "namespace": namespace or "all"}


# ── Debate ─────────────────────────────────────────────────────────────

@router.post("/api/debate/start")
async def start_debate(body: DebateStartRequest, request: Request) -> dict[str, Any]:
    """Start a structured debate between two agents."""
    svc = _get_debate(request)
    debate = svc.start_debate(**body.model_dump())
    return debate.to_dict()

@router.get("/api/debate/{debate_id}")
async def get_debate(debate_id: str, request: Request) -> dict[str, Any]:
    """Get debate status and rounds."""
    svc = _get_debate(request)
    debate = svc.get_debate(debate_id)
    if not debate:
        raise HTTPException(404, "Debate not found")
    return debate


# ── Knowledge Base ─────────────────────────────────────────────────────

@router.get("/api/knowledge-base")
async def get_knowledge_base(request: Request) -> dict[str, Any]:
    """Get all knowledge base entries."""
    svc = _get_kb(request)
    entries = svc.get_all()
    return {"entries": entries, "total": len(entries)}

@router.post("/api/knowledge-base")
async def add_knowledge(body: KBAddRequest, request: Request) -> dict[str, Any]:
    """Add a knowledge base entry."""
    svc = _get_kb(request)
    entry = svc.add(**body.model_dump())
    return entry
