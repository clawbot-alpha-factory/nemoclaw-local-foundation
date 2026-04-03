# Revenue Dashboard Generator

**ID:** `scl-08-revenue-dashboard-generator` | **Version:** 1.0.0 | **Type:** generator | **Tag:** scale

## Description

Auto-generates weekly revenue report: pipeline value, conversion rates, channel ROI, forecast, action items.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `revenue_data` | string | Yes | Revenue metrics: pipeline, conversions, spend, revenue |
| `report_type` | string | No | Report frequency |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | The generated output |
| `result_file` | file_path | Path to the markdown artifact |
| `envelope_file` | file_path | Path to JSON envelope for skill chaining |

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=N/A, max_improvements=N/A
- **Max Execution:** 120s
- **Max Cost:** $0.35

## Composability

- **Output Type:** scale_generator_output

## Example Usage

```json
{
  "inputs": {
    "revenue_data": "Pipeline: $94,000 across 8 active deals. Closed this month: $34,500 (4 deals). Monthly target: $50,000. MRR: $12,800 from 85 active subscriptions. Churn: 2 customers ($298 MRR lost). New MRR added: $1,640. Ad spend: $2,476. Content costs: $500. Tooling costs: $340. LLM costs: $18.40. Total leads generated: 48. Qualified leads: 21. Demos completed: 14. Proposals sent: 8. Win rate: 39.3 percent. Average deal size: $11,200. Sales cycle: 21 days average.",
    "report_type": "weekly"
  }
}
```
