"""
NemoClaw Execution Engine — Orchestrator Router (E-3)

10 endpoints for orchestration, lifecycle, and team formation.

NEW FILE: command-center/backend/app/api/routers/orchestrator.py
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from app.auth import require_auth

logger = logging.getLogger("cc.api.orchestrator")

router = APIRouter(tags=["orchestrator"])


# ── Request Models ─────────────────────────────────────────────────────


class PlanRequest(BaseModel):
    goal: str


class StageDataUpdate(BaseModel):
    field: str
    value: Any = True


class CreateProjectRequest(BaseModel):
    name: str
    description: str = ""
    project_type: str = "default"
    template: str | None = None


# ── Helpers ────────────────────────────────────────────────────────────


def _get_orchestrator(request: Request):
    svc = getattr(request.app.state, "orchestrator_service", None)
    if svc is None:
        raise HTTPException(503, "OrchestratorService not initialized")
    return svc


def _get_lifecycle(request: Request):
    svc = getattr(request.app.state, "lifecycle_service", None)
    if svc is None:
        raise HTTPException(503, "ProjectLifecycleService not initialized")
    return svc


def _get_team(request: Request):
    svc = getattr(request.app.state, "team_service", None)
    if svc is None:
        raise HTTPException(503, "TeamFormationService not initialized")
    return svc


def _get_multi(request: Request):
    svc = getattr(request.app.state, "multi_project_service", None)
    if svc is None:
        raise HTTPException(503, "MultiProjectService not initialized")
    return svc


def _get_task_workflow(request: Request):
    svc = getattr(request.app.state, "task_workflow_service", None)
    if svc is None:
        raise HTTPException(503, "TaskWorkflowService not initialized")
    return svc


# ── Orchestrator Endpoints ─────────────────────────────────────────────


@router.post("/api/orchestrator/plan", dependencies=[Depends(require_auth)])
async def create_plan(body: PlanRequest, request: Request) -> dict[str, Any]:
    """Decompose a goal into an executable plan with cost estimate."""
    svc = _get_orchestrator(request)
    workflow = await svc.create_plan(body.goal)
    return workflow.to_dict()


@router.post("/api/orchestrator/execute", dependencies=[Depends(require_auth)])
async def execute_plan(request: Request, workflow_id: str = "") -> dict[str, Any]:
    """Approve and execute a planned workflow."""
    svc = _get_orchestrator(request)
    exec_svc = getattr(request.app.state, "execution_service", None)
    workflow = await svc.execute_workflow(workflow_id, exec_svc)
    if not workflow:
        raise HTTPException(404, f"Workflow {workflow_id} not found")
    return workflow.to_dict()


@router.get("/api/orchestrator/workflows", dependencies=[Depends(require_auth)])
async def list_workflows(request: Request) -> dict[str, Any]:
    """List all workflows (scanned from disk + in-memory)."""
    svc = _get_task_workflow(request)
    workflows = svc.list_workflows()
    return {"workflows": workflows, "total": len(workflows)}


@router.get("/api/orchestrator/{workflow_id}", dependencies=[Depends(require_auth)])
async def get_workflow(workflow_id: str, request: Request) -> dict[str, Any]:
    """Get a specific workflow."""
    svc = _get_task_workflow(request)
    wf = svc.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(404, f"Workflow {workflow_id} not found")
    return wf


@router.get("/api/orchestrator/{workflow_id}/artifacts", dependencies=[Depends(require_auth)])
async def list_artifacts(workflow_id: str, request: Request) -> dict[str, Any]:
    """List artifact files for a workflow."""
    svc = _get_task_workflow(request)
    files = svc.list_artifacts(workflow_id)
    if not files:
        raise HTTPException(404, f"No artifacts found for workflow {workflow_id}")
    return {"workflow_id": workflow_id, "files": files}


@router.get("/api/orchestrator/{workflow_id}/artifacts/{filename}", dependencies=[Depends(require_auth)])
async def get_artifact(workflow_id: str, filename: str, request: Request):
    """Serve a workflow artifact file as text."""
    svc = _get_task_workflow(request)
    content = svc.get_artifact(workflow_id, filename)
    if content is None:
        raise HTTPException(404, f"Artifact {filename} not found in workflow {workflow_id}")
    media = "application/json" if filename.endswith(".json") else "text/markdown"
    return PlainTextResponse(content, media_type=media)


@router.post("/api/orchestrator/{workflow_id}/cancel", dependencies=[Depends(require_auth)])
async def cancel_workflow(workflow_id: str, request: Request) -> dict[str, Any]:
    """Cancel a workflow."""
    svc = _get_orchestrator(request)
    success = svc.cancel_workflow(workflow_id)
    if not success:
        raise HTTPException(404, "Workflow not found or not cancellable")
    return {"cancelled": True, "workflow_id": workflow_id}


# ── Lifecycle Endpoints ────────────────────────────────────────────────


@router.post("/api/projects/create-with-lifecycle", dependencies=[Depends(require_auth)])
async def create_project_with_lifecycle(
    body: CreateProjectRequest, request: Request
) -> dict[str, Any]:
    """Create a project and initialize its lifecycle."""
    proj_svc = getattr(request.app.state, "project_service", None)
    if not proj_svc:
        raise HTTPException(503, "ProjectService not initialized")

    lifecycle_svc = _get_lifecycle(request)
    team_svc = _get_team(request)

    # Form team
    team = team_svc.form_team(body.project_type)

    # Create project
    project = proj_svc.create_project(
        name=body.name,
        description=body.description,
        assigned_agents=team["all_agents"],
        tags=[body.project_type],
        template=body.template,
    )

    # Initialize lifecycle
    lifecycle = lifecycle_svc.initialize_lifecycle(project["id"])

    return {
        "project": project,
        "lifecycle": lifecycle,
        "team": team,
    }


@router.get("/api/projects/{project_id}/lifecycle", dependencies=[Depends(require_auth)])
async def get_project_lifecycle(
    project_id: str, request: Request
) -> dict[str, Any]:
    """Get lifecycle state for a project."""
    svc = _get_lifecycle(request)
    lifecycle = svc.get_lifecycle(project_id)
    if not lifecycle:
        raise HTTPException(404, "Project or lifecycle not found")
    return lifecycle


@router.post("/api/projects/{project_id}/advance-stage", dependencies=[Depends(require_auth)])
async def advance_project_stage(
    project_id: str, request: Request, force: bool = False
) -> dict[str, Any]:
    """Advance project to next lifecycle stage (with gate check)."""
    svc = _get_lifecycle(request)
    result = svc.advance_stage(project_id, force=force)
    if not result.get("success"):
        raise HTTPException(400, result)
    return result


@router.get("/api/orchestrator/projects/active", dependencies=[Depends(require_auth)])
async def get_active_with_allocation(request: Request) -> dict[str, Any]:
    """Get active projects with resource allocation data."""
    multi = _get_multi(request)
    active = multi.get_active_projects()
    contention = multi.get_resource_contention()
    return {
        "projects": active,
        "contention": contention,
    }


@router.get("/api/projects/{project_id}/team", dependencies=[Depends(require_auth)])
async def get_project_team(
    project_id: str, request: Request
) -> dict[str, Any]:
    """Get team composition for a project."""
    proj_svc = getattr(request.app.state, "project_service", None)
    if not proj_svc:
        raise HTTPException(503, "ProjectService not initialized")

    project = proj_svc.get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    team_svc = _get_team(request)
    team = team_svc.get_team_for_project(project)
    return {"project_id": project_id, "team": team}
