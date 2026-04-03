# Experiment Decision Engine

**ID:** `rev-25-experiment-decision-engine` | **Version:** 1.0.0 | **Type:** analyzer | **Tag:** revenue

## Description

Kill/scale decisions based on conversion thresholds. If conversion < threshold → kill. If ROI > threshold → scale. Completes autonomous loop.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `experiment_data` | string | Yes | Experiment results: variants, impressions, conversions, costs, revenue |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string |  |
| `envelope_file` | file_path |  |
| `insight` | string |  |
| `recommended_action` | string |  |
| `trigger_skill` | string |  |
| `confidence` | float |  |

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=N/A, max_improvements=N/A
- **Max Execution:** 120s
- **Max Cost:** $0.3

## Example Usage

```json
{
  "inputs": {
    "experiment_data": "Experiment: Landing page headline test. Duration: 10 days. Variant A ('Automate Your Sales Pipeline with AI'): 1,200 impressions, 28 signups (2.3 percent conversion), $840 ad spend, 2 paid conversions ($298 revenue). Variant B ('Close 3x More Deals Without Hiring SDRs'): 1,180 impressions, 41 signups (3.5 percent conversion), $826 ad spend, 5 paid conversions ($745 revenue). Variant C ('AI Sales Automation for Growing Teams'): 1,150 impressions, 22 signups (1.9 percent conversion), $810 ad spend, 1 paid conversion ($149 revenue)."
  }
}
```
