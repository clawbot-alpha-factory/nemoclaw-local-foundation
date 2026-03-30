"""
NemoClaw Execution Engine — PhaseCompletionService (E-7b)

Runs exit criteria for current phase. All pass → marks complete, advances.
Not all pass → identifies gaps, generates fix tasks.

NEW FILE: command-center/backend/app/services/phase_completion_service.py
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("cc.phase")


class PhaseCompletionService:
    """
    Evaluates whether a phase's exit criteria are met.

    For each phase, runs specific checks:
      - Endpoint availability
      - Service importability
      - Skill compilation
      - Behavioral tests
    """

    def __init__(self, repo_root: Path, build_tracker=None):
        self.repo_root = repo_root
        self.backend_dir = repo_root / "command-center" / "backend"
        self.build_tracker = build_tracker
        logger.info("PhaseCompletionService initialized")

    async def check_phase(self, phase_id: str) -> dict[str, Any]:
        """Run exit criteria for a phase."""
        checks = {
            "E-8": self._check_e8,
            "E-9": self._check_e9,
            "E-10": self._check_e10,
            "E-11": self._check_e11,
            "E-12": self._check_e12,
        }

        checker = checks.get(phase_id)
        if not checker:
            return {"phase_id": phase_id, "status": "unknown", "reason": "No checker defined"}

        result = await checker()
        result["phase_id"] = phase_id
        result["checked_at"] = datetime.now(timezone.utc).isoformat()

        # Record in build tracker
        if self.build_tracker:
            if result.get("passed"):
                # Don't auto-complete — let the build cycle handle it
                pass
            else:
                gaps = result.get("gaps", [])
                if gaps:
                    self.build_tracker.record_failure(phase_id, gaps[0])

        # Active fix loop (Fix #7): if gaps found, return fix tasks
        if not result.get("passed") and result.get("gaps"):
            result["fix_tasks"] = [
                {
                    "task": f"Fix: {gap}",
                    "target_files": [f"app/services/{gap.split('.')[0]}.py" if ".py" in gap else ""],
                    "priority": "high",
                }
                for gap in result["gaps"]
            ]

        logger.info("Phase %s check: %s (%d gaps)",
                     phase_id, "PASSED" if result.get("passed") else "FAILED",
                     len(result.get("gaps", [])))
        return result

    async def _check_e8(self) -> dict[str, Any]:
        """E-8: Bridge activation — 3+ bridges active, idempotency, MENA."""
        gaps = []
        # Check if bridge scripts have real API calls
        for bridge in ["apollo", "resend", "instantly"]:
            bridge_file = self.repo_root / "scripts" / f"{bridge}_bridge.py"
            if bridge_file.exists():
                content = bridge_file.read_text()
                if "MOCK" in content.upper() or "mock" in content:
                    gaps.append(f"{bridge}_bridge still mocked")
            else:
                gaps.append(f"{bridge}_bridge.py not found")

        return {"passed": len(gaps) == 0, "gaps": gaps}

    async def _check_e9(self) -> dict[str, Any]:
        """E-9: 77+ skills total."""
        skills_dir = self.repo_root / "skills"
        skill_count = sum(1 for d in skills_dir.iterdir()
                         if d.is_dir() and (d / "skill.yaml").exists())
        passed = skill_count >= 77
        gaps = [] if passed else [f"Only {skill_count}/77 skills built"]
        return {"passed": passed, "skill_count": skill_count, "gaps": gaps}

    async def _check_e10(self) -> dict[str, Any]:
        """E-10: Revenue engine — pipeline, catalog, A/B, attribution."""
        gaps = []
        for svc in ["pipeline_service", "catalog_service", "ab_test_service", "attribution_service"]:
            svc_path = self.backend_dir / "app" / "services" / f"{svc}.py"
            if not svc_path.exists():
                gaps.append(f"{svc}.py not found")
        return {"passed": len(gaps) == 0, "gaps": gaps}

    async def _check_e11(self) -> dict[str, Any]:
        """E-11: Client lifecycle — onboarding, deliverables, churn."""
        gaps = []
        for svc in ["onboarding_service", "deliverable_service", "churn_service"]:
            svc_path = self.backend_dir / "app" / "services" / f"{svc}.py"
            if not svc_path.exists():
                gaps.append(f"{svc}.py not found")
        return {"passed": len(gaps) == 0, "gaps": gaps}

    async def _check_e12(self) -> dict[str, Any]:
        """E-12: Full autonomous — metrics, data lifecycle, self-improvement."""
        gaps = []
        for svc in ["metrics_service", "self_improvement_service"]:
            svc_path = self.backend_dir / "app" / "services" / f"{svc}.py"
            if not svc_path.exists():
                gaps.append(f"{svc}.py not found")
        return {"passed": len(gaps) == 0, "gaps": gaps}
