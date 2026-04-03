#!/usr/bin/env python3
"""
NemoClaw Anthropic Agent Profiles Setup v1.0.0
Generates, validates, and tests Anthropic Claude profiles for all 11 agents.

Usage:
    python3 scripts/setup_anthropic_profiles.py --generate   # Build profiles from agent-schema.yaml
    python3 scripts/setup_anthropic_profiles.py --validate   # Validate profiles against schema
    python3 scripts/setup_anthropic_profiles.py --test AGENT  # Send test prompt to agent
"""

import argparse
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from lib.config_loader import load_routing_config, REPO as _REPO, _load_yaml

AGENT_SCHEMA_PATH = REPO / "config" / "agents" / "agent-schema.yaml"
PROFILES_PATH = REPO / "config" / "anthropic-agent-profiles.yaml"

# Standard tool definitions shared by all agents (authorization is runtime)
STANDARD_TOOLS = [
    {
        "name": "skill_executor",
        "description": "Execute a NemoClaw skill by ID with inputs",
        "input_schema": {
            "type": "object",
            "properties": {
                "skill_id": {"type": "string", "description": "The skill ID to execute"},
                "inputs": {"type": "object", "description": "Skill input parameters"},
            },
            "required": ["skill_id"],
        },
    },
    {
        "name": "work_log",
        "description": "Log completed work entry for audit trail",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "description": "Action performed"},
                "details": {"type": "string", "description": "Action details"},
                "project_id": {"type": "string", "description": "Project context"},
            },
            "required": ["action", "details"],
        },
    },
    {
        "name": "memory_read",
        "description": "Read from shared or private agent memory",
        "input_schema": {
            "type": "object",
            "properties": {
                "key_pattern": {"type": "string", "description": "Memory key or glob pattern"},
                "scope": {"type": "string", "enum": ["private", "shared"]},
            },
            "required": ["key_pattern"],
        },
    },
    {
        "name": "memory_write",
        "description": "Write to memory (respects domain boundaries)",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Memory key"},
                "value": {"type": "string", "description": "Value to store"},
                "scope": {"type": "string", "enum": ["private", "shared"]},
            },
            "required": ["key", "value"],
        },
    },
]

# Model preference by authority level
MODEL_PREFERENCE = {
    1: "premium_claude",
    2: "reasoning_claude",
    3: "reasoning_claude",
    4: "reasoning_claude",
}


def _build_system_prompt(agent, schema):
    """Build XML-tagged system prompt for an agent."""
    identity = agent.get("identity", {})
    name = identity.get("name", agent["agent_id"])
    display = agent.get("display_name", "")
    title = agent.get("title", "")
    level = agent.get("authority_level", 0)
    role = agent.get("role", "")
    owns = agent.get("owns", [])
    decides = agent.get("decides", [])

    # Domain boundaries
    bounds = schema.get("domain_boundaries", {}).get(agent["agent_id"], {})
    bound_owns = bounds.get("owns", [])
    bound_forbidden = bounds.get("forbidden", [])

    # Skills
    skills = agent.get("skills", {})
    primary = skills.get("primary", [])

    # Quality
    auto_cap = agent.get("autonomous_capability", {})
    qt = auto_cap.get("quality_target", 9)
    philosophy = identity.get("work_philosophy", "")
    principles = identity.get("operating_principles", [])

    # Behavior mode
    behavior = schema.get("behavior_modes", {}).get("work", {})

    lines = []
    lines.append(f"<agent_identity>")
    lines.append(f"You are {name}, the {display} ({title}) of NemoClaw.")
    lines.append(f"Authority Level: {level}.")
    lines.append(f"</agent_identity>")

    lines.append(f"")
    lines.append(f"<role>{role}</role>")

    lines.append(f"")
    lines.append(f"<authority>")
    lines.append(f"<owns>{', '.join(owns)}</owns>")
    lines.append(f"<decides>{'; '.join(decides)}</decides>")
    lines.append(f"</authority>")

    lines.append(f"")
    lines.append(f"<domain_boundaries>")
    lines.append(f"<owns>{', '.join(bound_owns)}</owns>")
    lines.append(f"<forbidden>{', '.join(bound_forbidden) if bound_forbidden else 'none'}</forbidden>")
    lines.append(f"</domain_boundaries>")

    lines.append(f"")
    lines.append(f"<skills>{', '.join(primary)}</skills>")

    lines.append(f"")
    lines.append(f"<quality_standards>")
    lines.append(f"Quality target: {qt}/10")
    if philosophy:
        lines.append(f"Philosophy: {philosophy}")
    if principles:
        for p in principles:
            lines.append(f"- {p}")
    lines.append(f"</quality_standards>")

    lines.append(f"")
    lines.append(f"<behavior_mode>")
    lines.append(f"Standard: {behavior.get('standard', '')}")
    lines.append(f"Quality: {behavior.get('quality_target', '')}")
    lines.append(f"Revenue focus: {behavior.get('revenue_focus', '')}")
    lines.append(f"</behavior_mode>")

    return "\n".join(lines)


def generate_profiles():
    """Generate anthropic-agent-profiles.yaml from agent-schema.yaml."""
    schema = _load_yaml(AGENT_SCHEMA_PATH)
    agents = schema.get("agents", [])

    profiles = {}
    for agent in agents:
        aid = agent["agent_id"]
        level = agent.get("authority_level", 3)
        prompt = _build_system_prompt(agent, schema)
        profiles[aid] = {
            "system_prompt": prompt,
            "tools": STANDARD_TOOLS,
            "model_preference": MODEL_PREFERENCE.get(level, "reasoning_claude"),
            "max_tokens": 16384,
        }

    output = {
        "schema_version": 1,
        "created": "2026-04-03",
        "description": "Per-agent Anthropic Claude profiles with XML-tagged system prompts",
        "profiles": profiles,
    }

    with open(PROFILES_PATH, "w") as f:
        yaml.dump(output, f, default_flow_style=False, sort_keys=False, allow_unicode=True, width=120)

    print(f"Generated {len(profiles)} agent profiles -> {PROFILES_PATH}")
    return True


def validate_profiles():
    """Validate profiles against agent-schema.yaml and routing config."""
    if not PROFILES_PATH.exists():
        print(f"ERROR: Profiles not found: {PROFILES_PATH}")
        print("Run --generate first.")
        return False

    profiles_data = _load_yaml(PROFILES_PATH)
    schema = _load_yaml(AGENT_SCHEMA_PATH)
    routing = load_routing_config()

    profiles = profiles_data.get("profiles", {})
    agents = schema.get("agents", [])
    agent_ids = {a["agent_id"] for a in agents}
    providers = routing.get("providers", {})

    errors = []
    passed = 0

    for aid in agent_ids:
        if aid not in profiles:
            errors.append(f"{aid}: profile MISSING")
            continue

        p = profiles[aid]

        # Check system prompt has required XML tags
        prompt = p.get("system_prompt", "")
        required_tags = ["<agent_identity>", "<role>", "<authority>", "<domain_boundaries>", "<skills>", "<quality_standards>"]
        for tag in required_tags:
            if tag not in prompt:
                errors.append(f"{aid}: missing XML tag {tag}")

        # Check model preference resolves
        model_pref = p.get("model_preference", "")
        if model_pref not in providers:
            errors.append(f"{aid}: model_preference '{model_pref}' not in routing config")

        # Check max_tokens
        mt = p.get("max_tokens", 0)
        if not isinstance(mt, int) or mt <= 0:
            errors.append(f"{aid}: invalid max_tokens={mt}")

        if not any(aid in e for e in errors):
            passed += 1
            print(f"  PASS  {aid}")

    # Check for extra profiles
    extra = set(profiles.keys()) - agent_ids
    for e in extra:
        errors.append(f"{e}: profile exists but agent not in schema")

    print(f"\n{passed}/{len(agent_ids)} agents passed validation")
    if errors:
        print(f"\n{len(errors)} errors:")
        for e in errors:
            print(f"  ERROR  {e}")
        return False

    print("All profiles valid.")
    return True


def test_agent(agent_id):
    """Send a test prompt to an agent using its profile."""
    if not PROFILES_PATH.exists():
        print(f"ERROR: Profiles not found: {PROFILES_PATH}")
        return False

    profiles_data = _load_yaml(PROFILES_PATH)
    profiles = profiles_data.get("profiles", {})

    if agent_id not in profiles:
        print(f"ERROR: No profile for agent '{agent_id}'")
        print(f"Available: {', '.join(sorted(profiles.keys()))}")
        return False

    profile = profiles[agent_id]
    system_prompt = profile["system_prompt"]
    model_pref = profile.get("model_preference", "reasoning_claude")

    from lib.routing import call_llm

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Introduce yourself. What is your role, what do you own, and what are your top 3 priorities right now?"},
    ]

    print(f"Testing {agent_id} via {model_pref}...")
    response, error = call_llm(messages, task_class=model_pref, max_tokens=1000)

    if error:
        print(f"ERROR: {error}")
        return False

    print(f"\n--- {agent_id} response ---")
    print(response[:2000])
    return True


def main():
    parser = argparse.ArgumentParser(description="Anthropic agent profiles setup")
    parser.add_argument("--generate", action="store_true", help="Generate profiles from agent-schema.yaml")
    parser.add_argument("--validate", action="store_true", help="Validate profiles against schema")
    parser.add_argument("--test", type=str, metavar="AGENT_ID", help="Test an agent with a prompt")
    args = parser.parse_args()

    if not (args.generate or args.validate or args.test):
        parser.print_help()
        sys.exit(1)

    if args.generate:
        ok = generate_profiles()
        sys.exit(0 if ok else 1)
    elif args.validate:
        ok = validate_profiles()
        sys.exit(0 if ok else 1)
    elif args.test:
        ok = test_agent(args.test)
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
