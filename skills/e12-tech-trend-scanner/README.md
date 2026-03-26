# e12-tech-trend-scanner — Technology Trend Scanner

> **Family:** F12 | **Domain:** E | **Tag:** dual-use | **Type:** executor
> **Schema:** v2 | **Runner:** v4.0+ | **Routing:** complex_reasoning

## What It Does

Takes a technology domain, industry context, time horizon, known technologies, and
specific focus areas. Produces a structured technology trend intelligence report with
maturity-classified trends, adoption timelines, disruption vectors, convergence analysis,
strategic implications, and actionable recommendations.

Works only from provided input — does not fabricate adoption statistics, market sizes,
or research citations. States analysis limitations explicitly.

## Inputs

| Name | Type | Required | Description |
|---|---|---|---|
| technology_domain | string | yes | Technology area to scan (min 20 chars) |
| industry_context | string | yes | Industry background, players, tech stack, pain points (min 20 chars) |
| time_horizon | string | no | near_term, mid_term, long_term, comprehensive (default: comprehensive) |
| known_technologies | string | no | Technologies user already tracks — scan goes beyond these |
| specific_focus | string | no | Priority angles: cost reduction, security, etc. |
| scan_depth | string | no | overview (5+ trends), detailed (8+), strategic (5+, deeper). Default: overview |

## Usage

```bash
python3 skills/skill-runner.py --skill e12-tech-trend-scanner --input '{
  "technology_domain": "AI and machine learning applications in mid-market B2B SaaS companies",
  "industry_context": "B2B SaaS market serving mid-market companies. Current stacks include CRM, support tools, analytics, and basic automation. $50K-$200K/year software spend.",
  "time_horizon": "comprehensive",
  "known_technologies": "GPT-4 chatbots, basic sentiment analysis, Zapier automation",
  "specific_focus": "cost reduction and customer retention",
  "scan_depth": "detailed"
}'
```

## Output Sections

1. Technology Landscape Overview
2. Emerging Technology Trends (each with maturity, timeline, confidence, relevance, barriers)
3. Maturity Assessment (summary mapping)
4. Disruption Analysis (specific vectors)
5. Technology Convergence (compound impacts or explicit no-convergence acknowledgment)
6. Strategic Implications (industry-grounded)
7. Recommendations (action verb + trend reference + time horizon)
8. Assumptions and Limitations

## Routing

| Step | Task Class | Default Alias | Model |
|---|---|---|---|
| step_2 (generate) | complex_reasoning | reasoning_claude | claude-sonnet-4-6 |
| step_3 (critic) | moderate | cheap_claude | claude-haiku-4-5 |
| step_4 (improve) | complex_reasoning | reasoning_claude | claude-sonnet-4-6 |

## Key Deterministic Checks

- 7 required sections
- Trend count scaled by depth (5/8/5)
- 80% maturity classification coverage
- Maturity-timeline coherence (with pilot exception)
- 60% confidence classification coverage
- 2+ specific disruption vectors
- Convergence points or explicit acknowledgment
- 30%+ known-tech differentiation (or coverage acknowledgment)
- Action verbs in recommendations
- 50% recommendation-trend linkage
- Industry term grounding in implications
- Anti-hallucination: citation fabrication, fabricated statistics
- Anti-buzzword: substance requirement per trend

## Composability

**Feeds into:** e12-market-research-analyst, f09-product-req-writer, f09-pricing-strategist, a01-arch-spec-writer
**Accepts from:** e08-comp-intel-synth
