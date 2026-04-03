# Campaign Performance Optimizer

**ID:** `out-06-campaign-performance-optimizer` | **Version:** 1.0.0 | **Type:** analyzer | **Tag:** outreach

## Description

Analyzes open rates, reply rates, conversion per variant. Kills losers, scales winners. Enforced action output with trigger_skill.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `campaign_data` | string | Yes | Campaign metrics: sends, opens, replies, conversions per variant |
| `min_sample_size` | string | No | Minimum sample before declaring winner |

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

- **Output Type:** outreach_analyzer_output

## Example Usage

```json
{
  "inputs": {
    "campaign_data": "Variant A (Professional tone): 200 sends, 42 percent open rate, 8 percent reply rate, 3 demos booked, 1 closed deal ($8,500). Variant B (Casual tone): 200 sends, 38 percent open rate, 12 percent reply rate, 5 demos booked, 2 closed deals ($14,200). Variant C (Data-driven tone): 150 sends, 51 percent open rate, 6 percent reply rate, 2 demos booked, 0 closed deals. Campaign duration: 14 days. Target: B2B SaaS founders, MENA region.",
    "min_sample_size": "50"
  }
}
```
