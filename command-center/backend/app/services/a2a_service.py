"""A2A Protocol Service — Agent Cards + Task Lifecycle (Google A2A v1.0)"""
import json, logging, yaml
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger("cc.a2a")

REPO = Path(__file__).resolve().parents[4]
AGENT_SCHEMA = REPO / "config" / "agents" / "agent-schema.yaml"
CAPABILITY_REGISTRY = REPO / "config" / "agents" / "capability-registry.yaml"

class A2AService:
    def __init__(self, agent_loop_service=None, task_workflow_service=None):
        self.agent_loop_service = agent_loop_service
        self.task_workflow_service = task_workflow_service
        self._cards: list[dict] = []
        self._tasks: dict[str, dict] = {}
        self._load_agent_cards()

    def _load_agent_cards(self):
        agents = {}
        if AGENT_SCHEMA.exists():
            data = yaml.safe_load(AGENT_SCHEMA.read_text())
            raw_agents = data.get("agents", [])
            if isinstance(raw_agents, list):
                for a in raw_agents:
                    if isinstance(a, dict):
                        aid = a.get("agent_id", a.get("id", ""))
                        if aid:
                            agents[aid] = a
            elif isinstance(raw_agents, dict):
                for aid, ainfo in raw_agents.items():
                    if isinstance(ainfo, dict):
                        ainfo["agent_id"] = aid
                        agents[aid] = ainfo

        skills_map = {}
        if CAPABILITY_REGISTRY.exists():
            data = yaml.safe_load(CAPABILITY_REGISTRY.read_text())
            for cap in data.get("capabilities", []):
                if not isinstance(cap, dict):
                    continue
                owner = cap.get("owned_by", "")
                skill = cap.get("skill", "")
                if owner and skill:
                    skills_map.setdefault(owner, []).append(skill)

        self._cards = []
        for aid, agent in agents.items():
            self._cards.append({
                "name": agent.get("display_name", agent.get("name", aid)),
                "description": agent.get("role", agent.get("title", "")),
                "url": "https://nemoclaw-local-foundation-production.up.railway.app",
                "version": "1.0.0",
                "capabilities": {
                    "skills": skills_map.get(aid, []),
                    "streaming": True,
                },
                "defaultInputModes": ["text/plain"],
                "defaultOutputModes": ["text/plain", "application/json"],
                "authentication": {"schemes": ["bearer"]},
                "_agent_id": aid,
                "_authority_level": agent.get("authority_level", 4),
                "_domains": agent.get("domains", []),
            })
        logger.info("A2A: loaded %d agent cards", len(self._cards))

    def get_all_cards(self) -> list[dict]:
        return self._cards

    def get_card(self, agent_id: str) -> Optional[dict]:
        for c in self._cards:
            if c.get("_agent_id") == agent_id:
                return c
        return None

    async def submit_task(self, agent_id: str, goal: str, metadata: dict = None) -> dict:
        import uuid
        task_id = f"a2a-{uuid.uuid4().hex[:12]}"
        task = {
            "task_id": task_id,
            "agent_id": agent_id,
            "goal": goal,
            "status": "SUBMITTED",
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "result": None,
            "error": None,
            "workflow_id": None,
        }
        self._tasks[task_id] = task

        if self.agent_loop_service:
            try:
                dispatch = await self.agent_loop_service.dispatch_task(
                    agent_id=agent_id, goal=goal, source="a2a"
                )
                task["status"] = "WORKING"
                task["workflow_id"] = dispatch.get("workflow_id")
                if dispatch.get("status") == "failed":
                    task["status"] = "FAILED"
                    task["error"] = dispatch.get("error", "Dispatch failed")
            except Exception as e:
                task["status"] = "FAILED"
                task["error"] = str(e)

        task["updated_at"] = datetime.now(timezone.utc).isoformat()
        return task

    def get_task(self, task_id: str) -> Optional[dict]:
        task = self._tasks.get(task_id)
        if not task:
            return None
        # Check workflow status if available
        wf_id = task.get("workflow_id")
        if wf_id and self.task_workflow_service:
            wf = self.task_workflow_service._workflows.get(wf_id)
            if wf:
                from app.services.task_workflow_service import WorkflowPhase
                phase_map = {
                    WorkflowPhase.BRAINSTORM: "WORKING",
                    WorkflowPhase.PLAN: "WORKING",
                    WorkflowPhase.EXECUTE: "WORKING",
                    WorkflowPhase.VALIDATE: "WORKING",
                    WorkflowPhase.DOCUMENT: "WORKING",
                    WorkflowPhase.COMPLETED: "COMPLETED",
                    WorkflowPhase.FAILED: "FAILED",
                }
                task["status"] = phase_map.get(wf.phase, task["status"])
                if wf.error:
                    task["error"] = wf.error
        return task

    def cancel_task(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if not task:
            return False
        task["status"] = "CANCELED"
        task["updated_at"] = datetime.now(timezone.utc).isoformat()
        return True
