"""
NemoClaw Execution Engine — Skill Chain Wiring (E-9)

Defines how skills chain together. Rev-06 Revenue Orchestrator
uses this to auto-trigger downstream skills.

Enforced rule: Every analyzer output with trigger_skill is auto-routed.
Confidence gating: auto-execute if confidence > 0.8 and demand_volume == "high".

NEW FILE: command-center/backend/app/services/skill_chain_wiring.py
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger("cc.chain_wiring")

# ── CHAIN DEFINITIONS ──────────────────────────────────────────────
# Each chain: name → ordered list of skills with trigger conditions.

CHAIN_DEFINITIONS: dict[str, dict[str, Any]] = {
    "demand_to_revenue": {
        "description": "Full loop: demand signal → offer → content → outreach → close → payment",
        "trigger": "auto",  # auto-execute when conditions met
        "steps": [
            {"skill": "int-01-comment-signal-scraper", "next": "int-02-demand-pattern-analyzer"},
            {"skill": "int-02-demand-pattern-analyzer", "next": "int-03-opportunity-offer-generator",
             "condition": "confidence > 0.6"},
            {"skill": "int-03-opportunity-offer-generator", "next": "rev-08-agentic-service-packager"},
            {"skill": "rev-08-agentic-service-packager", "next": "biz-01-proposal-generator"},
            {"skill": "biz-01-proposal-generator", "next": "out-01-multi-touch-sequence-builder"},
            {"skill": "out-01-multi-touch-sequence-builder", "next": "out-02-email-executor"},
        ],
    },
    "content_engine": {
        "description": "Content creation → repurpose → distribute → analyze",
        "trigger": "scheduled",
        "steps": [
            {"skill": "cnt-01-viral-hook-generator", "next": "cnt-02-instagram-reel-script-writer"},
            {"skill": "cnt-02-instagram-reel-script-writer", "next": "cnt-04-content-repurposer"},
            {"skill": "cnt-04-content-repurposer", "next": "cnt-08-cross-channel-distributor"},
            {"skill": "cnt-08-cross-channel-distributor", "next": "cnt-09-social-posting-executor"},
            {"skill": "cnt-09-social-posting-executor", "next": "cnt-07-content-performance-analyzer"},
        ],
    },
    "outreach_sequence": {
        "description": "Lead → qualify → personalize → send → follow-up",
        "trigger": "on_new_lead",
        "steps": [
            {"skill": "rev-02-lead-qualification-engine", "next": "out-05-outreach-personalization-engine",
             "condition": "tier in ['hot', 'warm']"},
            {"skill": "out-05-outreach-personalization-engine", "next": "out-01-multi-touch-sequence-builder"},
            {"skill": "out-01-multi-touch-sequence-builder", "next": "out-02-email-executor"},
            {"skill": "out-02-email-executor", "next": "out-04-follow-up-intelligence"},
            {"skill": "out-04-follow-up-intelligence", "next": "rev-11-follow-up-enforcer"},
        ],
    },
    "deal_close": {
        "description": "Proposal → contract → invoice → payment → onboarding",
        "trigger": "on_deal_advance",
        "steps": [
            {"skill": "biz-01-proposal-generator", "next": "biz-02-contract-drafter"},
            {"skill": "biz-02-contract-drafter", "next": "biz-03-invoice-generator"},
            {"skill": "biz-03-invoice-generator", "next": "rev-09-payment-execution-engine"},
            {"skill": "rev-09-payment-execution-engine", "next": "biz-04-client-onboarding-sequence"},
        ],
    },
    "niche_blitz": {
        "description": "Demand → niche select → flood content + outreach + comments",
        "trigger": "manual",
        "steps": [
            {"skill": "rev-17-demand-signal-miner", "next": "int-02-demand-pattern-analyzer"},
            {"skill": "int-02-demand-pattern-analyzer", "next": "scl-09-niche-domination-engine",
             "condition": "confidence > 0.8 and demand_volume == 'high'"},
            {"skill": "scl-09-niche-domination-engine", "next": "cnt-06-content-calendar-builder"},
        ],
    },
    "experiment_loop": {
        "description": "Design experiment → run → analyze → learn",
        "trigger": "on_low_conversion",
        "steps": [
            {"skill": "scl-06-growth-experiment-designer", "next": "rev-13-live-experiment-runner"},
            {"skill": "rev-13-live-experiment-runner", "next": "rev-15-playbook-memory-engine"},
            {"skill": "rev-15-playbook-memory-engine", "next": "rev-19-system-learning-engine"},
        ],
    },
    "client_health": {
        "description": "Monitor → detect issues → upsell or intervene",
        "trigger": "scheduled_daily",
        "steps": [
            {"skill": "biz-05-client-health-monitor", "next": "biz-06-upsell-opportunity-detector",
             "condition": "health_score > 70"},
            {"skill": "biz-05-client-health-monitor", "next": "rev-11-follow-up-enforcer",
             "condition": "health_score <= 70"},
            {"skill": "biz-06-upsell-opportunity-detector", "next": "biz-01-proposal-generator"},
        ],
    },
}

# ── ANALYZER → ACTION ROUTING ──────────────────────────────────────
# Every analyzer MUST output {insight, recommended_action, trigger_skill}.
# This map defines which skill each analyzer can trigger.

ANALYZER_TRIGGER_MAP: dict[str, list[str]] = {
    "rev-02-lead-qualification-engine": ["out-05-outreach-personalization-engine", "rev-01-autonomous-sales-closer"],
    "rev-03-revenue-attribution-analyzer": ["rev-16-speed-to-revenue-optimizer", "rev-12-risk-capital-allocator"],
    "rev-04-offer-optimization-engine": ["rev-08-agentic-service-packager", "rev-18-instant-offer-launcher"],
    "rev-05-funnel-conversion-analyzer": ["rev-13-live-experiment-runner", "out-06-campaign-performance-optimizer"],
    "rev-15-playbook-memory-engine": ["rev-06-revenue-orchestrator"],
    "rev-19-system-learning-engine": ["rev-06-revenue-orchestrator", "rev-12-risk-capital-allocator"],
    "int-02-demand-pattern-analyzer": ["int-03-opportunity-offer-generator", "rev-08-agentic-service-packager"],
    "int-04-reality-check-engine": [],  # Can output trigger_skill: null to STOP
    "cnt-07-content-performance-analyzer": ["cnt-01-viral-hook-generator", "cnt-10-viral-pattern-analyzer"],
    "cnt-10-viral-pattern-analyzer": ["cnt-01-viral-hook-generator", "cnt-02-instagram-reel-script-writer"],
    "out-04-follow-up-intelligence": ["rev-01-autonomous-sales-closer", "rev-11-follow-up-enforcer"],
    "out-06-campaign-performance-optimizer": ["rev-13-live-experiment-runner"],
    "biz-05-client-health-monitor": ["biz-06-upsell-opportunity-detector", "rev-11-follow-up-enforcer"],
    "biz-06-upsell-opportunity-detector": ["biz-01-proposal-generator"],
    "biz-07-competitive-intelligence-monitor": ["rev-04-offer-optimization-engine"],
}

# ── CONFIDENCE GATING ──────────────────────────────────────────────
CONFIDENCE_THRESHOLD = 0.8
HIGH_DEMAND_AUTO_EXECUTE = True


class SkillChainWiringService:
    """
    Wires skills together into executable chains.

    Features:
    - Get chain definitions
    - Route analyzer outputs to next skill
    - Confidence gating for auto-execution
    - Execute skill via subprocess
    """

    def __init__(self, skill_agent_mapping=None, bridge_manager=None):
        self.skill_agent_mapping = skill_agent_mapping
        self.bridge_manager = bridge_manager
        self._chains = CHAIN_DEFINITIONS
        self._analyzer_map = ANALYZER_TRIGGER_MAP
        self._execution_log: list[dict[str, Any]] = []
        self._persist_path = Path.home() / ".nemoclaw" / "chain-executions.json"
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info(
            "SkillChainWiringService initialized (%d chains, %d analyzer routes)",
            len(self._chains), len(self._analyzer_map),
        )

    def get_chains(self) -> dict[str, Any]:
        """Get all chain definitions."""
        return {
            name: {
                "description": chain["description"],
                "trigger": chain["trigger"],
                "steps": len(chain["steps"]),
            }
            for name, chain in self._chains.items()
        }

    def get_chain(self, name: str) -> dict[str, Any] | None:
        """Get a specific chain definition."""
        return self._chains.get(name)

    def route_analyzer_output(self, analyzer_id: str, output: dict[str, Any]) -> dict[str, Any]:
        """
        Route an analyzer's output to the next skill.

        Enforced format: {insight, recommended_action, trigger_skill, confidence}
        Confidence gating: auto-execute if confidence > 0.8 and demand_volume == "high"
        """
        trigger_skill = output.get("trigger_skill")
        confidence = float(output.get("confidence", 0))
        demand_volume = output.get("demand_volume", "low")

        # Reality check engine can STOP the pipeline
        if trigger_skill is None:
            logger.info("Analyzer %s: STOP signal (trigger_skill=null)", analyzer_id)
            return {
                "action": "stop",
                "reason": output.get("insight", "No action recommended"),
                "analyzer": analyzer_id,
            }

        # Validate trigger_skill is allowed
        allowed = self._analyzer_map.get(analyzer_id, [])
        if allowed and trigger_skill not in allowed:
            logger.warning(
                "Analyzer %s tried to trigger %s (not in allowed: %s)",
                analyzer_id, trigger_skill, allowed,
            )
            return {
                "action": "blocked",
                "reason": f"Skill {trigger_skill} not in allowed triggers for {analyzer_id}",
            }

        # Confidence gating
        auto_execute = (
            confidence >= CONFIDENCE_THRESHOLD
            and demand_volume == "high"
            and HIGH_DEMAND_AUTO_EXECUTE
        )

        result = {
            "action": "auto_execute" if auto_execute else "recommend",
            "trigger_skill": trigger_skill,
            "confidence": confidence,
            "demand_volume": demand_volume,
            "insight": output.get("insight", ""),
            "recommended_action": output.get("recommended_action", ""),
            "analyzer": analyzer_id,
        }

        self._log_execution(result)
        logger.info(
            "Analyzer %s → %s (confidence=%.2f, demand=%s, action=%s)",
            analyzer_id, trigger_skill, confidence, demand_volume, result["action"],
        )
        return result

    async def execute_skill(self, skill_id: str, inputs: dict[str, Any]) -> dict[str, Any]:
        """Execute a skill via subprocess."""
        repo = Path.home() / "nemoclaw-local-foundation"
        skill_dir = repo / "skills" / skill_id
        run_py = skill_dir / "run.py"

        if not run_py.exists():
            return {"success": False, "error": f"Skill {skill_id} not found at {run_py}"}

        # Build command
        cmd = ["python3", str(run_py), "--force"]
        for key, value in inputs.items():
            cmd.extend(["--input", key, str(value)])

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=120, cwd=str(repo),
            )
            success = result.returncode == 0

            # Parse output for envelope
            envelope = None
            if success:
                for line in result.stdout.split("\n"):
                    if "Output:" in line:
                        artifact_path = line.split("Output:", 1)[1].strip()
                        envelope_path = artifact_path.replace(".md", "_envelope.json")
                        ep = Path(envelope_path)
                        if ep.exists():
                            envelope = json.loads(ep.read_text())

            return {
                "success": success,
                "skill_id": skill_id,
                "stdout": result.stdout[-500:] if result.stdout else "",
                "stderr": result.stderr[-500:] if result.stderr else "",
                "envelope": envelope,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"Skill {skill_id} timed out (120s)"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def execute_chain(self, chain_name: str, initial_input: dict[str, Any]) -> dict[str, Any]:
        """Execute a full chain of skills."""
        chain = self._chains.get(chain_name)
        if not chain:
            return {"success": False, "error": f"Chain {chain_name} not found"}

        results = []
        current_input = initial_input

        for step in chain["steps"]:
            skill_id = step["skill"]
            logger.info("Chain %s: executing %s", chain_name, skill_id)

            result = await self.execute_skill(skill_id, current_input)
            results.append({"skill": skill_id, "result": result})

            if not result.get("success"):
                logger.warning("Chain %s: %s failed, stopping", chain_name, skill_id)
                break

            # Pass envelope outputs as next input
            if result.get("envelope") and result["envelope"].get("outputs"):
                envelope_outputs = result["envelope"]["outputs"]
                current_input = {
                    "input_data": envelope_outputs.get("result_summary", ""),
                    **{k: str(v) for k, v in envelope_outputs.items() if k != "result"},
                }

        return {
            "success": all(r["result"].get("success") for r in results),
            "chain": chain_name,
            "steps_completed": len(results),
            "steps_total": len(chain["steps"]),
            "results": results,
        }

    def _log_execution(self, entry: dict[str, Any]) -> None:
        self._execution_log.append(entry)
        if len(self._execution_log) > 500:
            self._execution_log = self._execution_log[-500:]
        try:
            self._persist_path.write_text(
                json.dumps(self._execution_log[-100:], indent=2, default=str)
            )
        except Exception:
            pass

    def get_execution_log(self, limit: int = 50) -> list[dict[str, Any]]:
        return self._execution_log[-limit:]

    def get_analyzer_routes(self) -> dict[str, list[str]]:
        return self._analyzer_map

    def get_stats(self) -> dict[str, Any]:
        return {
            "chains": len(self._chains),
            "analyzer_routes": len(self._analyzer_map),
            "total_chain_steps": sum(len(c["steps"]) for c in self._chains.values()),
            "executions_logged": len(self._execution_log),
            "confidence_threshold": CONFIDENCE_THRESHOLD,
            "auto_execute_enabled": HIGH_DEMAND_AUTO_EXECUTE,
        }
