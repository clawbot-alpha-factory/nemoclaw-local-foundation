# Lead Qualification Engine

**ID:** `rev-02-lead-qualification-engine` | **Version:** 1.0.0 | **Type:** analyzer | **Tag:** revenue

## Description

Scores leads on ICP fit, intent signals, engagement, timing. Outputs priority tier (hot/warm/cold/disqualify). Feeds into sales closer.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `lead_data` | string | Yes | Lead details to qualify |
| `icp_criteria` | string | No | ICP definition |

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
    "lead_data": "Lead: Tariq Mansour, Operations Director at FreshCart Delivery (85 employees, food delivery SaaS, Dubai). Found us through Google search for 'AI automation for logistics companies'. Visited pricing page twice, downloaded case study. Company growing 15 percent month-over-month. Currently using Zapier for basic automations but hitting limitations. No previous conversation with our team.",
    "icp_criteria": "B2B SaaS, 10-500 employees, MENA or global, needs automation"
  }
}
```
