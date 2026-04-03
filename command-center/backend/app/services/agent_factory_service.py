"""
NemoClaw Execution Engine — AgentFactoryService

Creates per-agent workspaces with backend-specific instruction files.
- Claude Code agents get CLAUDE.md
- Codex agents get .codex/instructions.md
- API agents get workspace/output dirs only

Reads execution_backend config from agent-schema.yaml.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("cc.agent_factory")

REPO_ROOT = Path(__file__).resolve().parents[4]  # command-center/backend/app/services -> repo root
SCHEMA_PATH = REPO_ROOT / "config" / "agents" / "agent-schema.yaml"
WORKSPACE_ROOT = Path.home() / ".nemoclaw" / "workspaces"

DEFAULT_BACKEND = {
    "backend": "api",
    "backend_model": "",
    "fallback_backend": "api",
    "max_turns": 10,
}


class AgentFactoryService:
    """Provisions per-agent workspaces and generates instruction files."""

    def __init__(self, schema_path: Path | None = None):
        self._schema_path = schema_path or SCHEMA_PATH
        self._schema: dict[str, Any] = {}
        self._agents: dict[str, dict[str, Any]] = {}
        self._load_schema()

    def _load_schema(self) -> None:
        """Load agent-schema.yaml and index by agent_id."""
        try:
            raw = yaml.safe_load(self._schema_path.read_text())
            self._schema = raw or {}
            agents_list = raw.get("agents", [])
            if not agents_list:
                # Schema uses top-level list under authority_hierarchy, agents at root
                # Try extracting from the list items that have agent_id
                for item in raw if isinstance(raw, list) else []:
                    if "agent_id" in item:
                        self._agents[item["agent_id"]] = item
            else:
                for agent in agents_list:
                    if "agent_id" in agent:
                        self._agents[agent["agent_id"]] = agent
            logger.info(
                "AgentFactoryService loaded %d agents from %s",
                len(self._agents), self._schema_path.name,
            )
        except Exception as e:
            logger.error("Failed to load agent schema: %s", e)

    def get_agent_config(self, agent_id: str) -> dict[str, Any]:
        """Return full agent config dict."""
        return self._agents.get(agent_id, {})

    def get_backend_config(self, agent_id: str) -> dict[str, Any]:
        """Return execution_backend block with safe defaults."""
        agent = self._agents.get(agent_id, {})
        return agent.get("execution_backend", dict(DEFAULT_BACKEND))

    def create_workspace(self, agent_id: str) -> Path:
        """
        Create per-agent workspace directory structure.

        ~/.nemoclaw/workspaces/{agent_id}/
        ├── workspace/
        ├── output/
        ├── CLAUDE.md          (if backend=claude_code)
        └── .codex/
            └── instructions.md (if backend=codex)
        """
        agent = self._agents.get(agent_id)
        if not agent:
            logger.warning("create_workspace: unknown agent %s", agent_id)
            return WORKSPACE_ROOT / agent_id

        ws_root = WORKSPACE_ROOT / agent_id
        (ws_root / "workspace").mkdir(parents=True, exist_ok=True)
        (ws_root / "output").mkdir(parents=True, exist_ok=True)

        backend_cfg = agent.get("execution_backend", DEFAULT_BACKEND)
        backend = backend_cfg.get("backend", "api")

        if backend == "claude_code":
            claude_md = self.generate_claude_md(agent_id)
            (ws_root / "CLAUDE.md").write_text(claude_md)
            logger.debug("Wrote CLAUDE.md for %s", agent_id)
        elif backend == "codex":
            codex_dir = ws_root / ".codex"
            codex_dir.mkdir(parents=True, exist_ok=True)
            instructions = self.generate_codex_instructions(agent_id)
            (codex_dir / "instructions.md").write_text(instructions)
            logger.debug("Wrote .codex/instructions.md for %s", agent_id)
        # api backend: no instruction file needed

        return ws_root

    def create_all_workspaces(self) -> list[str]:
        """Create workspaces for all agents. Returns list of agent_ids provisioned."""
        provisioned = []
        for agent_id in self._agents:
            self.create_workspace(agent_id)
            provisioned.append(agent_id)
        logger.info("Provisioned %d agent workspaces", len(provisioned))
        return provisioned

    def generate_claude_md(
        self,
        agent_id: str,
        mission_id: str | None = None,
        task: str | None = None,
    ) -> str:
        """Render CLAUDE.md for a Claude Code agent."""
        agent = self._agents.get(agent_id, {})
        backend_cfg = agent.get("execution_backend", DEFAULT_BACKEND)

        title = agent.get("title", agent_id)
        display_name = agent.get("display_name", agent_id)
        role = agent.get("role", "")
        authority = agent.get("authority_level", 0)
        owns = agent.get("owns", [])
        skills = agent.get("skills", {}).get("primary", [])
        constraints = agent.get("constraints", [])
        reports_to = agent.get("reports_to", [])
        max_turns = backend_cfg.get("max_turns", 10)
        model = backend_cfg.get("backend_model", "sonnet")

        # Build reporting chain
        if reports_to:
            chain = " -> ".join(reports_to) + " -> executive_operator (CEO)"
        elif agent_id == "executive_operator":
            chain = "Human (founder)"
        else:
            chain = "executive_operator (CEO)"

        lines = [
            f"# {display_name} — {title}",
            "",
            f"**Agent ID:** {agent_id}",
            f"**Authority Level:** L{authority}",
            f"**Model:** {model}",
            f"**Reporting Chain:** {chain}",
            "",
            "## Role",
            role,
            "",
            "## Owned Domains",
        ]
        for domain in owns:
            lines.append(f"- {domain}")

        lines.extend(["", "## Available Skills"])
        for skill in skills:
            lines.append(f"- {skill}")

        if constraints:
            lines.extend(["", "## Constraints"])
            if isinstance(constraints, list):
                for c in constraints:
                    lines.append(f"- {c}")
            else:
                lines.append(str(constraints))

        if mission_id:
            lines.extend(["", f"## Active Mission: {mission_id}"])
        if task:
            lines.extend(["", f"## Current Task", task])

        lines.extend([
            "",
            "## Heartbeat Protocol",
            "Report status every 5 turns via `workspace/status.json`:",
            "```json",
            '{',
            '  "agent_id": "' + agent_id + '",',
            '  "turn": <current_turn>,',
            '  "status": "working|blocked|complete",',
            '  "progress_pct": <0-100>,',
            '  "summary": "<one-line update>"',
            '}',
            "```",
            "",
            "## Turn Budget",
            f"Maximum {max_turns} turns per task. Plan accordingly.",
            f"If blocked after {max_turns // 2} turns, escalate via workspace/status.json.",
            "",
            "## Output",
            "Write all artifacts to `output/`. Do not modify files outside your workspace.",
        ])

        return "\n".join(lines) + "\n"

    def generate_codex_instructions(
        self,
        agent_id: str,
        mission_id: str | None = None,
        task: str | None = None,
    ) -> str:
        """Render instructions.md for a Codex agent."""
        agent = self._agents.get(agent_id, {})
        backend_cfg = agent.get("execution_backend", DEFAULT_BACKEND)

        title = agent.get("title", agent_id)
        display_name = agent.get("display_name", agent_id)
        role = agent.get("role", "")
        authority = agent.get("authority_level", 0)
        owns = agent.get("owns", [])
        skills = agent.get("skills", {}).get("primary", [])
        max_turns = backend_cfg.get("max_turns", 10)
        model = backend_cfg.get("backend_model", "gpt-5.4")
        reports_to = agent.get("reports_to", [])

        if reports_to:
            chain = " -> ".join(reports_to) + " -> executive_operator (CEO)"
        elif agent_id == "executive_operator":
            chain = "Human (founder)"
        else:
            chain = "executive_operator (CEO)"

        lines = [
            f"# {display_name} — {title}",
            "",
            f"Agent: {agent_id} | L{authority} | Model: {model}",
            f"Reports to: {chain}",
            "",
            f"Role: {role}",
            "",
            f"Domains: {', '.join(owns)}",
            f"Skills: {', '.join(skills[:10])}{'...' if len(skills) > 10 else ''}",
            "",
            f"Turn budget: {max_turns}. Escalate if blocked after {max_turns // 2}.",
            "Output to output/. Status to workspace/status.json every 5 turns.",
        ]

        if mission_id:
            lines.append(f"\nMission: {mission_id}")
        if task:
            lines.append(f"Task: {task}")

        return "\n".join(lines) + "\n"
