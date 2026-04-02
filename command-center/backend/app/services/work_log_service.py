"""
NemoClaw Command Center — WorkLogService

Agents log work entries and answer "what did you do?" with markdown summaries.
Storage: ~/.nemoclaw/work-logs/{agent_id}/YYYY-MM-DD.jsonl (append-only)
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger("cc.work_log")

BASE_DIR = Path.home() / ".nemoclaw" / "work-logs"


class WorkLogEntry:
    """Single work log entry."""

    def __init__(
        self,
        agent_id: str,
        project_id: str,
        action: str,
        details: str,
        artifacts: list[str] | None = None,
    ):
        self.entry_id = uuid4().hex[:12]
        self.agent_id = agent_id
        self.project_id = project_id
        self.action = action
        self.details = details
        self.artifacts = artifacts or []
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "agent_id": self.agent_id,
            "project_id": self.project_id,
            "action": self.action,
            "details": self.details,
            "artifacts": self.artifacts,
            "timestamp": self.timestamp,
        }


class WorkLogService:
    """Append-only work log with per-agent daily JSONL files."""

    def __init__(self, base_dir: Path | None = None):
        self.base_dir = base_dir or BASE_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)
        logger.info("WorkLogService initialized (storage: %s)", self.base_dir)

    # ── Write ─────────────────────────────────────────────────────────

    def log_work(
        self,
        agent_id: str,
        project_id: str,
        action: str,
        details: str,
        artifacts: list[str] | None = None,
    ) -> dict[str, Any]:
        """Append a work entry to the agent's daily JSONL file."""
        entry = WorkLogEntry(agent_id, project_id, action, details, artifacts)
        agent_dir = self.base_dir / agent_id
        agent_dir.mkdir(parents=True, exist_ok=True)

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_file = agent_dir / f"{today}.jsonl"

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry.to_dict(), default=str) + "\n")

        logger.debug("Logged work: %s/%s — %s", agent_id, project_id, action)
        return entry.to_dict()

    # ── Read ──────────────────────────────────────────────────────────

    def _read_agent_logs(
        self, agent_id: str, since: datetime | None = None
    ) -> list[dict[str, Any]]:
        """Read all JSONL entries for an agent, optionally filtered by date."""
        agent_dir = self.base_dir / agent_id
        if not agent_dir.exists():
            return []

        entries: list[dict[str, Any]] = []
        for jsonl_file in sorted(agent_dir.glob("*.jsonl")):
            # Quick date filter by filename
            file_date_str = jsonl_file.stem  # YYYY-MM-DD
            if since:
                try:
                    file_date = datetime.strptime(file_date_str, "%Y-%m-%d").replace(
                        tzinfo=timezone.utc
                    )
                    if file_date.date() < since.date():
                        continue
                except ValueError:
                    continue

            try:
                for line in jsonl_file.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    entry = json.loads(line)
                    # Precise timestamp filter
                    if since:
                        entry_ts = datetime.fromisoformat(entry["timestamp"])
                        if entry_ts < since:
                            continue
                    entries.append(entry)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to read %s: %s", jsonl_file, e)

        return entries

    def get_agent_summary(
        self, agent_id: str, period: str = "today"
    ) -> dict[str, Any]:
        """Build a markdown summary of agent work for a period."""
        now = datetime.now(timezone.utc)
        if period == "today":
            since = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "week":
            since = now - timedelta(days=7)
        else:  # "all"
            since = None

        entries = self._read_agent_logs(agent_id, since)

        if not entries:
            md = f"# Work Log — {agent_id}\n\nNo entries for period: {period}\n"
            return {"agent_id": agent_id, "period": period, "total": 0, "markdown": md, "entries": []}

        # Group by project
        by_project: dict[str, list[dict]] = {}
        for e in entries:
            pid = e.get("project_id", "unassigned")
            by_project.setdefault(pid, []).append(e)

        lines = [f"# Work Log — {agent_id}", f"**Period:** {period} | **Entries:** {len(entries)}", ""]
        for pid, proj_entries in by_project.items():
            lines.append(f"## Project: {pid}")
            for e in proj_entries:
                ts = e["timestamp"][:16].replace("T", " ")
                lines.append(f"- **[{ts}]** {e['action']}: {e['details']}")
                if e.get("artifacts"):
                    for a in e["artifacts"]:
                        lines.append(f"  - artifact: `{a}`")
            lines.append("")

        md = "\n".join(lines)
        return {
            "agent_id": agent_id,
            "period": period,
            "total": len(entries),
            "markdown": md,
            "entries": entries,
        }

    def get_project_log(self, project_id: str) -> dict[str, Any]:
        """All work entries across all agents for a project."""
        entries: list[dict[str, Any]] = []

        if not self.base_dir.exists():
            return {"project_id": project_id, "total": 0, "entries": []}

        for agent_dir in self.base_dir.iterdir():
            if not agent_dir.is_dir():
                continue
            for e in self._read_agent_logs(agent_dir.name):
                if e.get("project_id") == project_id:
                    entries.append(e)

        entries.sort(key=lambda e: e.get("timestamp", ""))
        return {"project_id": project_id, "total": len(entries), "entries": entries}

    def search_logs(
        self, query: str, agent_id: str | None = None
    ) -> dict[str, Any]:
        """Full-text search across work log entries."""
        query_lower = query.lower()
        results: list[dict[str, Any]] = []

        if agent_id:
            agent_ids = [agent_id]
        else:
            if not self.base_dir.exists():
                return {"query": query, "total": 0, "results": []}
            agent_ids = [
                d.name for d in self.base_dir.iterdir() if d.is_dir()
            ]

        for aid in agent_ids:
            for entry in self._read_agent_logs(aid):
                searchable = " ".join([
                    entry.get("action", ""),
                    entry.get("details", ""),
                    entry.get("project_id", ""),
                    " ".join(entry.get("artifacts", [])),
                ]).lower()
                if query_lower in searchable:
                    results.append(entry)

        results.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
        return {"query": query, "total": len(results), "results": results[:100]}

    def export_logs(
        self, agent_id: str, fmt: str = "markdown"
    ) -> dict[str, Any]:
        """Export all logs for an agent as markdown or JSON."""
        entries = self._read_agent_logs(agent_id)

        if fmt == "markdown":
            summary = self.get_agent_summary(agent_id, period="all")
            return {
                "agent_id": agent_id,
                "format": "markdown",
                "total": summary["total"],
                "content": summary["markdown"],
            }

        return {
            "agent_id": agent_id,
            "format": "json",
            "total": len(entries),
            "content": json.dumps(entries, indent=2, default=str),
        }
