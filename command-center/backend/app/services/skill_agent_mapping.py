"""
NemoClaw Execution Engine — Skill-Agent Mapping (E-9)

Many-to-many mapping between skills and agents.
Multiple agents can share the same skill for quality + redundancy.

NEW FILE: command-center/backend/app/services/skill_agent_mapping.py
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("cc.skill_map")

# ── MASTER MAPPING ──────────────────────────────────────────────────
# Key = agent_id, Value = list of skill IDs this agent can execute.
# Skills appear under MULTIPLE agents when overlap improves quality.

AGENT_SKILL_MAP: dict[str, list[str]] = {
    # ── SALES & OUTREACH LEAD ──
    # Primary revenue executor: owns deals, outreach, follow-ups
    "sales_outreach_lead": [
        # Revenue Core
        "rev-01-autonomous-sales-closer",
        "rev-02-lead-qualification-engine",
        "rev-07-deal-progression-tracker",
        "rev-09-payment-execution-engine",
        "rev-10-lead-source-engine",
        "rev-11-follow-up-enforcer",
        "rev-13-live-experiment-runner",
        # Outreach (ALL)
        "out-01-multi-touch-sequence-builder",
        "out-02-email-executor",
        "out-03-linkedin-action-planner",
        "out-04-follow-up-intelligence",
        "out-05-outreach-personalization-engine",
        "out-06-campaign-performance-optimizer",
        "out-07-whatsapp-message-composer",
        "out-08-comment-conversion-engine",
        # Business
        "biz-01-proposal-generator",
        "biz-02-contract-drafter",
        "biz-03-invoice-generator",
    ],

    # ── MARKETING & CAMPAIGNS LEAD ──
    # Content + campaigns + analytics
    "marketing_campaigns_lead": [
        # Content (ALL)
        "cnt-01-viral-hook-generator",
        "cnt-02-instagram-reel-script-writer",
        "cnt-03-tiktok-content-engine",
        "cnt-04-content-repurposer",
        "cnt-05-youtube-script-writer",
        "cnt-06-content-calendar-builder",
        "cnt-07-content-performance-analyzer",
        "cnt-08-cross-channel-distributor",
        "cnt-09-social-posting-executor",
        "cnt-10-viral-pattern-analyzer",
        # Revenue (campaign-related)
        "rev-03-revenue-attribution-analyzer",
        "rev-05-funnel-conversion-analyzer",
        "rev-13-live-experiment-runner",  # shared with sales
        # Outreach (campaign optimization)
        "out-05-outreach-personalization-engine",  # shared with sales
        "out-06-campaign-performance-optimizer",  # shared with sales
        "out-08-comment-conversion-engine",  # shared with sales
        # Intelligence
        "int-01-comment-signal-scraper",
        "int-02-demand-pattern-analyzer",
        "rev-17-demand-signal-miner",
    ],

    # ── CLIENT SUCCESS LEAD ──
    # Post-sale: onboarding, health, retention, upsell
    "client_success_lead": [
        # Business Ops (ALL)
        "biz-04-client-onboarding-sequence",
        "biz-05-client-health-monitor",
        "biz-06-upsell-opportunity-detector",
        "biz-07-competitive-intelligence-monitor",
        "biz-08-social-proof-engine",
        # Revenue
        "rev-07-deal-progression-tracker",  # shared with sales
        "rev-11-follow-up-enforcer",  # shared with sales
        "rev-14-revenue-loop-enforcer",
        # Outreach (client comms)
        "out-02-email-executor",  # shared — sends client emails
        "out-07-whatsapp-message-composer",  # shared — client WhatsApp
    ],

    # ── GROWTH & REVENUE LEAD ──
    # Strategy + orchestration + revenue optimization
    "growth_revenue_lead": [
        # Revenue Core (strategic)
        "rev-04-offer-optimization-engine",
        "rev-05-funnel-conversion-analyzer",
        "rev-06-revenue-orchestrator",
        "rev-08-agentic-service-packager",
        "rev-09-payment-execution-engine",  # shared
        "rev-12-risk-capital-allocator",
        "rev-14-revenue-loop-enforcer",
        "rev-15-playbook-memory-engine",
        "rev-16-speed-to-revenue-optimizer",
        "rev-18-instant-offer-launcher",
        "rev-19-system-learning-engine",
        # Scale (ALL)
        "scl-01-affiliate-program-engine",
        "scl-02-partnership-proposal-writer",
        "scl-03-webinar-funnel-builder",
        "scl-04-podcast-guest-pitch-writer",
        "scl-05-community-growth-engine",
        "scl-06-growth-experiment-designer",
        "scl-07-cross-channel-scheduler",
        "scl-08-revenue-dashboard-generator",
        "scl-09-niche-domination-engine",
        "scl-10-micro-saas-generator",
        # Intelligence
        "int-03-opportunity-offer-generator",
    ],

    # ── STRATEGY LEAD ──
    # Market intelligence, risk, competitive analysis
    "strategy_lead": [
        "int-01-comment-signal-scraper",  # shared with marketing
        "int-02-demand-pattern-analyzer",  # shared with marketing
        "int-03-opportunity-offer-generator",  # shared with growth
        "int-04-reality-check-engine",
        "rev-03-revenue-attribution-analyzer",  # shared with marketing
        "rev-04-offer-optimization-engine",  # shared with growth
        "rev-12-risk-capital-allocator",  # shared with growth
        "rev-15-playbook-memory-engine",  # shared with growth
        "rev-17-demand-signal-miner",  # shared with marketing
        "biz-07-competitive-intelligence-monitor",  # shared with client success
    ],

    # ── NARRATIVE & CONTENT LEAD ──
    # Content quality, brand consistency, storytelling
    "narrative_content_lead": [
        "cnt-01-viral-hook-generator",  # shared with marketing
        "cnt-02-instagram-reel-script-writer",  # shared
        "cnt-03-tiktok-content-engine",  # shared
        "cnt-04-content-repurposer",  # shared
        "cnt-05-youtube-script-writer",  # shared
        "cnt-06-content-calendar-builder",  # shared
        "cnt-10-viral-pattern-analyzer",  # shared
        "biz-08-social-proof-engine",  # shared with client success
        "scl-04-podcast-guest-pitch-writer",  # shared with growth
    ],

    # ── OPERATIONS LEAD ──
    # Orchestration, scheduling, enforcement, dashboards
    "operations_lead": [
        "rev-06-revenue-orchestrator",  # shared with growth
        "rev-14-revenue-loop-enforcer",  # shared with growth + client
        "rev-19-system-learning-engine",  # shared with growth
        "scl-07-cross-channel-scheduler",  # shared with growth
        "scl-08-revenue-dashboard-generator",  # shared with growth
    ],

    # ── EXECUTIVE OPERATOR ──
    # Oversight: risk, revenue, strategy (read + override access)
    "executive_operator": [
        "rev-06-revenue-orchestrator",  # shared
        "rev-12-risk-capital-allocator",  # shared
        "rev-16-speed-to-revenue-optimizer",  # shared
        "rev-19-system-learning-engine",  # shared
        "int-04-reality-check-engine",  # shared with strategy
        "scl-08-revenue-dashboard-generator",  # shared
    ],

    # ── PRODUCT ARCHITECT ──
    # Product design, MVP, technical architecture
    "product_architect": [
        "scl-10-micro-saas-generator",  # shared with growth
        "rev-08-agentic-service-packager",  # shared with growth
    ],

    # ── ENGINEERING LEAD ──
    # Technical execution, system health
    "engineering_lead": [
        "rev-19-system-learning-engine",  # shared
        "scl-10-micro-saas-generator",  # shared
    ],
}


class SkillAgentMappingService:
    """
    Many-to-many skill ↔ agent mapping.

    Features:
    - Get all skills for an agent
    - Get all agents for a skill
    - Stats on coverage
    - Shared skills report
    """

    def __init__(self):
        self._agent_to_skills = AGENT_SKILL_MAP
        self._skill_to_agents: dict[str, list[str]] = {}
        self._build_reverse_map()
        logger.info(
            "SkillAgentMappingService initialized (%d agents, %d unique skills, %d total assignments)",
            len(self._agent_to_skills),
            len(self._skill_to_agents),
            sum(len(v) for v in self._agent_to_skills.values()),
        )

    def _build_reverse_map(self) -> None:
        """Build skill → agents reverse lookup."""
        self._skill_to_agents = {}
        for agent, skills in self._agent_to_skills.items():
            for skill in skills:
                if skill not in self._skill_to_agents:
                    self._skill_to_agents[skill] = []
                self._skill_to_agents[skill].append(agent)

    def get_agent_skills(self, agent_id: str) -> list[str]:
        """Get all skills assigned to an agent."""
        return self._agent_to_skills.get(agent_id, [])

    def get_skill_agents(self, skill_id: str) -> list[str]:
        """Get all agents that can execute a skill."""
        return self._skill_to_agents.get(skill_id, [])

    def get_best_agent_for_skill(self, skill_id: str) -> str | None:
        """Get primary agent for a skill (first in list = primary owner)."""
        agents = self._skill_to_agents.get(skill_id, [])
        return agents[0] if agents else None

    def is_shared_skill(self, skill_id: str) -> bool:
        """Check if skill is shared across multiple agents."""
        return len(self._skill_to_agents.get(skill_id, [])) > 1

    def get_shared_skills(self) -> dict[str, list[str]]:
        """Get all skills shared by multiple agents."""
        return {
            skill: agents
            for skill, agents in self._skill_to_agents.items()
            if len(agents) > 1
        }

    def get_unassigned_skills(self, all_skill_ids: list[str]) -> list[str]:
        """Find skills not assigned to any agent."""
        return [s for s in all_skill_ids if s not in self._skill_to_agents]

    def get_stats(self) -> dict[str, Any]:
        """Get mapping statistics."""
        total_assignments = sum(len(v) for v in self._agent_to_skills.values())
        unique_skills = len(self._skill_to_agents)
        shared = self.get_shared_skills()
        return {
            "agents": len(self._agent_to_skills),
            "unique_skills_mapped": unique_skills,
            "total_assignments": total_assignments,
            "shared_skills": len(shared),
            "avg_skills_per_agent": round(total_assignments / max(len(self._agent_to_skills), 1), 1),
            "per_agent": {
                agent: len(skills) for agent, skills in self._agent_to_skills.items()
            },
            "top_shared": {
                skill: agents for skill, agents in sorted(
                    shared.items(), key=lambda x: len(x[1]), reverse=True
                )[:10]
            },
        }
