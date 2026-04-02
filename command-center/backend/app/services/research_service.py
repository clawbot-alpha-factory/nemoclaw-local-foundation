"""
NemoClaw Command Center — ResearchService (E-14)

Pre-built research workflow templates that chain 2-3 skills via
SkillChainRunner.  Each template maps a high-level research intent
to a concrete skill chain with proper initial inputs.

Templates:
  social_intelligence  → int-05 → int-01 → cnt-10
  competitor_analysis  → k51 → e08-comp-intel-synth → int-04
  market_research      → e12-market-research-analyst → int-02 → e08-kb-article-writer
  trend_detection      → cnt-10-viral-pattern-analyzer → int-02 → f09-pricing-strategist

NEW FILE: command-center/backend/app/services/research_service.py
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.domain.engine_models import ChainRequest, LLMTier

logger = logging.getLogger("cc.research")


# ── Template Definitions ─────────────────────────────────────────────


@dataclass(frozen=True)
class ResearchTemplate:
    """Immutable definition of a research workflow template."""

    template_id: str
    name: str
    description: str
    chain: list[str]
    required_inputs: list[str]
    optional_inputs: list[str] = field(default_factory=list)
    default_tier: LLMTier = LLMTier.STANDARD


TEMPLATES: dict[str, ResearchTemplate] = {
    "social_intelligence": ResearchTemplate(
        template_id="social_intelligence",
        name="Social Intelligence",
        description=(
            "Cross-platform scraping → comment signal analysis → "
            "viral pattern detection.  Reveals audience sentiment "
            "and engagement patterns across platforms."
        ),
        chain=["int-05", "int-01", "cnt-10"],
        required_inputs=["targets"],
        optional_inputs=["platforms"],
        default_tier=LLMTier.STANDARD,
    ),
    "competitor_analysis": ResearchTemplate(
        template_id="competitor_analysis",
        name="Competitor Analysis",
        description=(
            "Competitor scraping → competitive intelligence synthesis → "
            "reality-check validation.  Produces verified competitor "
            "intelligence with confidence scoring."
        ),
        chain=["k51", "e08-comp-intel-synth", "int-04"],
        required_inputs=["competitors"],
        optional_inputs=[],
        default_tier=LLMTier.STANDARD,
    ),
    "market_research": ResearchTemplate(
        template_id="market_research",
        name="Market Research",
        description=(
            "Market research analysis → demand pattern detection → "
            "knowledge-base article.  End-to-end market sizing with "
            "a publishable research report."
        ),
        chain=["e12-market-research-analyst", "int-02", "e08-kb-article-writer"],
        required_inputs=["topic"],
        optional_inputs=[],
        default_tier=LLMTier.COMPLEX,
    ),
    "trend_detection": ResearchTemplate(
        template_id="trend_detection",
        name="Trend Detection",
        description=(
            "Viral pattern analysis → demand pattern detection → "
            "pricing strategy.  Spots emerging trends and maps them "
            "to monetisation opportunities."
        ),
        chain=["cnt-10-viral-pattern-analyzer", "int-02", "f09-pricing-strategist"],
        required_inputs=["niche"],
        optional_inputs=[],
        default_tier=LLMTier.STANDARD,
    ),
}


# ── Service ──────────────────────────────────────────────────────────


class ResearchService:
    """
    Provides pre-built research workflow templates that submit
    skill chains through SkillChainRunner.

    Usage:
        result = research_service.run("social_intelligence", {
            "targets": "Nike, Adidas",
            "platforms": "twitter, reddit",
        })
    """

    def __init__(self, chain_runner):
        """
        Args:
            chain_runner: SkillChainRunner instance for chain submission.
        """
        self.chain_runner = chain_runner
        self._history: list[dict[str, Any]] = []
        logger.info("ResearchService initialized with %d templates", len(TEMPLATES))

    # ── Public API ────────────────────────────────────────────────────

    def list_templates(self) -> list[dict[str, Any]]:
        """Return metadata for every available template."""
        return [
            {
                "template_id": t.template_id,
                "name": t.name,
                "description": t.description,
                "chain": t.chain,
                "required_inputs": t.required_inputs,
                "optional_inputs": t.optional_inputs,
                "default_tier": t.default_tier.value,
            }
            for t in TEMPLATES.values()
        ]

    def get_template(self, template_id: str) -> dict[str, Any] | None:
        """Return metadata for a single template, or None."""
        t = TEMPLATES.get(template_id)
        if t is None:
            return None
        return {
            "template_id": t.template_id,
            "name": t.name,
            "description": t.description,
            "chain": t.chain,
            "required_inputs": t.required_inputs,
            "optional_inputs": t.optional_inputs,
            "default_tier": t.default_tier.value,
        }

    def run(
        self,
        template_id: str,
        inputs: dict[str, str],
        agent_id: str = "",
        tier: LLMTier | None = None,
    ) -> dict[str, Any]:
        """
        Execute a research template.

        Args:
            template_id: One of the registered template IDs.
            inputs: Key-value inputs; must satisfy required_inputs.
            agent_id: Optional agent identity for tracing.
            tier: Override the template's default LLM tier.

        Returns:
            Dict with chain_id, template, status, and submitted_at.

        Raises:
            ValueError: Unknown template or missing required inputs.
        """
        template = TEMPLATES.get(template_id)
        if template is None:
            raise ValueError(
                f"Unknown research template '{template_id}'. "
                f"Available: {list(TEMPLATES.keys())}"
            )

        # Validate required inputs
        missing = [k for k in template.required_inputs if not inputs.get(k)]
        if missing:
            raise ValueError(
                f"Template '{template_id}' requires inputs: {missing}"
            )

        effective_tier = tier or template.default_tier

        # Build chain request
        request = ChainRequest(
            chain=list(template.chain),
            initial_inputs=inputs,
            agent_id=agent_id,
            tier=effective_tier,
        )

        chain = self.chain_runner.submit_chain(request)

        result = {
            "chain_id": chain.chain_id,
            "template": template_id,
            "chain": template.chain,
            "inputs": inputs,
            "agent_id": agent_id,
            "tier": effective_tier.value,
            "status": chain.status.value,
            "submitted_at": datetime.utcnow().isoformat(),
        }

        self._history.append(result)

        logger.info(
            "Research '%s' submitted → chain %s (%d steps)",
            template_id,
            chain.chain_id[:8],
            len(template.chain),
        )

        return result

    def get_history(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return recent research submissions (newest first)."""
        return list(reversed(self._history[-limit:]))
