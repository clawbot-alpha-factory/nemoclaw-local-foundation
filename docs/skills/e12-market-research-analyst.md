# Market Research Analyst

**ID:** `e12-market-research-analyst` | **Version:** 1.0.0 | **Family:** F12 | **Domain:** E | **Type:** executor | **Tag:** dual-use

## Description

Takes a research topic, industry context, specific questions, and known data, produces a structured market research report with market overview, segmentation, trends, competitive landscape, opportunities, risk factors, and actionable recommendations. Works only from provided input — does not fabricate statistics, market sizes, or research citations. States data gaps explicitly.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `research_topic` | string | Yes | What to research: market, industry, technology, trend, or competitive question |
| `industry_context` | string | Yes | Industry/market background: known players, size signals, trends, regulations, geography |
| `specific_questions` | string | No | Specific questions the research should answer — drives focus |
| `known_data` | string | No | Any data the user already has: statistics, reports, findings, competitor info |
| `research_depth` | string | No | overview (high-level), detailed (deep with sub-segments), competitive_focus (competitor-centric) |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | The complete market research report in markdown |
| `result_file` | file_path | Path to the markdown artifact |
| `envelope_file` | file_path | Path to the JSON envelope |

## Steps

- **step_1** — Parse research context and identify analysis dimensions (`local`, `general_short`)
- **step_2** — Generate complete market research report (`llm`, `complex_reasoning`)
- **step_3** — Evaluate research completeness and analytical rigor (`critic`, `moderate`)
- **step_4** — Strengthen research based on critic feedback (`llm`, `complex_reasoning`)
- **step_5** — Validate final research report and write artifact (`local`, `general_short`)

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=10, max_improvements=5
- **Max Execution:** 120s
- **Max Cost:** $0.15

## Declarative Guarantees

- Market overview includes sizing context, qualitative scoping, or explicit data gap acknowledgment
- Segmentation identifies distinct segments with meaningful names (not Segment A/B)
- Trends are specific, not generic — count scales with depth (3 overview, 5 detailed)
- Competitive landscape names entities from input or provides archetypes when no data given
- Opportunities reference specific trends, segments, or competitive insights
- Risks are tied to market forces, competition, or constraints — not generic
- Recommendations contain actionable verbs and reference analysis sections
- No fabricated research citations or statistics — assumptions labeled explicitly
- Specific questions addressed when provided (60% minimum coverage)
- Known data integrated into analysis context, not just repeated

## Composability

- **Output Type:** market_research
- **Can Feed Into:** f09-product-req-writer, f09-pricing-strategist, d11-copywriting-specialist
- **Accepts Input From:** e12-tech-trend-scanner, e08-comp-intel-synth

## Example Usage

```json
{
  "skill_id": "e12-market-research-analyst",
  "inputs": {
    "research_topic": "AI-powered customer onboarding platforms for B2B SaaS companies",
    "industry_context": "B2B SaaS market serving mid-market companies with 50 to 500 employees"
  }
}
```
