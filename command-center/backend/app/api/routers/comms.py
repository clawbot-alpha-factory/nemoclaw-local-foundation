"""
Communications Router (CC-3)

REST API for the messaging system:
  GET  /api/comms/lanes              — list all lanes
  GET  /api/comms/lanes/{id}         — get lane details
  GET  /api/comms/lanes/{id}/messages — get messages for a lane
  POST /api/comms/lanes/{id}/send    — send a message (+ agent response for DM/group)
  POST /api/comms/lanes/{id}/read    — mark lane as read
  GET  /api/comms/agents             — list available agents
  GET  /api/comms/stats              — message store statistics

NEW FILE: command-center/backend/app/routers/comms.py
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth import require_auth
from app.domain.comms_models import (
    LaneListResponse,
    MessageListResponse,
    MessageType,
    SendMessageRequest,
    SenderType,
)

logger = logging.getLogger("cc.comms")

router = APIRouter(prefix="/api/comms", tags=["comms"])


def _get_store(request: Request):
    """Get MessageStore from app state."""
    store = getattr(request.app.state, "message_store", None)
    if not store:
        raise HTTPException(status_code=503, detail="MessageStore not initialized")
    return store


def _get_agent_service(request: Request):
    """Get AgentChatService from app state."""
    service = getattr(request.app.state, "agent_chat_service", None)
    if not service:
        raise HTTPException(status_code=503, detail="AgentChatService not initialized")
    return service


def _get_ws_manager(request: Request):
    """Get WebSocketManager from app state."""
    return getattr(request.app.state, "ws_manager", None)


def _get_task_dispatch(request: Request):
    """Get TaskDispatchService from app state."""
    return getattr(request.app.state, "task_dispatch_service", None)


# ------------------------------------------------------------------
# Lanes
# ------------------------------------------------------------------


@router.get("/lanes", dependencies=[Depends(require_auth)])
async def list_lanes(request: Request) -> LaneListResponse:
    """List all communication lanes."""
    store = _get_store(request)
    lanes = store.get_lanes()
    return LaneListResponse(lanes=lanes, total=len(lanes))


@router.get("/lanes/{lane_id}", dependencies=[Depends(require_auth)])
async def get_lane(lane_id: str, request: Request):
    """Get a specific lane."""
    store = _get_store(request)
    lane = store.get_lane(lane_id)
    if not lane:
        raise HTTPException(status_code=404, detail=f"Lane not found: {lane_id}")
    return lane


# ------------------------------------------------------------------
# Messages
# ------------------------------------------------------------------


@router.get("/lanes/{lane_id}/messages", dependencies=[Depends(require_auth)])
async def get_messages(
    lane_id: str,
    request: Request,
    limit: int = 50,
    before: Optional[str] = None,
) -> MessageListResponse:
    """Get messages for a lane, paginated."""
    store = _get_store(request)

    if not store.get_lane(lane_id):
        raise HTTPException(status_code=404, detail=f"Lane not found: {lane_id}")

    before_dt = None
    if before:
        try:
            before_dt = datetime.fromisoformat(before)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid 'before' datetime")

    messages = store.get_messages(lane_id, limit=limit, before=before_dt)
    total_in_lane = len(store._lane_index.get(lane_id, []))

    return MessageListResponse(
        messages=messages,
        lane_id=lane_id,
        total=total_in_lane,
        has_more=total_in_lane > len(messages),
    )


@router.post("/lanes/{lane_id}/send", dependencies=[Depends(require_auth)])
async def send_message(
    lane_id: str,
    body: SendMessageRequest,
    request: Request,
):
    """Send a message to a lane.

    For DM and group lanes, automatically triggers an agent response.
    For system/broadcast lanes, just stores the message.
    """
    store = _get_store(request)
    agent_service = _get_agent_service(request)
    ws_manager = _get_ws_manager(request)

    lane = store.get_lane(lane_id)
    if not lane:
        raise HTTPException(status_code=404, detail=f"Lane not found: {lane_id}")

    # Validate message content
    if not body.content or len(body.content.strip()) < 5:
        raise HTTPException(status_code=400, detail="Message must be at least 5 characters")

    # Audit: tag user messages with manual trigger
    user_metadata = {**body.metadata, "trigger": "manual", "source": "human"}

    # Store user message
    user_msg = store.add_message(
        lane_id=lane_id,
        sender_id="user",
        sender_name="Khaled",
        sender_type=SenderType.USER,
        content=body.content,
        message_type=body.message_type,
        reply_to=body.reply_to,
        metadata=user_metadata,
    )

    if not user_msg:
        raise HTTPException(status_code=500, detail="Failed to store message")

    # Broadcast user message via WS
    if ws_manager:
        await ws_manager.broadcast_chat_message(user_msg.to_ws_payload())

    response_data = {"user_message": user_msg.model_dump(mode="json")}

    # Task dispatch: if message_type is "task", dispatch to the agent
    if body.message_type == MessageType.TASK:
        dispatch_svc = _get_task_dispatch(request)
        if dispatch_svc and lane.participants:
            target_agent = lane.participants[0] if lane.lane_type == "dm" else None
            if target_agent:
                dispatch_result = await dispatch_svc.dispatch_task(
                    agent_id=target_agent,
                    goal=body.content,
                    source="comms",
                    project_id=body.metadata.get("project_id"),
                )
                response_data["dispatch"] = dispatch_result
                response_data["workflow_id"] = dispatch_result.get("workflow_id")

    # Trigger agent response(s) for DM and group/broadcast lanes
    if lane.lane_type in ("dm", "group", "broadcast") and lane.participants:
        try:
            if lane.lane_type == "dm":
                # DM: single agent responds
                responders = [lane.participants[0]]
            elif lane.lane_type == "broadcast":
                # All-hands: ALL participants respond (each agent speaks)
                responders = list(lane.participants)
            else:
                # Group: pick most relevant agent
                picked = await agent_service.select_relevant_agent(
                    body.content, lane.participants
                )
                responders = [picked] if picked else []

            agent_messages = []
            for responder_id in responders:
                if not responder_id:
                    continue
                agent = agent_service.get_agent(responder_id)
                if not agent:
                    continue

                # Get context messages for the agent
                context = store.get_context_messages(lane_id)

                # Generate agent response
                agent_response = await agent_service.generate_response(
                    agent_id=responder_id,
                    user_message=body.content,
                    context_messages=context,
                )

                if agent_response:
                    agent_metadata = {
                        "trigger": "auto",
                        "source": "agent",
                        "responding_to": user_msg.id,
                    }

                    agent_msg = store.add_message(
                        lane_id=lane_id,
                        sender_id=responder_id,
                        sender_name=agent.display_name,
                        sender_type=SenderType.AGENT,
                        content=agent_response,
                        message_type=MessageType.CHAT,
                        metadata=agent_metadata,
                    )

                    if agent_msg and ws_manager:
                        await ws_manager.broadcast_chat_message(
                            agent_msg.to_ws_payload()
                        )

                    agent_messages.append(agent_msg)

            response_data["agent_messages"] = [
                m.model_dump(mode="json") for m in agent_messages if m
            ]
            if agent_messages:
                response_data["agent_message"] = agent_messages[0].model_dump(mode="json")
                first_agent = agent_service.get_agent(responders[0])
                response_data["responder"] = {
                    "id": first_agent.id if first_agent else responders[0],
                    "name": first_agent.display_name if first_agent else responders[0],
                    "role": first_agent.role if first_agent else "",
                        }

        except Exception as e:
            logger.error("Agent response failed in lane %s: %s", lane_id, e)
            response_data["agent_error"] = str(e)[:200]

    return response_data


@router.post("/lanes/{lane_id}/read", dependencies=[Depends(require_auth)])
async def mark_lane_read(lane_id: str, request: Request):
    """Mark a lane as read (reset unread count)."""
    store = _get_store(request)
    if not store.get_lane(lane_id):
        raise HTTPException(status_code=404, detail=f"Lane not found: {lane_id}")
    store.mark_lane_read(lane_id)
    return {"status": "ok", "lane_id": lane_id}


# ------------------------------------------------------------------
# Agents
# ------------------------------------------------------------------


@router.get("/agents", dependencies=[Depends(require_auth)])
async def list_agents(request: Request):
    """List all available agents for chat."""
    agent_service = _get_agent_service(request)
    return {
        "agents": agent_service.list_agents(),
        "available": agent_service.is_available,
    }


# ------------------------------------------------------------------
# Stats
# ------------------------------------------------------------------


@router.get("/stats", dependencies=[Depends(require_auth)])
async def comms_stats(request: Request):
    """Get message store statistics."""
    store = _get_store(request)
    return store.stats()
