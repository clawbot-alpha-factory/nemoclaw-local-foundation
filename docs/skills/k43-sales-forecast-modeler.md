# Sales Forecast Modeler

**ID:** `k43-sales-forecast-modeler` | **Version:** 1.0.0 | **Family:** K43 | **Domain:** K | **Type:** analyzer | **Tag:** sales

## Description

Produces revenue forecasts based on pipeline data, historical conversion rates, and market signals.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `pipeline_summary` | string | Yes | Summary of current pipeline and historical data |
| `forecast_horizon` | string | No | Forecast period |

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

- **Output Type:** sales_analyzer_output

## Example Usage

```json
{
  "inputs": {
    "pipeline_summary": "Current pipeline: 12 active deals worth $127,000 total. Historical close rate by stage: Discovery 15 percent, Proposal 35 percent, Negotiation 62 percent. Average deal cycle: 21 days. Last quarter: $48,000 closed from $156,000 pipeline. Monthly new leads: averaging 28 with 40 percent qualification rate. Average deal size trending up from $8,500 to $11,200 over past 90 days.",
    "forecast_horizon": "90_days"
  }
}
```
