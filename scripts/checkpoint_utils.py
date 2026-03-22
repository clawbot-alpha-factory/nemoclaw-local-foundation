#!/usr/bin/env python3
"""
NemoClaw Checkpoint Utilities
Shared module for checkpoint creation, updates, pause/resume logic.
Imported by budget-enforcer.py and checkpoint-manager.py.
"""

import json
import os
import uuid
from datetime import datetime, timezone

LOCAL_CHECKPOINT_DIR  = os.path.expanduser("~/.nemoclaw/checkpoints")
REPO_CHECKPOINT_DIR   = os.path.expanduser("~/nemoclaw-local-foundation/checkpoints")

def _ensure_dirs():
    os.makedirs(LOCAL_CHECKPOINT_DIR, exist_ok=True)
    os.makedirs(REPO_CHECKPOINT_DIR, exist_ok=True)

def _local_path(workflow_id):
    return os.path.join(LOCAL_CHECKPOINT_DIR, f"{workflow_id}.json")

def _summary_path(workflow_id):
    return os.path.join(REPO_CHECKPOINT_DIR, f"{workflow_id}-summary.json")

def generate_workflow_id(prefix="wf"):
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    uid = str(uuid.uuid4())[:8]
    return f"{prefix}-{ts}-{uid}"

def create(workflow_id, phase, steps):
    """Create a new checkpoint. steps = list of step name strings."""
    _ensure_dirs()
    now = datetime.now(timezone.utc).isoformat()
    data = {
        "workflow_id":      workflow_id,
        "created_at":       now,
        "updated_at":       now,
        "status":           "running",
        "current_phase":    phase,
        "current_step":     steps[0] if steps else None,
        "completed_steps":  [],
        "pending_steps":    steps[:],
        "files_created":    [],
        "files_updated":    [],
        "provider_used":    None,
        "cumulative_spend_usd": {"anthropic": 0.0, "openai": 0.0},
        "resume_point":     {"step": steps[0] if steps else None, "instruction": ""},
        "pause_reason":     None,
        "pause_triggered_at": None,
    }
    _write_local(workflow_id, data)
    _write_summary(workflow_id, data)
    return data

def load(workflow_id):
    path = _local_path(workflow_id)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)

def complete_step(workflow_id, step, files_created=None, files_updated=None, provider=None, spend=None):
    """Mark a step as complete. Call after each atomic step finishes."""
    data = load(workflow_id)
    if not data:
        raise FileNotFoundError(f"Checkpoint {workflow_id} not found")

    if step not in data["completed_steps"]:
        data["completed_steps"].append(step)
    if step in data["pending_steps"]:
        data["pending_steps"].remove(step)

    if files_created:
        data["files_created"].extend(files_created)
    if files_updated:
        data["files_updated"].extend(files_updated)
    if provider:
        data["provider_used"] = provider
    if spend:
        for k, v in spend.items():
            data["cumulative_spend_usd"][k] = v

    next_step = data["pending_steps"][0] if data["pending_steps"] else None
    data["current_step"] = next_step
    data["resume_point"] = {"step": next_step, "instruction": f"Resume from step: {next_step}"}
    data["updated_at"] = datetime.now(timezone.utc).isoformat()

    if not data["pending_steps"]:
        data["status"] = "completed"

    _write_local(workflow_id, data)
    _write_summary(workflow_id, data)
    return data

def pause(workflow_id, reason, instruction=""):
    """Pause workflow due to budget or manual trigger."""
    data = load(workflow_id)
    if not data:
        raise FileNotFoundError(f"Checkpoint {workflow_id} not found")

    now = datetime.now(timezone.utc).isoformat()
    data["status"] = reason  # paused_budget_warning or paused_budget_exhausted
    data["pause_reason"] = reason
    data["pause_triggered_at"] = now
    data["updated_at"] = now
    if instruction:
        data["resume_point"]["instruction"] = instruction

    _write_local(workflow_id, data)
    _write_summary(workflow_id, data)
    return data

def resume(workflow_id):
    """Load checkpoint and return resume instructions."""
    data = load(workflow_id)
    if not data:
        return None, "Checkpoint not found"

    if data["status"] == "completed":
        return data, "Workflow already completed — nothing to resume"

    # Verify files still exist
    missing = [f for f in data["files_created"] if not os.path.exists(os.path.expanduser(f"~/nemoclaw-local-foundation/{f}"))]
    if missing:
        return data, f"CORRUPTED STATE — files missing: {missing}"

    return data, None

def is_step_done(workflow_id, step):
    """Check if a step was already completed — used for idempotency."""
    data = load(workflow_id)
    if not data:
        return False
    return step in data["completed_steps"]

def list_checkpoints():
    _ensure_dirs()
    files = [f for f in os.listdir(LOCAL_CHECKPOINT_DIR) if f.endswith(".json")]
    results = []
    for f in sorted(files):
        try:
            with open(os.path.join(LOCAL_CHECKPOINT_DIR, f)) as fh:
                d = json.load(fh)
            results.append({
                "workflow_id": d["workflow_id"],
                "status":      d["status"],
                "phase":       d["current_phase"],
                "step":        d["current_step"],
                "updated_at":  d["updated_at"],
            })
        except Exception:
            pass
    return results

def _write_local(workflow_id, data):
    _ensure_dirs()
    tmp = _local_path(workflow_id) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, _local_path(workflow_id))

def _write_summary(workflow_id, data):
    _ensure_dirs()
    summary = {
        "workflow_id":     data["workflow_id"],
        "updated_at":      data["updated_at"],
        "status":          data["status"],
        "current_phase":   data["current_phase"],
        "current_step":    data["current_step"],
        "completed_steps": data["completed_steps"],
        "pending_steps":   data["pending_steps"],
        "files_created":   data["files_created"],
        "pause_reason":    data["pause_reason"],
        "resume_point":    data["resume_point"],
    }
    tmp = _summary_path(workflow_id) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(summary, f, indent=2)
    os.replace(tmp, _summary_path(workflow_id))
