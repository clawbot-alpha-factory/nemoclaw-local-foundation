# Budget Allocator

**ID:** `k45-budget-allocator` | **Version:** 1.0.0 | **Family:** K45 | **Domain:** K | **Type:** analyzer | **Tag:** marketing

## Description

Recommends optimal budget allocation across channels based on performance data, goals, and constraints.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `channel_performance` | string | Yes | Performance data per channel (spend, leads, conversions) |
| `total_budget` | string | Yes | Total available budget |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | The generated output |
| `result_file` | file_path | Path to the markdown artifact |
| `envelope_file` | file_path | Path to the JSON envelope for skill chaining |

## Steps

- **step_1** — Parse input and prepare analysis context (`local`, `general_short`)
- **step_2** — Generate primary output (`llm`, `moderate`)
- **step_3** — Evaluate output quality (`critic`, `moderate`)
- **step_5** — Validate and write artifact (`local`, `general_short`)

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=N/A, max_improvements=N/A
- **Max Execution:** 120s
- **Max Cost:** $0.3

## Composability

- **Output Type:** marketing_analyzer_output

## Example Usage

```json
{
  "inputs": {
    "channel_performance": "Google Ads: $1,200 spent, 18 leads, 4 conversions, $8,400 revenue, CPA $300. LinkedIn Ads: $800 spent, 12 leads, 2 conversions, $5,200 revenue, CPA $400. Content/SEO: $500 spent (writer fees), 22 leads, 5 conversions, $11,000 revenue, CPA $100. Email Marketing: $200 spent (tooling), 8 leads, 3 conversions, $7,500 revenue, CPA $67. Cold Outreach: $300 spent (tooling), 15 leads, 1 conversion, $3,200 revenue, CPA $300.",
    "total_budget": "$5,000 per month"
  }
}
```
