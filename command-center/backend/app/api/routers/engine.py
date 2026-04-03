"""
NemoClaw Execution Engine — Engine Router (E-4a)

10 endpoints for agent loops, memory, scheduling, checkpoints, shutdown.

NEW FILE: command-center/backend/app/api/routers/engine.py
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from app.auth import require_auth

logger = logging.getLogger("cc.api.engine")

router = APIRouter(tags=["engine"], dependencies=[Depends(require_auth)])


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


# ── Time-Travel Debugging ─────────────────────────────────────────────

@router.get("/api/engine/checkpoints/{agent_id}")
async def get_agent_checkpoint(agent_id: str, request: Request) -> dict[str, Any]:
    """Get full checkpoint data for an agent — state, ticks, tasks, cost."""
    svc = _get_checkpoint(request)
    data = svc.load(agent_id)
    if not data:
        raise HTTPException(404, f"No checkpoint for agent {agent_id}")
    return {"agent_id": agent_id, "checkpoint": data}


@router.get("/api/engine/checkpoints/{agent_id}/history")
async def get_agent_checkpoint_history(agent_id: str, request: Request) -> dict[str, Any]:
    """Get checkpoint history with work log entries for timeline view."""
    svc = _get_checkpoint(request)
    data = svc.load(agent_id)

    # Gather work log history for this agent
    import os
    from pathlib import Path
    log_dir = Path.home() / ".nemoclaw" / "work-logs" / agent_id
    history = []
    if log_dir.is_dir():
        for log_file in sorted(log_dir.glob("*.jsonl"), reverse=True)[:7]:  # last 7 days
            import json as _json
            try:
                entries = []
                for line in log_file.read_text().strip().split("\n"):
                    if line.strip():
                        try:
                            entries.append(_json.loads(line))
                        except _json.JSONDecodeError:
                            pass
                history.append({
                    "date": log_file.stem,
                    "entries": entries[-20:],  # last 20 per day
                    "total_entries": len(entries),
                })
            except Exception:
                pass

    return {
        "agent_id": agent_id,
        "current_checkpoint": data,
        "work_history": history,
        "history_days": len(history),
    }


@router.post("/api/engine/checkpoints/{agent_id}/restore")
async def restore_agent_checkpoint(agent_id: str, request: Request) -> dict[str, Any]:
    """Restore an agent to its last checkpoint state (stop → reload → start)."""
    loop_svc = _get_loop_service(request)
    checkpoint_svc = _get_checkpoint(request)

    # Load checkpoint
    data = checkpoint_svc.load(agent_id)
    if not data:
        raise HTTPException(404, f"No checkpoint for agent {agent_id}")

    # Stop agent if running
    stop_result = await loop_svc.stop_agent(agent_id)

    # Restart with restored state
    start_result = await loop_svc.start_agent(agent_id)

    return {
        "agent_id": agent_id,
        "restored_from": data.get("_checkpoint_time"),
        "restored_ticks": data.get("ticks", 0),
        "stop_result": stop_result,
        "start_result": start_result,
    }


@router.get("/api/engine/skill-checkpoints")
async def get_skill_checkpoints(request: Request) -> dict[str, Any]:
    """List LangGraph skill execution checkpoints from SQLite DB."""
    from pathlib import Path
    import sqlite3

    db_path = Path.home() / ".nemoclaw" / "checkpoints" / "langgraph.db"
    bak_path = Path.home() / ".nemoclaw" / "checkpoints" / "langgraph.db.bak"

    # Try active DB first, fall back to backup
    target = db_path if db_path.exists() and db_path.stat().st_size > 0 else bak_path

    if not target.exists() or target.stat().st_size == 0:
        return {"threads": [], "total_checkpoints": 0, "db": str(target), "status": "empty"}

    try:
        conn = sqlite3.connect(str(target))
        cursor = conn.cursor()

        # Get threads with checkpoint counts
        cursor.execute("""
            SELECT thread_id,
                   COUNT(*) as checkpoint_count,
                   MIN(checkpoint_id) as first_checkpoint,
                   MAX(checkpoint_id) as last_checkpoint
            FROM checkpoints
            GROUP BY thread_id
            ORDER BY MAX(rowid) DESC
            LIMIT 50
        """)
        threads = []
        for row in cursor.fetchall():
            threads.append({
                "thread_id": row[0],
                "checkpoint_count": row[1],
                "first_checkpoint": row[2],
                "last_checkpoint": row[3],
            })

        # Total count
        cursor.execute("SELECT COUNT(*) FROM checkpoints")
        total = cursor.fetchone()[0]

        conn.close()
        return {
            "threads": threads,
            "total_checkpoints": total,
            "db": str(target),
            "status": "active",
        }
    except Exception as e:
        return {"threads": [], "total_checkpoints": 0, "error": str(e), "status": "error"}


@router.get("/api/engine/skill-checkpoints/{thread_id}")
async def get_skill_checkpoint_chain(thread_id: str, request: Request) -> dict[str, Any]:
    """Get the checkpoint chain for a specific skill execution thread."""
    from pathlib import Path
    import sqlite3

    db_path = Path.home() / ".nemoclaw" / "checkpoints" / "langgraph.db"
    bak_path = Path.home() / ".nemoclaw" / "checkpoints" / "langgraph.db.bak"
    target = db_path if db_path.exists() and db_path.stat().st_size > 0 else bak_path

    if not target.exists() or target.stat().st_size == 0:
        raise HTTPException(404, "No checkpoint database found")

    try:
        conn = sqlite3.connect(str(target))
        cursor = conn.cursor()

        cursor.execute("""
            SELECT checkpoint_id, parent_checkpoint_id, type
            FROM checkpoints
            WHERE thread_id = ?
            ORDER BY rowid ASC
        """, (thread_id,))

        chain = []
        for row in cursor.fetchall():
            chain.append({
                "checkpoint_id": row[0],
                "parent_id": row[1],
                "type": row[2],
                "step": len(chain) + 1,
            })

        conn.close()

        if not chain:
            raise HTTPException(404, f"No checkpoints for thread {thread_id}")

        return {
            "thread_id": thread_id,
            "chain": chain,
            "total_steps": len(chain),
            "can_replay": True,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/api/engine/shutdown")
async def engine_shutdown(request: Request) -> dict[str, Any]:
    """Emergency shutdown — stop all agents and execution."""
    svc = _get_loop_service(request)
    result = await svc.shutdown()
    return result
