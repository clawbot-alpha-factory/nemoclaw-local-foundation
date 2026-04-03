# Competitive Intelligence Synthesizer

**ID:** `e08-comp-intel-synth` | **Version:** 1.0.0 | **Family:** F08 | **Domain:** E | **Type:** executor | **Tag:** dual-use

## Description

Takes competitor data, industry context, and focus areas, produces structured competitive intelligence reports with SWOT analysis, market positioning, and prioritized strategic recommendations. Works only from provided data — no external knowledge, no web access, no fabrication.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `competitor_data` | string | Yes | Raw competitor information: names, products, pricing, funding, team, news, position |
| `focus_company` | string | Yes | The company whose competitive position is being analyzed |
| `industry_context` | string | Yes | Industry vertical, market segment, macro context |
| `analysis_priorities` | string | No | Specific strategic questions or focus areas to address |
| `report_depth` | string | No | Report depth: brief (1-2 pages), standard (3-5 pages), comprehensive (5-10 pages) |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | The structured competitive intelligence report |
| `result_file` | file_path | Path to the markdown artifact |
| `envelope_file` | file_path | Path to the JSON envelope |

## Steps

- **step_1** — Parse competitor data and structure analysis inputs (`local`, `general_short`)
- **step_2** — Generate competitive intelligence report (`llm`, `premium`)
- **step_3** — Evaluate report quality and analytical rigor (`critic`, `moderate`)
- **step_4** — Strengthen report based on critic feedback (`llm`, `premium`)
- **step_5** — Validate final report and write artifact (`local`, `general_short`)

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=10, max_improvements=5
- **Max Execution:** 120s
- **Max Cost:** $0.15

## Declarative Guarantees

- Every competitor from input data is covered with at least one analytical statement
- SWOT elements are grounded in provided input data; assumptions and data gaps are explicitly stated
- Strategic recommendations are linked to specific SWOT or positioning insights
- No fabricated statistics or claims not present in the input data
- Report depth matches the requested level
- Analysis priorities are explicitly addressed if provided
- Data gaps are surfaced in the report rather than filled with guesses

## Composability

- **Output Type:** competitive_intelligence_report
- **Can Feed Into:** f16-gtm-plan-writer, f18-sales-pitch-crafter, f09-product-req-writer

## Example Usage

```json
{
  "skill_id": "e08-comp-intel-synth",
  "inputs": {
    "competitor_data": "Confluence: Atlassian product, enterprise wiki, 60000 customers, priced at 5.75 per user. Coda: Series D startup, docs plus tables plus automation, growing in mid-market. Slite: Series A, async-first knowledge base for remote teams. Clickup Docs: part of Clickup project management suite, bundled free with PM tool.",
    "focus_company": "Notion",
    "industry_context": "Productivity software and knowledge management for teams",
    "analysis_priorities": "product differentiation and pricing strategy"
  }
}
```
