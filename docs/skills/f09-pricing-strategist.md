# Pricing Strategy Analyst

**ID:** `f09-pricing-strategist` | **Version:** 1.0.0 | **Family:** F09 | **Domain:** F | **Type:** executor | **Tag:** dual-use

## Description

Takes a product/service description, target market, cost structure, and competitive context, produces a complete pricing strategy with model recommendation, tier/plan structure with specific price points, feature-to-tier mapping, grounded revenue projections, competitive positioning, risk analysis, and implementation recommendations. Works only from provided input — does not invent market data or reference external research unless provided.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `product_description` | string | Yes | What the product/service is, who it's for, core value proposition |
| `target_market` | string | Yes | Who buys this: segments, size signals, willingness-to-pay context |
| `cost_structure` | string | No | Fixed costs, variable costs per unit/user, infrastructure costs, margins |
| `competitive_context` | string | No | Competitors, their pricing, market positioning, gaps |
| `pricing_goals` | string | No | What pricing should optimize for: revenue maximization, market penetration, premium positioning, simplicity |
| `scope` | string | No | initial_launch (conservative, max 3 tiers), mature (full 3-5 tiers), pivot (repositioning existing pricing) |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | The complete pricing strategy document in markdown |
| `result_file` | file_path | Path to the markdown artifact |
| `envelope_file` | file_path | Path to the JSON envelope |

## Steps

- **step_1** — Parse product context and identify pricing dimensions (`local`, `general_short`)
- **step_2** — Generate complete pricing strategy (`llm`, `complex_reasoning`)
- **step_3** — Evaluate pricing strategy completeness and analytical rigor (`critic`, `moderate`)
- **step_4** — Strengthen pricing strategy based on critic feedback (`llm`, `complex_reasoning`)
- **step_5** — Validate final pricing strategy and write artifact (`local`, `general_short`)

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=10, max_improvements=5
- **Max Execution:** 120s
- **Max Cost:** $0.15

## Declarative Guarantees

- Pricing model is explicitly named and justified
- Every tier has name, price, differentiated features, target audience, and justification
- Revenue projections reference input data or clearly derived computations, not invented figures
- If cost_structure missing, explicitly uses value-based pricing
- Competitive positioning addresses provided competitors when competitive_context given
- Risks are specific, not generic
- Each assumption relates to pricing logic and influences at least one output section
- For initial_launch scope: at least one tier has a concrete numeric price point
- For pivot scope: references prior state explicitly

## Composability

- **Output Type:** pricing_strategy
- **Can Feed Into:** d11-copywriting-specialist, j36-biz-idea-validator
- **Accepts Input From:** f09-product-req-writer, e12-market-research-analyst

## Example Usage

```json
{
  "skill_id": "f09-pricing-strategist",
  "inputs": {
    "product_description": "AI meeting assistant with transcription, summarization, and action item tracking for engineering teams",
    "target_market": "B2B SaaS companies with 50-500 employees",
    "competitive_pricing": "Otter.ai: 17 dollars per user per month, Fireflies: 19 dollars per user per month, Grain: 15 dollars per user per month",
    "cost_structure": "API costs approximately 0.02 dollars per minute of audio, infrastructure 500 dollars per month fixed",
    "pricing_scope": "mvp"
  }
}
```
