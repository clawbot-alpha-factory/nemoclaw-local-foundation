#!/usr/bin/env python3
"""
NemoClaw Agent Context Builder v1.0.0
Builds enriched agent context for LLM calls across all providers.

Provides:
  - build_agent_context(agent_id, task_class, project_id) → dict
  - format_for_provider(context, provider) → str
  - load_agent_schema() — mtime-cached agent-schema.yaml loader
"""

import json
import logging
import threading
from datetime import date
from pathlib import Path

from lib.config_loader import (
    REPO,
    _load_yaml,
    _get_mtime,
    _load_cached,
    _cache_lock,
    load_budget_config,
)

logger = logging.getLogger("nemoclaw.agent_context")

AGENT_SCHEMA = REPO / "config" / "agents" / "agent-schema.yaml"
CAPABILITY_REGISTRY = REPO / "config" / "agents" / "capability-registry.yaml"
WORK_LOGS_DIR = Path.home() / ".nemoclaw" / "work-logs"

_agent_schema_cache = (None, 0.0)
_capability_cache = (None, 0.0)


def load_agent_schema():
    """Load agent-schema.yaml with mtime-based cache invalidation (thread-safe)."""
    global _agent_schema_cache
    data, cached_mtime = _agent_schema_cache
    mtime = _get_mtime(AGENT_SCHEMA)
    if data is not None and mtime == cached_mtime:
        return data
    with _cache_lock:
        data, _agent_schema_cache = _load_cached(AGENT_SCHEMA, _agent_schema_cache)
        return data


def _load_capability_registry():
    """Load capability-registry.yaml with mtime cache."""
    global _capability_cache
    data, cached_mtime = _capability_cache
    mtime = _get_mtime(CAPABILITY_REGISTRY)
    if data is not None and mtime == cached_mtime:
        return data
    with _cache_lock:
        data, _capability_cache = _load_cached(CAPABILITY_REGISTRY, _capability_cache)
        return data


def _read_recent_work(agent_id):
    """Read today's work log for an agent. Returns summary string or None."""
    try:
        log_file = WORK_LOGS_DIR / agent_id / f"{date.today().isoformat()}.jsonl"
        if not log_file.exists():
            return None
        actions = []
        with open(log_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                action = entry.get("action", "unknown")
                details = entry.get("details", "")
                if details:
                    actions.append(f"{action}: {details[:80]}")
                else:
                    actions.append(action)
        if not actions:
            return None
        return f"{len(actions)} actions today: " + "; ".join(actions[:5])
    except Exception:
        return None


def _find_agent(schema, agent_id):
    """Find agent dict by agent_id in schema['agents'] list."""
    for agent in schema.get("agents", []):
        if agent.get("agent_id") == agent_id:
            return agent
    return None


def _build_team_roster(schema):
    """Build lightweight roster of all agents."""
    roster = []
    for agent in schema.get("agents", []):
        roster.append({
            "agent_id": agent["agent_id"],
            "display_name": agent.get("display_name", ""),
            "title": agent.get("title", ""),
            "authority_level": agent.get("authority_level", 0),
        })
    return roster


def build_agent_context(agent_id, task_class="moderate", project_id=None):
    """Build enriched context dict for an agent.

    Args:
        agent_id: Agent identifier from agent-schema.yaml.
        task_class: Routing task class for this call.
        project_id: Optional project context.

    Returns:
        dict with agent identity, authority, skills, budget, team, etc.
        None if agent_id not found.
    """
    schema = load_agent_schema()
    agent = _find_agent(schema, agent_id)
    if agent is None:
        logger.warning("Agent not found: %s", agent_id)
        return None

    # Domain boundaries
    boundaries = schema.get("domain_boundaries", {}).get(agent_id, {})

    # Routing profile
    routing_profile = schema.get("routing_profiles", {}).get(agent_id, {})

    # Quality requirements from autonomous_capability
    auto_cap = agent.get("autonomous_capability", {})
    quality = {
        "quality_target": auto_cap.get("quality_target", 9),
        "on_quality_below_8": auto_cap.get("on_quality_below_8", ""),
        "can_self_improve": auto_cap.get("can_self_improve", False),
    }

    # Identity fields
    identity = agent.get("identity", {})

    # Skills
    skills = agent.get("skills", {})

    # Budget state
    try:
        budget = load_budget_config()
        budget_state = {
            provider: {
                "total_usd": info.get("total_usd", 0),
                "threshold_warn": info.get("threshold_warn", 0.9),
            }
            for provider, info in budget.get("budgets", {}).items()
        }
    except Exception:
        budget_state = {}

    # Recent work
    recent_work = _read_recent_work(agent_id)

    # Team roster
    team = _build_team_roster(schema)

    # Behavior mode
    behavior = schema.get("behavior_modes", {}).get("work", {})

    # LLM worker limits per tier (employees are fixed, workers are disposable)
    tier_mapping = {"structured_short": 1, "general_short": 1, "vision": 1,
                    "moderate": 2, "long_document": 2,
                    "complex_reasoning": 3, "code": 3, "agentic": 3, "deep_reasoning": 3,
                    "premium": 4, "strategic": 4}
    task_tier = tier_mapping.get(task_class, 2)
    worker_limits = {1: 6, 2: 6, 3: 8, 4: 15}
    max_parallel_workers = worker_limits.get(task_tier, 6)

    context = {
        "agent_id": agent_id,
        "display_name": agent.get("display_name", ""),
        "title": agent.get("title", ""),
        "name": identity.get("name", ""),
        "authority_level": agent.get("authority_level", 0),
        "role": agent.get("role", ""),
        "owns": agent.get("owns", []),
        "decides": agent.get("decides", []),
        "domain_boundaries": boundaries,
        "routing_profile": routing_profile,
        "skills_primary": skills.get("primary", []),
        "skills_future": skills.get("future", []),
        "quality_requirements": quality,
        "work_philosophy": identity.get("work_philosophy", ""),
        "operating_principles": identity.get("operating_principles", []),
        "behavior_mode": behavior,
        "team_roster": team,
        "budget_state": budget_state,
        "recent_work": recent_work,
        "task_class": task_class,
        "task_tier": task_tier,
        "max_parallel_workers": max_parallel_workers,
        "project_id": project_id,
    }
    return context


def format_for_provider(context, provider):
    """Format agent context optimally for a specific LLM provider.

    Args:
        context: dict from build_agent_context().
        provider: 'openai', 'anthropic', 'google', or other.

    Returns:
        Formatted string for use as system message content.
    """
    if context is None:
        return ""

    if provider == "anthropic":
        return _format_anthropic(context)
    elif provider == "google":
        return _format_google(context)
    else:
        return _format_openai(context)


def _format_anthropic(ctx):
    """Format context with XML tags for Claude."""
    parts = []

    parts.append(f"<agent_identity>")
    parts.append(f"You are {ctx['name']}, the {ctx['display_name']} ({ctx['title']}) of NemoClaw.")
    parts.append(f"Authority Level: {ctx['authority_level']}.")
    parts.append(f"</agent_identity>")

    parts.append(f"\n<role>{ctx['role']}</role>")

    parts.append(f"\n<authority>")
    parts.append(f"<owns>{', '.join(ctx['owns'])}</owns>")
    parts.append(f"<decides>{'; '.join(ctx['decides'])}</decides>")
    parts.append(f"</authority>")

    bounds = ctx.get("domain_boundaries", {})
    if bounds:
        parts.append(f"\n<domain_boundaries>")
        parts.append(f"<owns>{', '.join(bounds.get('owns', []))}</owns>")
        parts.append(f"<forbidden>{', '.join(bounds.get('forbidden', []))}</forbidden>")
        parts.append(f"</domain_boundaries>")

    parts.append(f"\n<skills>")
    parts.append(f"Primary: {', '.join(ctx['skills_primary'])}")
    if ctx['skills_future']:
        parts.append(f"Future: {', '.join(ctx['skills_future'])}")
    parts.append(f"</skills>")

    parts.append(f"\n<quality_standards>")
    qr = ctx["quality_requirements"]
    parts.append(f"Quality target: {qr['quality_target']}/10")
    parts.append(f"Self-improve: {qr['can_self_improve']}")
    if ctx["work_philosophy"]:
        parts.append(f"Philosophy: {ctx['work_philosophy']}")
    if ctx["operating_principles"]:
        for p in ctx["operating_principles"]:
            parts.append(f"- {p}")
    parts.append(f"</quality_standards>")

    bm = ctx.get("behavior_mode", {})
    if bm:
        parts.append(f"\n<behavior_mode>")
        parts.append(f"Standard: {bm.get('standard', '')}")
        parts.append(f"Quality: {bm.get('quality_target', '')}")
        parts.append(f"Revenue focus: {bm.get('revenue_focus', '')}")
        parts.append(f"</behavior_mode>")

    parts.append(f"\n<team>")
    for t in ctx["team_roster"]:
        parts.append(f"- {t['display_name']} ({t['title']}, L{t['authority_level']})")
    parts.append(f"</team>")

    if ctx.get("recent_work"):
        parts.append(f"\n<recent_work>{ctx['recent_work']}</recent_work>")

    return "\n".join(parts)


def _format_openai(ctx):
    """Format context as structured JSON for OpenAI."""
    payload = {
        "agent": {
            "id": ctx["agent_id"],
            "name": ctx["name"],
            "display_name": ctx["display_name"],
            "title": ctx["title"],
            "authority_level": ctx["authority_level"],
        },
        "role": ctx["role"],
        "owns": ctx["owns"],
        "decides": ctx["decides"],
        "domain_boundaries": ctx.get("domain_boundaries", {}),
        "skills": {
            "primary": ctx["skills_primary"],
            "future": ctx["skills_future"],
        },
        "quality": {
            "target": ctx["quality_requirements"]["quality_target"],
            "can_self_improve": ctx["quality_requirements"]["can_self_improve"],
            "work_philosophy": ctx["work_philosophy"],
            "operating_principles": ctx["operating_principles"],
        },
        "team": [
            {"name": t["display_name"], "title": t["title"], "level": t["authority_level"]}
            for t in ctx["team_roster"]
        ],
        "budget": ctx.get("budget_state", {}),
    }
    if ctx.get("recent_work"):
        payload["recent_work"] = ctx["recent_work"]
    if ctx.get("project_id"):
        payload["project_id"] = ctx["project_id"]
    return json.dumps(payload, indent=2)


def _format_google(ctx):
    """Format context as markdown for Gemini."""
    parts = []

    parts.append(f"## Agent Identity")
    parts.append(f"You are {ctx['name']}, the {ctx['display_name']} ({ctx['title']}) of NemoClaw.")
    parts.append(f"Authority Level: {ctx['authority_level']}.")

    parts.append(f"\n## Role\n{ctx['role']}")

    parts.append(f"\n## Domain Ownership\n" + ", ".join(ctx["owns"]))

    parts.append(f"\n## Decision Authority")
    for d in ctx["decides"]:
        parts.append(f"- {d}")

    bounds = ctx.get("domain_boundaries", {})
    if bounds:
        parts.append(f"\n## Domain Boundaries")
        parts.append(f"Owns: {', '.join(bounds.get('owns', []))}")
        forbidden = bounds.get("forbidden", [])
        if forbidden:
            parts.append(f"Forbidden: {', '.join(forbidden)}")

    parts.append(f"\n## Available Skills\nPrimary: {', '.join(ctx['skills_primary'])}")

    parts.append(f"\n## Quality Standards")
    qr = ctx["quality_requirements"]
    parts.append(f"Target: {qr['quality_target']}/10")
    if ctx["work_philosophy"]:
        parts.append(f"Philosophy: {ctx['work_philosophy']}")
    if ctx["operating_principles"]:
        for p in ctx["operating_principles"]:
            parts.append(f"- {p}")

    parts.append(f"\n## Team")
    for t in ctx["team_roster"]:
        parts.append(f"- {t['display_name']} ({t['title']}, L{t['authority_level']})")

    if ctx.get("recent_work"):
        parts.append(f"\n## Recent Work\n{ctx['recent_work']}")

    return "\n".join(parts)
