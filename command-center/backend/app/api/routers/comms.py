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
import uuid
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


def _get_execution_service(request: Request):
    """Get ExecutionService from app state."""
    return getattr(request.app.state, "execution_service", None)


def _get_project_service(request: Request):
    """Get ProjectService from app state."""
    return getattr(request.app.state, "project_service", None)


def _get_notification_service(request: Request):
    """Get AgentNotificationService from app state."""
    return getattr(request.app.state, "notification_service", None)


async def _maybe_trigger_team_review(
    request: Request,
    lane_id: str,
    responder_id: str,
    agent_msg,
    dispatch_result: dict | None,
) -> None:
    """If this DM response belongs to a collaboration-worthy task, auto-post to team channel and trigger peer review."""
    try:
        # Guard: don't trigger reviews from within team channels (prevents recursion)
        if lane_id.startswith("team-"):
            return

        # Find team_lane_id from dispatch result (same request cycle)
        team_lane_id = None
        if dispatch_result:
            team_lane_id = dispatch_result.get("team_lane_id")

        # Fallback: look up via agent_loop_service workflow channels
        if not team_lane_id:
            loop_svc = getattr(request.app.state, "agent_loop_service", None)
            if loop_svc and dispatch_result:
                wf_id = dispatch_result.get("workflow_id", "")
                if wf_id:
                    team_lane_id = loop_svc._workflow_channels.get(wf_id)

        if not team_lane_id:
            return

        store = getattr(request.app.state, "message_store", None)
        agent_service = getattr(request.app.state, "agent_chat_service", None)
        if not store or not agent_service:
            return

        # Post response summary to team channel
        from app.services.agent_notification_service import AGENT_NAMES
        display = AGENT_NAMES.get(responder_id, responder_id)
        summary = agent_msg.content[:500] if agent_msg else ""
        if not summary:
            return

        store.add_message(
            lane_id=team_lane_id,
            sender_id=responder_id,
            sender_name=display,
            sender_type=SenderType.AGENT,
            content=f"**Response from {display}:**\n\n{summary}",
            message_type=MessageType.CHAT,
            metadata={"auto_review": True, "source_lane": lane_id},
        )

        # Trigger peer review
        await agent_service.trigger_peer_review(
            lane_id=team_lane_id,
            agent_id=responder_id,
            deliverable_summary=summary,
            message_store=store,
        )

        # Broadcast team channel update via WebSocket
        ws_manager = getattr(request.app.state, "ws_manager", None)
        if ws_manager:
            lane = store.get_lane(team_lane_id)
            if lane and lane.last_message:
                await ws_manager.broadcast_chat_message(lane.last_message.to_ws_payload())

    except Exception as e:
        logger.warning("Team review trigger failed for %s: %s", lane_id, e)


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
    if not body.content or not body.content.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

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

    # ── Asana Sync: create task for agent-directed messages ──────────
    asana_bridge = getattr(request.app.state, "asana_bridge", None)
    if asana_bridge and lane.lane_type in ("dm", "group") and lane.participants:
        import asyncio as _aio
        async def _sync_to_asana():
            try:
                target = lane.participants[0] if lane.participants else "unknown"
                # Find or create the NemoClaw Operations project
                project_gid = getattr(request.app.state, "_asana_project_gid", None)
                if not project_gid:
                    # Search for existing project
                    ws = await asana_bridge.get_workspaces()
                    if ws:
                        workspace_gid = ws[0]["gid"]
                        project_gid = await asana_bridge.find_or_create_project(
                            workspace_gid, "NemoClaw Operations"
                        )
                        request.app.state._asana_project_gid = project_gid

                if project_gid:
                    task_name = body.content[:120] if body.content else "Agent task"
                    await asana_bridge.create_task(
                        project_gid=project_gid,
                        name=f"[{target}] {task_name}",
                        notes=f"Agent: {target}\nFull prompt:\n{body.content[:2000]}",
                        assignee_name=target,
                    )
                    logger.info("Asana: task created for %s in project %s", target, project_gid)
            except Exception as e:
                logger.warning("Asana sync failed (non-blocking): %s", e)
        _aio.ensure_future(_sync_to_asana())

    # ── Intent Classification ────────────────────────────────────────
    # Classify user intent via LLM before generating agent response
    intent_result = None
    responder_id = None
    if lane.lane_type == "dm" and lane.participants:
        responder_id = lane.participants[0]
    elif lane.lane_type == "group" and lane.participants:
        responder_id = lane.participants[0]

    try:
        from app.services.intent_classifier import classify_intent, Intent

        intent_result = await classify_intent(body.content, responder_id or "")
        response_data["intent"] = {
            "intent": intent_result.intent.value,
            "confidence": intent_result.confidence,
            "extracted_params": intent_result.extracted_params,
        }

        # Act on high-confidence intents (>= 0.6)
        if intent_result.confidence >= 0.6:
            params = intent_result.extracted_params

            if intent_result.intent == Intent.RUN_SKILL:
                exec_svc = _get_execution_service(request)
                skill_id = params.get("skill_id", "")
                if exec_svc and skill_id:
                    from app.domain.engine_models import ExecutionRequest, LLMTier
                    exec_req = ExecutionRequest(
                        skill_id=skill_id,
                        inputs={k: v for k, v in params.items() if k != "skill_id"},
                        agent_id=responder_id or "",
                        tier=LLMTier.STANDARD,
                    )
                    execution = exec_svc.submit(exec_req)
                    response_data["skill_dispatch"] = {
                        "execution_id": execution.execution_id,
                        "skill_id": skill_id,
                    }

            elif intent_result.intent == Intent.CREATE_PROJECT:
                proj_svc = _get_project_service(request)
                if proj_svc:
                    project = proj_svc.create_project(
                        name=params.get("project_name", "New Project"),
                        description=params.get("description", ""),
                        template=params.get("template"),
                    )
                    response_data["project_created"] = {
                        "id": project.get("id"),
                        "name": project.get("name"),
                    }

            elif intent_result.intent == Intent.CREATE_TEAM:
                notif_svc = _get_notification_service(request)
                if notif_svc:
                    task_name = params.get("task_name", body.content[:60])
                    suggested = params.get("suggested_agents", [])
                    # Use suggested agents or fallback to lane participants
                    team_agents = suggested if suggested else list(lane.participants or [])
                    lane_id = notif_svc.create_task_channel(
                        task_name=task_name,
                        agent_ids=team_agents,
                    )
                    response_data["team_channel"] = {"lane_id": lane_id, "agents": team_agents}

            elif intent_result.intent == Intent.RESEARCH:
                exec_svc = _get_execution_service(request)
                if exec_svc:
                    from app.domain.engine_models import ExecutionRequest, LLMTier
                    exec_req = ExecutionRequest(
                        skill_id="e12-market-research-analyst",
                        inputs={
                            "research_topic": params.get("topic", body.content),
                            "research_depth": params.get("depth", "standard"),
                        },
                        agent_id="strategy_lead",
                        tier=LLMTier.STANDARD,
                    )
                    execution = exec_svc.submit(exec_req)
                    response_data["research_dispatch"] = {
                        "execution_id": execution.execution_id,
                        "topic": params.get("topic", body.content[:100]),
                    }

            elif intent_result.intent == Intent.DELEGATE:
                # Override responder to delegated agent
                delegate_to = params.get("agent_id", "")
                if delegate_to:
                    responder_id = delegate_to

    except Exception as e:
        logger.warning("Intent classification skipped: %s", e)

    # Task dispatch: if message_type is "task", dispatch to the agent
    dispatch_result = None
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
            # If intent delegation picked a specific agent, use that
            if responder_id and intent_result and intent_result.intent.value == "delegate":
                responders = [responder_id]
            elif lane.lane_type == "dm":
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

                # Pre-generate message ID for streaming correlation
                msg_id = str(uuid.uuid4())
                full_text = ""
                had_error = False

                # Stream agent response via WebSocket chunks
                async for chunk, is_complete in agent_service.generate_response_stream(
                    agent_id=responder_id,
                    user_message=body.content,
                    context_messages=context,
                ):
                    if is_complete:
                        break
                    if chunk:
                        full_text += chunk
                        if ws_manager:
                            await ws_manager.broadcast_chat_chunk({
                                "message_id": msg_id,
                                "lane_id": lane_id,
                                "sender_id": responder_id,
                                "sender_name": agent.display_name,
                                "chunk": chunk,
                            })

                # Check for error in final chunk
                if full_text.startswith("[Error:"):
                    had_error = True

                agent_response = full_text if full_text else None

                if agent_response:
                    agent_metadata = {
                        "trigger": "auto",
                        "source": "agent",
                        "responding_to": user_msg.id,
                    }
                    if had_error:
                        agent_metadata["streaming_error"] = True

                    agent_msg = store.add_message(
                        lane_id=lane_id,
                        sender_id=responder_id,
                        sender_name=agent.display_name,
                        sender_type=SenderType.AGENT,
                        content=agent_response,
                        message_type=MessageType.CHAT,
                        metadata=agent_metadata,
                        message_id=msg_id,
                    )

                    if ws_manager:
                        # Signal stream complete
                        await ws_manager.broadcast_chat_complete({
                            "message_id": msg_id,
                            "lane_id": lane_id,
                            "sender_id": responder_id,
                            "full_content": agent_response,
                        })
                        # Also broadcast full message for clients not using streaming
                        if agent_msg:
                            await ws_manager.broadcast_chat_message(
                                agent_msg.to_ws_payload()
                            )

                    if agent_msg:
                        agent_messages.append(agent_msg)

                        # Auto-trigger team review for task dispatches
                        if dispatch_result and dispatch_result.get("team_lane_id"):
                            await _maybe_trigger_team_review(
                                request=request,
                                lane_id=lane_id,
                                responder_id=responder_id,
                                agent_msg=agent_msg,
                                dispatch_result=dispatch_result,
                            )

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
