# Deal Pipeline Tracker

**ID:** `k40-deal-pipeline-tracker` | **Version:** 1.0.0 | **Family:** K40 | **Domain:** K | **Type:** analyzer | **Tag:** sales

## Description

Analyzes the current deal pipeline, identifies bottlenecks, stalled deals, and recommends next actions for each stage.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `pipeline_data` | string | Yes | Description of current pipeline deals and stages |
| `time_period` | string | No | Analysis time period |

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
    "pipeline_data": "Deal 1: Apex Digital - Discovery stage, $8,500, last activity 2 days ago. Deal 2: CloudFirst Solutions - Proposal sent, $15,000, last activity 5 days ago. Deal 3: NovaTech MENA - Negotiation, $22,000, last activity 1 day ago. Deal 4: DataBridge Analytics - Closed won, $12,000, signed yesterday. Deal 5: SwiftOps - Discovery stage, $6,000, last activity 9 days ago (stale). Total pipeline value: $63,500 across 5 deals.",
    "time_period": "this_quarter"
  }
}
```
