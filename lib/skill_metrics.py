"""
Skill success rate tracking — tracks execution outcomes per (skill, agent) pair.

Enables intelligent routing: assign skills to agents with highest success rates.
Storage: ~/.nemoclaw/logs/skill-metrics.jsonl (append-only)
"""

import json
import logging
import os
import time
from collections import defaultdict
from pathlib import Path
from typing import Optional

logger = logging.getLogger("nemoclaw.skill_metrics")

METRICS_PATH = Path.home() / ".nemoclaw" / "logs" / "skill-metrics.jsonl"


class SkillMetrics:
    """Track and query skill execution metrics."""

    def __init__(self, metrics_path: Optional[Path] = None):
        self.path = metrics_path or METRICS_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._stats = defaultdict(lambda: {
            "success": 0, "failure": 0, "total_duration_ms": 0,
            "total_cost": 0.0, "total_quality": 0.0, "runs": 0,
        })
        self._agent_stats = defaultdict(lambda: defaultdict(lambda: {
            "success": 0, "failure": 0, "runs": 0,
        }))
        self._load()

    def _load(self):
        """Load existing metrics from JSONL."""
        if not self.path.exists():
            return
        try:
            for line in self.path.read_text().strip().split("\n"):
                if not line.strip():
                    continue
                entry = json.loads(line)
                self._aggregate(entry)
        except Exception as e:
            logger.warning(f"Failed to load metrics: {e}")

    def _aggregate(self, entry: dict):
        skill = entry.get("skill_id", "")
        agent = entry.get("agent_id", "")
        success = entry.get("success", False)

        s = self._stats[skill]
        s["runs"] += 1
        s["success" if success else "failure"] += 1
        s["total_duration_ms"] += entry.get("duration_ms", 0)
        s["total_cost"] += entry.get("cost_usd", 0.0)
        s["total_quality"] += entry.get("quality_score", 0.0)

        if agent:
            a = self._agent_stats[agent][skill]
            a["runs"] += 1
            a["success" if success else "failure"] += 1

    def track_execution(
        self, skill_id: str, agent_id: str, success: bool,
        duration_ms: int = 0, cost_usd: float = 0.0, quality_score: float = 0.0,
    ):
        """Record a skill execution result."""
        entry = {
            "skill_id": skill_id, "agent_id": agent_id, "success": success,
            "duration_ms": duration_ms, "cost_usd": cost_usd,
            "quality_score": quality_score, "timestamp": time.time(),
        }
        try:
            with open(self.path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.warning(f"Failed to write metric: {e}")
        self._aggregate(entry)

    def get_skill_stats(self, skill_id: str) -> dict:
        """Get aggregated stats for a skill."""
        s = self._stats.get(skill_id)
        if not s or s["runs"] == 0:
            return {"success_rate": 0, "runs": 0}
        return {
            "success_rate": round(s["success"] / s["runs"], 3),
            "avg_duration_ms": int(s["total_duration_ms"] / s["runs"]),
            "avg_cost": round(s["total_cost"] / s["runs"], 4),
            "avg_quality": round(s["total_quality"] / max(s["success"], 1), 2),
            "total_runs": s["runs"],
        }

    def get_agent_skill_affinity(self, agent_id: str) -> dict:
        """Get success rates per skill for an agent."""
        result = {}
        for skill_id, stats in self._agent_stats.get(agent_id, {}).items():
            if stats["runs"] > 0:
                result[skill_id] = round(stats["success"] / stats["runs"], 3)
        return dict(sorted(result.items(), key=lambda x: -x[1]))

    def get_best_agent_for_skill(self, skill_id: str) -> Optional[str]:
        """Find the agent with highest success rate for a skill."""
        best_agent, best_rate = None, 0.0
        for agent_id, skills in self._agent_stats.items():
            stats = skills.get(skill_id)
            if stats and stats["runs"] >= 2:
                rate = stats["success"] / stats["runs"]
                if rate > best_rate:
                    best_rate = rate
                    best_agent = agent_id
        return best_agent

    def get_all_stats(self) -> dict:
        """Get summary of all skill metrics."""
        return {
            "total_skills_tracked": len(self._stats),
            "total_agents_tracked": len(self._agent_stats),
            "skills": {k: self.get_skill_stats(k) for k in sorted(self._stats.keys())},
        }
