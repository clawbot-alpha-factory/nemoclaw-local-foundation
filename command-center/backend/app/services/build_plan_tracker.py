"""
NemoClaw Execution Engine — BuildPlanTracker (E-7b)

Tracks the 15-phase build plan. Knows which phases are complete,
identifies next phase, reports blockers. Failure memory (#4):
stores failure count + common issues per phase for adaptive prioritization.

NEW FILE: command-center/backend/app/services/build_plan_tracker.py
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("cc.buildplan")


# ── The 15-Phase Plan ──────────────────────────────────────────────────

PHASES = [
    {"id": "E-1", "name": "Fix Stale Infrastructure", "status": "complete", "commit": "f092733"},
    {"id": "E-2", "name": "Execution Engine", "status": "complete", "commit": "8f6588e"},
    {"id": "E-3", "name": "Orchestrator + Projects", "status": "complete", "commit": "e35cd3e"},
    {"id": "E-4a", "name": "Agent Runtime", "status": "complete", "commit": "b877031"},
    {"id": "E-4b", "name": "Agent Collaboration", "status": "complete", "commit": "29e32e3"},
    {"id": "E-4c", "name": "Enterprise Operations", "status": "complete", "commit": "8ec9fef"},
    {"id": "E-5", "name": "Skill Factory", "status": "complete", "commit": "e4f1c43"},
    {"id": "E-6", "name": "Build 15 Skills", "status": "complete", "commit": "ad61f09"},
    {"id": "E-7", "name": "Regression & Quality Gate", "status": "complete", "commit": "e357b4c"},
    {"id": "E-7b", "name": "Self-Build Engine", "status": "in_progress", "commit": None},
    {"id": "E-8", "name": "Bridge Activation", "status": "not_started", "commit": None},
    {"id": "E-9", "name": "Tier 3-5 Skills", "status": "not_started", "commit": None},
    {"id": "E-10", "name": "Revenue Engine", "status": "not_started", "commit": None},
    {"id": "E-11", "name": "Client Lifecycle", "status": "not_started", "commit": None},
    {"id": "E-12", "name": "Full Autonomous Operation", "status": "not_started", "commit": None},
]


class BuildPlanTracker:
    """
    Tracks build plan progress with failure memory.

    Failure memory: stores per-phase failure count + common issues.
    Prioritizes fixes before advancing to next phase.
    """

    MAX_ATTEMPTS_PER_PHASE = 3
    COOLDOWN_MINUTES = 10

    def __init__(self, persist_path: Path | None = None):
        self.persist_path = persist_path or (Path.home() / ".nemoclaw" / "build-plan-state.json")
        self.persist_path.parent.mkdir(parents=True, exist_ok=True)
        self.phases = [dict(p) for p in PHASES]
        self.failure_memory: dict[str, dict[str, Any]] = {}
        self._self_build_killed: bool = False
        self._load()
        logger.info("BuildPlanTracker initialized (%d phases)", len(self.phases))

    def _load(self):
        if self.persist_path.exists():
            try:
                data = json.loads(self.persist_path.read_text())
                # Merge saved status into phases
                saved_phases = {p["id"]: p for p in data.get("phases", [])}
                for phase in self.phases:
                    if phase["id"] in saved_phases:
                        saved = saved_phases[phase["id"]]
                        phase["status"] = saved.get("status", phase["status"])
                        phase["commit"] = saved.get("commit", phase["commit"])
                self.failure_memory = data.get("failure_memory", {})
            except (json.JSONDecodeError, OSError):
                pass

    def _save(self):
        data = {
            "phases": self.phases,
            "failure_memory": self.failure_memory,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.persist_path.write_text(json.dumps(data, indent=2, default=str))

    def get_plan(self) -> list[dict[str, Any]]:
        """Get full plan with failure data."""
        result = []
        for p in self.phases:
            entry = dict(p)
            fm = self.failure_memory.get(p["id"], {})
            entry["failures"] = fm.get("count", 0)
            entry["last_failure"] = fm.get("last_failure", None)
            entry["common_issue"] = fm.get("common_issue", None)
            result.append(entry)
        return result

    def get_current_phase(self) -> dict[str, Any] | None:
        """Get the first non-complete phase."""
        for p in self.phases:
            if p["status"] != "complete":
                fm = self.failure_memory.get(p["id"], {})
                return {
                    **p,
                    "failures": fm.get("count", 0),
                    "common_issue": fm.get("common_issue", None),
                    "blocked": fm.get("count", 0) >= self.MAX_ATTEMPTS_PER_PHASE,
                }
        return None

    def get_next_phase(self) -> dict[str, Any] | None:
        """Get next phase after current."""
        found_current = False
        for p in self.phases:
            if found_current and p["status"] == "not_started":
                return p
            if p["status"] != "complete":
                found_current = True
        return None

    def mark_complete(self, phase_id: str, commit: str) -> dict[str, Any]:
        """Mark a phase as complete."""
        for p in self.phases:
            if p["id"] == phase_id:
                p["status"] = "complete"
                p["commit"] = commit
                self._save()
                logger.info("Phase %s marked complete (commit: %s)", phase_id, commit)
                return {"success": True, "phase": p}
        return {"success": False, "reason": f"Phase {phase_id} not found"}

    def record_failure(self, phase_id: str, issue: str) -> dict[str, Any]:
        """Record a failure for adaptive learning."""
        if phase_id not in self.failure_memory:
            self.failure_memory[phase_id] = {"count": 0, "issues": []}

        fm = self.failure_memory[phase_id]
        fm["count"] = fm.get("count", 0) + 1
        fm["last_failure"] = datetime.now(timezone.utc).isoformat()
        fm["issues"] = fm.get("issues", [])
        fm["issues"].append({"issue": issue, "timestamp": fm["last_failure"]})
        # Keep last 10 issues
        fm["issues"] = fm["issues"][-10:]
        # Most common issue
        issue_texts = [i["issue"] for i in fm["issues"]]
        fm["common_issue"] = max(set(issue_texts), key=issue_texts.count) if issue_texts else None

        self._save()

        blocked = fm["count"] >= self.MAX_ATTEMPTS_PER_PHASE
        if blocked:
            logger.warning("Phase %s BLOCKED after %d failures", phase_id, fm["count"])

        return {
            "phase_id": phase_id,
            "failure_count": fm["count"],
            "blocked": blocked,
            "common_issue": fm["common_issue"],
            "cooldown_minutes": self.COOLDOWN_MINUTES if not blocked else None,
        }

    def kill_self_build(self) -> dict[str, Any]:
        """Emergency kill switch for autonomous loop (Fix #10)."""
        self._self_build_killed = True
        self._save()
        logger.warning("SELF-BUILD KILLED")
        return {"killed": True, "timestamp": datetime.now(timezone.utc).isoformat()}

    def resume_self_build(self) -> dict[str, Any]:
        """Resume autonomous loop."""
        self._self_build_killed = False
        self._save()
        logger.info("Self-build resumed")
        return {"killed": False}

    def get_progress(self) -> dict[str, Any]:
        """Get overall progress summary."""
        complete = sum(1 for p in self.phases if p["status"] == "complete")
        total = len(self.phases)
        return {
            "complete": complete,
            "total": total,
            "progress_pct": round(complete / total * 100, 1),
            "current_phase": self.get_current_phase(),
            "total_failures": sum(fm.get("count", 0) for fm in self.failure_memory.values()),
        }
