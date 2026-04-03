# Funnel Conversion Analyzer

**ID:** `rev-05-funnel-conversion-analyzer` | **Version:** 1.0.0 | **Type:** analyzer | **Tag:** revenue

## Description

Identifies where leads drop off. Outputs bottleneck report + fix recommendations per stage. Enforced action output.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `funnel_data` | string | Yes | Stage-by-stage conversion data |
| `funnel_type` | string | No | Funnel type: sales, content, onboarding |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | The generated output |
| `result_file` | file_path | Path to the markdown artifact |
| `envelope_file` | file_path | Path to JSON envelope for skill chaining |
| `insight` | string | Key insight from analysis |
| `recommended_action` | string | Specific action to take |
| `trigger_skill` | string | Skill ID to trigger (or null to stop) |
| `confidence` | float | Confidence score 0-1 |

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=N/A, max_improvements=N/A
- **Max Execution:** 120s
- **Max Cost:** $0.3

## Composability

- **Output Type:** revenue_analyzer_output

## Example Usage

```json
{
  "inputs": {
    "funnel_data": "Stage 1 - Awareness: 4,200 website visitors. Stage 2 - Interest: 380 resource downloads (9.0 percent). Stage 3 - Consideration: 85 demo requests (22.4 percent). Stage 4 - Evaluation: 42 demos completed (49.4 percent). Stage 5 - Decision: 28 proposals sent (66.7 percent). Stage 6 - Close: 11 deals won (39.3 percent). Total revenue: $127,500. Period: March 2026. Notable: demo-to-proposal drop is 17 percent worse than February.",
    "funnel_type": "sales"
  }
}
```
