"""
NemoClaw Execution Engine — Self-Build Router (E-7b)

6 endpoints for build plan tracking, self-build orchestration, code reviews.

NEW FILE: command-center/backend/app/api/routers/self_build.py
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from app.auth import require_auth

logger = logging.getLogger("cc.api.selfbuild")

router = APIRouter(tags=["self-build"], dependencies=[Depends(require_auth)])


def _svc(request: Request, attr: str, name: str):
    svc = getattr(request.app.state, attr, None)
    if svc is None:
        raise HTTPException(503, f"{name} not initialized")
    return svc


class SelfBuildRequest(BaseModel):
    task: str = ""
    phase_id: str = ""


# ── Build Plan ─────────────────────────────────────────────────────────

@router.get("/api/engine/build-plan")
async def get_build_plan(request: Request) -> dict[str, Any]:
    """Full build plan with status and failure data per phase."""
    tracker = _svc(request, "build_plan_tracker", "BuildPlanTracker")
    return {
        "plan": tracker.get_plan(),
        "progress": tracker.get_progress(),
    }


@router.get("/api/engine/build-plan/current")
async def get_current_phase(request: Request) -> dict[str, Any]:
    """Current phase details + exit criteria + failure memory."""
    tracker = _svc(request, "build_plan_tracker", "BuildPlanTracker")
    current = tracker.get_current_phase()
    if not current:
        return {"status": "all_complete", "message": "All phases complete"}
    return current


@router.post("/api/engine/build-plan/advance")
async def advance_build_plan(request: Request) -> dict[str, Any]:
    """Manually advance to next phase (marks current as complete)."""
    tracker = _svc(request, "build_plan_tracker", "BuildPlanTracker")
    current = tracker.get_current_phase()
    if not current:
        raise HTTPException(400, "No phase to advance")

    import subprocess
    commit = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True,
        cwd=str(request.app.state.build_plan_tracker.persist_path.parent.parent)
    ).stdout.strip() or "unknown"

    result = tracker.mark_complete(current["id"], commit)
    return result


# ── Self-Build ─────────────────────────────────────────────────────────

@router.post("/api/engine/self-build/start")
async def start_self_build(body: SelfBuildRequest, request: Request) -> dict[str, Any]:
    """Trigger autonomous build cycle for current or specified phase."""
    tracker = _svc(request, "build_plan_tracker", "BuildPlanTracker")
    codegen = _svc(request, "code_generation_service", "CodeGenerationService")
    reviewer = _svc(request, "code_review_service", "CodeReviewService")
    deployer = _svc(request, "deploy_service", "DeployService")

    current = tracker.get_current_phase()
    if not current:
        return {"status": "all_complete"}

    if current.get("blocked"):
        return {
            "status": "blocked",
            "phase": current["id"],
            "failures": current.get("failures", 0),
            "common_issue": current.get("common_issue"),
        }

    # Phase-specific task
    task = body.task or f"Build {current['name']} (phase {current['id']})"

    # Actually run the self-build loop (Fix #1)
    asyncio.create_task(_run_self_build_cycle(
        tracker=tracker,
        codegen=codegen,
        reviewer=reviewer,
        deployer=deployer,
        phase=current,
        task=task,
    ))

    return {
        "status": "started",
        "phase": current["id"],
        "task": task,
        "message": "Self-build cycle running. Monitor via /api/engine/self-build/status",
    }


async def _run_self_build_cycle(tracker, codegen, reviewer, deployer, phase, task):
    """The actual autonomous build loop."""
    phase_id = phase["id"]
    logger.info("Self-build cycle started for %s", phase_id)

    # Kill switch check (Fix #10)
    if getattr(tracker, "_self_build_killed", False):
        logger.warning("Self-build killed — aborting")
        return

    try:
        # Step 1: Generate code + tests
        job = await codegen.generate(
            task=task,
            target_files=[f"app/services/{phase_id.lower().replace('-','_')}_service.py"],
            context=f"Phase {phase_id}: {phase['name']}",
        )

        # Wait for generation
        for _ in range(120):
            j = codegen.get_job(job.job_id)
            if j and j.status in ("completed", "failed"):
                break
            await asyncio.sleep(2)

        if not job.generated_code:
            tracker.record_failure(phase_id, "Code generation produced no output")
            return

        # Step 2: Review (5 layers)
        review = await reviewer.review(job)

        if review.overall_verdict != "approved":
            tracker.record_failure(phase_id, f"Review rejected: {review.blocking_issues}")
            return

        # Step 3: Deploy (staging → canary → commit)
        deploy = await deployer.deploy(
            description=f"{phase_id}: {task}",
            files=job.generated_code,
            tests=job.generated_tests,
        )

        if deploy.status == "complete":
            tracker.mark_complete(phase_id, deploy.commit_hash or "unknown")
            logger.info("Self-build cycle COMPLETE for %s", phase_id)
        else:
            tracker.record_failure(phase_id, f"Deploy failed: {deploy.error}")

    except Exception as e:
        tracker.record_failure(phase_id, str(e))
        logger.error("Self-build cycle failed for %s: %s", phase_id, e)


@router.get("/api/engine/self-build/status")
async def get_self_build_status(request: Request) -> dict[str, Any]:
    """Self-build progress: codegen jobs, reviews, deploys."""
    codegen = _svc(request, "code_generation_service", "CodeGenerationService")
    reviewer = _svc(request, "code_review_service", "CodeReviewService")
    deployer = _svc(request, "deploy_service", "DeployService")

    return {
        "codegen_jobs": codegen.list_jobs(),
        "reviews": reviewer.get_reviews(),
        "deploys": deployer.get_deploys(),
    }


# ── Code Reviews ───────────────────────────────────────────────────────

@router.get("/api/engine/code-reviews")
async def get_code_reviews(request: Request) -> dict[str, Any]:
    """Code review history."""
    reviewer = _svc(request, "code_review_service", "CodeReviewService")
    reviews = reviewer.get_reviews()
    return {"reviews": reviews, "total": len(reviews)}
