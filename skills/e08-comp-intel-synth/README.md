# e08-comp-intel-synth — Competitive Intelligence Synthesizer

> **Family:** F08 (Knowledge Management and Synthesis)
> **Domain:** E (Intelligence, Data, and Analytics)
> **Tag:** dual-use
> **Type:** executor
> **Schema:** v2
> **Runner:** >=4.0.0

## Purpose

Takes competitor data, industry context, and focus areas, produces structured
competitive intelligence reports with SWOT analysis, market positioning, and
prioritized strategic recommendations. Works only from provided data — no
external knowledge, no web access, no fabrication.

## Inputs

| Name | Type | Required | Description |
|---|---|---|---|
| `competitor_data` | string | yes | Raw competitor info |
| `focus_company` | string | yes | Company being analyzed |
| `industry_context` | string | yes | Industry/market context |
| `analysis_priorities` | string | no | Specific questions to address |
| `report_depth` | string | no | `brief`, `standard`, `comprehensive` |

## Steps

| Step | Name | Type | Description |
|---|---|---|---|
| step_1 | Parse competitor data and structure analysis inputs | local | Extract competitors, factual tokens, detect data gaps |
| step_2 | Generate competitive intelligence report | llm | Structured report with no external knowledge |
| step_3 | Evaluate report quality and analytical rigor | critic | Deterministic + LLM two-layer validation |
| step_4 | Strengthen report based on critic feedback | llm | Fix issues, loop back |
| step_5 | Validate final report and write artifact | local | Deterministic gate, hard-fail on critical violations |

## Deterministic Checks

- Required sections: Executive Summary, Competitor Profiles, SWOT, Positioning, Recommendations
- SWOT structured as bullet lists (non-empty)
- Competitor coverage: each must have analytical statement, not just mention
- Factual token preservation (F35 pattern)
- Banned fluff phrases (11 patterns)
- Report depth word count check

## Usage

```bash
~/nemoclaw-local-foundation/.venv313/bin/python \
  ~/nemoclaw-local-foundation/skills/skill-runner.py \
  --skill e08-comp-intel-synth \
  --input competitor_data 'Competitor A: $50M ARR, 200 employees, Series C...' \
  --input focus_company 'Our Company' \
  --input industry_context 'Enterprise SaaS, B2B analytics vertical' \
  --input report_depth standard
```

## Composable

- **Output type:** `competitive_intelligence_report`
- **Can feed into:** `f16-gtm-plan-writer`, `f18-sales-pitch-crafter`, `f09-product-req-writer`
