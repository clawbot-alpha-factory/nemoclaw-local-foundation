# f09-pricing-strategist — Pricing Strategy Analyst

**Family:** F09 | **Domain:** F | **Tag:** dual-use | **Type:** executor
**Schema:** v2 | **Runner:** v4.0+ | **Routing:** complex_reasoning

## What It Does

Takes a product/service description, target market, cost structure, and competitive context, then produces a complete pricing strategy document with pricing model recommendation, tier/plan structure, feature-to-tier mapping, grounded revenue projections, competitive positioning, risk analysis, assumptions, and implementation recommendations.

## Key Design Decisions

- **Revenue grounding:** Projections must reference 2+ numeric tokens from inputs OR use clearly derived computations. If insufficient data exists, the output must explicitly acknowledge it.
- **Tier differentiation:** Feature lists across tiers must not be identical. Each tier requires a target audience and justification for existing.
- **Value-based fallback:** When cost_structure is not provided, the skill explicitly switches to value-based pricing methodology.
- **Scope-driven generation:** initial_launch (max 3 tiers, conservative), mature (3-5 tiers, expansion revenue), pivot (references prior state, migration paths).
- **Anti-hallucination:** No external research claims unless provided in input. General assumptions must be labeled as such.
- **Concrete pricing:** For initial_launch, at least one tier must have a numeric price point (not just "contact us").
- **Pivot enforcement:** Pivot scope must reference prior state using markers like "currently", "existing", "changing from".

## Usage

```bash
.venv312/bin/python skills/skill-runner.py \
  --skill f09-pricing-strategist \
  --input product_description 'AI-powered document analysis SaaS for legal teams. Extracts clauses, flags risks, summarizes contracts.' \
  --input target_market 'Mid-market law firms (50-200 attorneys), corporate legal departments. Market: ~15000 firms in US. Budget: $500-$2000/month for legal tech tools.' \
  --input cost_structure 'Infrastructure: $0.03 per document processed (GPU inference). Fixed: $2000/month servers. Team: 2 engineers at $180k/year each. Support: $500/month.' \
  --input competitive_context 'Kira Systems: $50k+/year enterprise. Luminance: $30k+/year. ContractPodAi: undisclosed. Gap: no mid-market option under $500/month.' \
  --input pricing_goals 'Market penetration — capture mid-market before enterprise players move down' \
  --input scope 'initial_launch'
```

## Inputs

| Name | Required | Description |
|---|---|---|
| product_description | yes | What the product/service is, core value proposition (min 30 chars) |
| target_market | yes | Who buys: segments, size, willingness-to-pay (min 20 chars) |
| cost_structure | no | Costs — fixed, variable, infrastructure, margins |
| competitive_context | no | Competitors, their pricing, positioning |
| pricing_goals | no | What pricing optimizes for |
| scope | no | initial_launch (default), mature, pivot |

## Composability

- **Accepts input from:** f09-product-req-writer, e12-market-research-analyst
- **Can feed into:** d11-copywriting-specialist, j36-biz-idea-validator

## Deterministic Validation

- Required sections: Pricing Model, Tier/Plan Structure, Feature Mapping, Revenue Projections, Competitive Positioning, Risks, Implementation, Assumptions
- Pricing model explicitly named from known list
- 2+ tiers with differentiated features, each with name + price + target audience
- Revenue grounded in input data (2+ tokens, derivation language, or insufficient-data acknowledgment)
- Research claims only if from provided competitive_context
- Assumptions relate to pricing logic and influence output sections
- Scope-specific rules enforced (tier count, concrete pricing, pivot state reference)
