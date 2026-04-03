# Growth Experiment Designer

**ID:** `scl-06-growth-experiment-designer` | **Version:** 1.0.0 | **Type:** generator | **Tag:** scale

## Description

Hypothesis → test design → success metrics → timeline → analysis template. 10 experiments per run.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `growth_goal` | string | Yes | What growth metric to improve |
| `constraints` | string | No | Resource constraints |

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
    "growth_goal": "Increase qualified demo requests from 85 per month to 150 per month within 60 days while maintaining current cost per acquisition of under $120. Current channels: LinkedIn outreach (38 percent of leads), content/SEO (30 percent), Google Ads (20 percent), referrals (12 percent).",
    "constraints": "budget_limited"
  }
}
```
