#!/usr/bin/env python3
"""
NemoClaw Agent Registry v1.0

Loads agent-schema.yaml and capability-registry.yaml.
Enforces:
  - Domain boundaries (agents can't operate outside their domain)
  - Memory write permissions (agents can only write to their keys)
  - Authority hierarchy (overrides require proper level)
  - Capability ownership (skills are invoked by the owning agent)
  - Decision logging (every decision persisted)

Usage:
  from agent_registry import AgentRegistry
  registry = AgentRegistry()
  registry.validate_action("strategy_lead", "market_research", {"research_topic": "AI agents"})
"""

import fnmatch
import json
import os
import re
import uuid
import yaml
from datetime import datetime, timezone
from pathlib import Path

REPO = Path.home() / "nemoclaw-local-foundation"
SCHEMA_PATH = REPO / "config" / "agents" / "agent-schema.yaml"
REGISTRY_PATH = REPO / "config" / "agents" / "capability-registry.yaml"
DECISION_LOG_PATH = Path.home() / ".nemoclaw" / "logs" / "decision-log.jsonl"


class AgentRegistry:
    """Central registry for all agents, capabilities, and enforcement rules."""

    def __init__(self, schema_path=None, registry_path=None):
        self.schema_path = schema_path or SCHEMA_PATH
        self.registry_path = registry_path or REGISTRY_PATH
        self.schema = self._load_yaml(self.schema_path)
        self.registry = self._load_yaml(self.registry_path)

        # Build lookup tables
        self.agents = {a["agent_id"]: a for a in self.schema.get("agents", [])}
        self.capabilities = self.registry.get("capabilities", {})
        self.domains = self.schema.get("domain_boundaries", {})
        self.authority = self.schema.get("authority_hierarchy", {})
        self.override_rules = {r["from"]: r for r in self.authority.get("override_rules", [])}

    def _load_yaml(self, path):
        """Load YAML file, return empty dict if not found."""
        if not os.path.exists(path):
            return {}
        with open(path) as f:
            return yaml.safe_load(f) or {}

    # ── Agent Queries ─────────────────────────────────────────────────────

    def get_agent(self, agent_id):
        """Get agent definition by ID."""
        return self.agents.get(agent_id)

    def list_agents(self):
        """List all registered agents with their roles."""
        result = []
        for aid, agent in self.agents.items():
            result.append({
                "agent_id": aid,
                "title": agent.get("title", ""),
                "authority_level": agent.get("authority_level", 99),
                "owns": agent.get("owns", []),
            })
        return sorted(result, key=lambda x: x["authority_level"])

    def get_agent_skills(self, agent_id):
        """Get all skills available to an agent."""
        agent = self.agents.get(agent_id)
        if not agent:
            return []
        skills = agent.get("skills", {})
        return skills.get("primary", []) + skills.get("future", [])

    def get_agent_for_capability(self, capability_name):
        """Find which agent owns a capability."""
        cap = self.capabilities.get(capability_name)
        if not cap:
            return None, f"Unknown capability: {capability_name}"
        return cap.get("owned_by"), None

    def get_fallback_agent(self, capability_name):
        """Get fallback agent for a capability."""
        cap = self.capabilities.get(capability_name)
        if not cap:
            return None
        return cap.get("fallback_agent")

    # ── Domain Enforcement ────────────────────────────────────────────────

    def validate_action(self, agent_id, capability_name, inputs=None):
        """Validate that an agent is allowed to perform a capability.
        
        Returns: (allowed: bool, reason: str)
        """
        # Check agent exists
        if agent_id not in self.agents:
            return False, f"Unknown agent: {agent_id}"

        # Check capability exists
        cap = self.capabilities.get(capability_name)
        if not cap:
            return False, f"Unknown capability: {capability_name}"

        # Check ownership
        owner = cap.get("owned_by")
        if owner != agent_id:
            fallback = cap.get("fallback_agent")
            if fallback != agent_id:
                return False, (
                    f"DOMAIN VIOLATION: {agent_id} cannot perform {capability_name}. "
                    f"Owned by {owner}" +
                    (f", fallback: {fallback}" if fallback else "")
                )

        # Check domain boundaries
        domain = self.domains.get(agent_id, {})
        forbidden = domain.get("forbidden", [])
        for f in forbidden:
            if f.lower() in capability_name.lower():
                return False, f"FORBIDDEN: {agent_id} cannot perform actions related to '{f}'"

        # Validate required inputs
        required = cap.get("requires_inputs", [])
        if inputs:
            missing = [r for r in required if r not in inputs]
            if missing:
                return False, f"Missing required inputs: {missing}"

        return True, "OK"

    def validate_memory_write(self, agent_id, memory_key):
        """Check if an agent is allowed to write to a specific memory key.
        
        Returns: (allowed: bool, reason: str)
        """
        domain = self.domains.get(agent_id, {})
        allowed_patterns = domain.get("memory_write_keys", [])

        # Executive operator has wildcard access
        if "*" in allowed_patterns:
            return True, "Full access"

        # Check if key matches any allowed pattern
        for pattern in allowed_patterns:
            if fnmatch.fnmatch(memory_key, pattern):
                return True, f"Matches pattern: {pattern}"

        return False, (
            f"MEMORY VIOLATION: {agent_id} cannot write to key '{memory_key}'. "
            f"Allowed patterns: {allowed_patterns}"
        )

    # ── Authority Enforcement ─────────────────────────────────────────────

    def validate_override(self, from_agent, target_agent, reason=""):
        """Check if one agent can override another.
        
        Returns: (allowed: bool, reason: str, logging_required: bool)
        """
        from_level = self.agents.get(from_agent, {}).get("authority_level", 99)
        target_level = self.agents.get(target_agent, {}).get("authority_level", 99)

        rule = self.override_rules.get(from_agent, {})
        can_override = rule.get("can_override", [])

        if can_override == "all":
            return True, "CEO-level override", True

        if target_agent in can_override:
            conditions = rule.get("conditions", "")
            return True, f"Allowed with conditions: {conditions}", True

        if from_level < target_level:
            return True, f"Higher authority ({from_level} < {target_level})", True

        return False, (
            f"AUTHORITY VIOLATION: {from_agent} (level {from_level}) "
            f"cannot override {target_agent} (level {target_level})"
        ), False

    def check_joint_review_needed(self, decision_context):
        """Check if a decision triggers a joint review requirement.
        
        Returns: (needed: bool, required_agents: list, tiebreaker: str)
        """
        triggers = self.authority.get("joint_review_triggers", [])
        for trigger in triggers:
            # Simple keyword matching — can be upgraded to LLM classification
            trigger_text = trigger.get("trigger", "").lower()
            context_lower = decision_context.lower()
            keywords = ["constrain", "implementation", "complexity", "feasibility", "scope"]
            if any(kw in context_lower for kw in keywords):
                return (
                    True,
                    trigger.get("required_agents", []),
                    trigger.get("tiebreaker", "executive_operator"),
                )
        return False, [], ""

    # ── Decision Logging ──────────────────────────────────────────────────

    def log_decision(self, owner, context, options, decision, rationale,
                     reversibility="reversible"):
        """Log a decision to the persistent decision log.
        
        Returns: decision_id
        """
        decision_id = f"dec_{uuid.uuid4().hex[:8]}"
        entry = {
            "decision_id": decision_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "decision_owner": owner,
            "context": context,
            "options_considered": options,
            "final_decision": decision,
            "rationale": rationale,
            "reversibility": reversibility,  # reversible | irreversible
            "outcome": None,  # filled post-execution
            "outcome_score": None,  # 1-10, filled post-execution
        }

        DECISION_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(DECISION_LOG_PATH, "a") as f:
            f.write(json.dumps(entry) + "\n")

        return decision_id

    def update_decision_outcome(self, decision_id, outcome, score):
        """Update a decision with its outcome (post-execution)."""
        if not DECISION_LOG_PATH.exists():
            return False

        lines = []
        updated = False
        with open(DECISION_LOG_PATH) as f:
            for line in f:
                entry = json.loads(line.strip())
                if entry.get("decision_id") == decision_id:
                    entry["outcome"] = outcome
                    entry["outcome_score"] = score
                    updated = True
                lines.append(json.dumps(entry))

        if updated:
            with open(DECISION_LOG_PATH, "w") as f:
                f.write("\n".join(lines) + "\n")

        return updated

    # ── Constraint Checking ───────────────────────────────────────────────

    def check_constraints(self, agent_id, action_context=None):
        """Check agent-specific constraints.
        
        Returns: list of violations (empty = all clear)
        """
        violations = []
        agent = self.agents.get(agent_id, {})
        constraints = agent.get("constraints", [])
        domain = self.domains.get(agent_id, {})
        domain_constraints = domain.get("constraints", [])

        all_constraints = constraints + domain_constraints

        # Operations Lead bias check
        if agent_id == "operations_lead" and action_context:
            scheduling = action_context.get("currently_scheduling", [])
            modifying_prompts_for = action_context.get("modifying_prompts_for", [])
            overlap = set(scheduling) & set(modifying_prompts_for)
            if overlap:
                violations.append(
                    f"BIAS VIOLATION: operations_lead cannot modify prompts for "
                    f"agents it is scheduling: {overlap}"
                )

        return violations

    # ── Capability Queries ────────────────────────────────────────────────

    def get_capabilities_for_agent(self, agent_id):
        """Get all capabilities owned by an agent."""
        result = []
        for cap_name, cap in self.capabilities.items():
            if cap.get("owned_by") == agent_id:
                result.append({
                    "name": cap_name,
                    "skill": cap.get("skill"),
                    "requires": cap.get("requires_inputs", []),
                    "produces": cap.get("produces_outputs", []),
                })
        return result

    def find_capability_for_task(self, task_description):
        """Find the best capability for a task description (keyword matching).
        
        Returns: (capability_name, agent_id, skill_id) or (None, None, None)
        """
        task_lower = task_description.lower()
        best_match = None
        best_score = 0

        for cap_name, cap in self.capabilities.items():
            # Score by keyword overlap
            cap_words = set(cap_name.replace("_", " ").lower().split())
            skill_name = cap.get("skill", "").replace("-", " ").lower()
            all_words = cap_words | set(skill_name.split())

            score = sum(1 for w in all_words if w in task_lower)
            if score > best_score:
                best_score = score
                best_match = cap_name

        if best_match:
            cap = self.capabilities[best_match]
            return best_match, cap.get("owned_by"), cap.get("skill")

        return None, None, None

    # ── Summary ───────────────────────────────────────────────────────────

    def summary(self):
        """Print registry summary."""
        print(f"Agents: {len(self.agents)}")
        print(f"Capabilities: {len(self.capabilities)}")
        print(f"Authority levels: {len(self.authority.get('levels', {}))}")
        print()
        for agent in self.list_agents():
            caps = self.get_capabilities_for_agent(agent["agent_id"])
            print(f"  [{agent['authority_level']}] {agent['agent_id']} — {agent['title']}")
            print(f"      Owns: {', '.join(agent['owns'][:4])}{'...' if len(agent['owns']) > 4 else ''}")
            print(f"      Capabilities: {len(caps)}")


# ═══════════════════════════════════════════════════════════════════════════════
# CLI Interface
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="NemoClaw Agent Registry")
    parser.add_argument("--summary", action="store_true", help="Print registry summary")
    parser.add_argument("--validate-action", nargs=2, metavar=("AGENT", "CAPABILITY"),
                       help="Validate if agent can perform capability")
    parser.add_argument("--validate-memory", nargs=2, metavar=("AGENT", "KEY"),
                       help="Validate if agent can write to memory key")
    parser.add_argument("--validate-override", nargs=2, metavar=("FROM", "TARGET"),
                       help="Validate if agent can override another")
    parser.add_argument("--agent-caps", metavar="AGENT",
                       help="List capabilities for an agent")
    parser.add_argument("--find-task", metavar="DESCRIPTION",
                       help="Find best capability for a task")
    args = parser.parse_args()

    registry = AgentRegistry()

    if args.summary:
        registry.summary()

    elif args.validate_action:
        agent, cap = args.validate_action
        ok, reason = registry.validate_action(agent, cap)
        print(f"{'✅' if ok else '❌'} {reason}")

    elif args.validate_memory:
        agent, key = args.validate_memory
        ok, reason = registry.validate_memory_write(agent, key)
        print(f"{'✅' if ok else '❌'} {reason}")

    elif args.validate_override:
        from_a, target_a = args.validate_override
        ok, reason, log = registry.validate_override(from_a, target_a)
        print(f"{'✅' if ok else '❌'} {reason} (logging: {'required' if log else 'no'})")

    elif args.agent_caps:
        caps = registry.get_capabilities_for_agent(args.agent_caps)
        for c in caps:
            print(f"  {c['name']}: skill={c['skill']}, requires={c['requires']}")

    elif args.find_task:
        cap, agent, skill = registry.find_capability_for_task(args.find_task)
        if cap:
            print(f"  Capability: {cap}")
            print(f"  Agent: {agent}")
            print(f"  Skill: {skill}")
        else:
            print("  No matching capability found")

    else:
        registry.summary()
