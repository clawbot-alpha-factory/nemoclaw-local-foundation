#!/usr/bin/env python3
"""
NemoClaw Google Gemini Agent Profiles Generator v1.0.0
Generates config/google-agent-profiles.yaml from agent-schema.yaml.

Usage:
    python3 scripts/setup_google_profiles.py --generate
"""

import argparse
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from lib.config_loader import _load_yaml

AGENT_SCHEMA_PATH = REPO / "config" / "agents" / "agent-schema.yaml"
PROFILES_PATH = REPO / "config" / "google-agent-profiles.yaml"

# Temperature by agent role type
TEMP_MAP = {
    "executive_operator": 0.3,      # L1 strategic
    "strategy_lead": 0.3,           # L2 strategic
    "operations_lead": 0.3,         # L2 process
    "product_architect": 0.2,       # L3 technical
    "growth_revenue_lead": 0.4,     # L3 revenue
    "narrative_content_lead": 0.8,  # L3 creative
    "engineering_lead": 0.2,        # L3 technical
    "sales_outreach_lead": 0.5,     # L4 execution
    "marketing_campaigns_lead": 0.5, # L4 execution
    "client_success_lead": 0.5,     # L4 execution
    "social_media_lead": 0.7,       # L4 creative execution
}

# Long context strategy by domain focus
CONTEXT_STRATEGY = {
    "executive_operator": "full_document_injection",
    "strategy_lead": "full_document_injection",
    "operations_lead": "codebase_aware",
    "product_architect": "codebase_aware",
    "growth_revenue_lead": "crm_context",
    "narrative_content_lead": "sliding_window",
    "engineering_lead": "codebase_aware",
    "sales_outreach_lead": "crm_context",
    "marketing_campaigns_lead": "crm_context",
    "client_success_lead": "crm_context",
    "social_media_lead": "sliding_window",
}

# Grounding: enable search for agents that benefit from web context
GROUNDING_SEARCH = {
    "executive_operator": False,
    "strategy_lead": True,
    "operations_lead": False,
    "product_architect": False,
    "growth_revenue_lead": True,
    "narrative_content_lead": False,
    "engineering_lead": False,
    "sales_outreach_lead": True,
    "marketing_campaigns_lead": True,
    "client_success_lead": False,
    "social_media_lead": True,
}


def _build_system_instruction(agent, schema):
    """Build markdown-formatted system instruction for Gemini."""
    identity = agent.get("identity", {})
    name = identity.get("name", agent["agent_id"])
    display = agent.get("display_name", "")
    title = agent.get("title", "")
    level = agent.get("authority_level", 0)
    role = agent.get("role", "")
    owns = agent.get("owns", [])
    decides = agent.get("decides", [])
    bounds = schema.get("domain_boundaries", {}).get(agent["agent_id"], {})
    skills = agent.get("skills", {}).get("primary", [])
    auto_cap = agent.get("autonomous_capability", {})
    philosophy = identity.get("work_philosophy", "")
    principles = identity.get("operating_principles", [])

    lines = []
    lines.append(f"## Agent Identity")
    lines.append(f"You are {name}, the {display} ({title}) of NemoClaw.")
    lines.append(f"Authority Level: {level}.")

    lines.append(f"\n## Role\n{role}")

    lines.append(f"\n## Domain Ownership\n{', '.join(owns)}")

    lines.append(f"\n## Decision Authority")
    for d in decides:
        lines.append(f"- {d}")

    bound_owns = bounds.get("owns", [])
    bound_forbidden = bounds.get("forbidden", [])
    if bound_owns or bound_forbidden:
        lines.append(f"\n## Domain Boundaries")
        lines.append(f"Owns: {', '.join(bound_owns)}")
        if bound_forbidden:
            lines.append(f"Forbidden: {', '.join(bound_forbidden)}")

    lines.append(f"\n## Available Skills\n{', '.join(skills)}")

    lines.append(f"\n## Quality Standards")
    lines.append(f"Target: {auto_cap.get('quality_target', 9)}/10")
    if philosophy:
        lines.append(f"Philosophy: {philosophy}")
    for p in principles:
        lines.append(f"- {p}")

    return "\n".join(lines)


def generate_profiles():
    """Generate google-agent-profiles.yaml from agent-schema.yaml."""
    schema = _load_yaml(AGENT_SCHEMA_PATH)
    agents = schema.get("agents", [])

    profiles = {}
    for agent in agents:
        aid = agent["agent_id"]
        instruction = _build_system_instruction(agent, schema)
        temp = TEMP_MAP.get(aid, 0.5)
        ctx_strategy = CONTEXT_STRATEGY.get(aid, "full_document_injection")
        search = GROUNDING_SEARCH.get(aid, False)

        profiles[aid] = {
            "system_instruction": instruction,
            "generation_config": {
                "temperature": temp,
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 16384,
            },
            "long_context_strategy": ctx_strategy,
            "grounding": {
                "google_search": search,
            },
        }

    output = {
        "schema_version": 1,
        "created": "2026-04-03",
        "description": "Per-agent Google Gemini profiles with grounding, safety, and generation config",
        "defaults": {
            "safety_settings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            ],
        },
        "profiles": profiles,
    }

    with open(PROFILES_PATH, "w") as f:
        yaml.dump(output, f, default_flow_style=False, sort_keys=False, allow_unicode=True, width=120)

    print(f"Generated {len(profiles)} Google agent profiles -> {PROFILES_PATH}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Google Gemini agent profiles setup")
    parser.add_argument("--generate", action="store_true", help="Generate profiles from agent-schema.yaml")
    args = parser.parse_args()

    if not args.generate:
        parser.print_help()
        sys.exit(1)

    ok = generate_profiles()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
