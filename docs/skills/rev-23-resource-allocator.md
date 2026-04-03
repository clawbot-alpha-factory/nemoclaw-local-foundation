# Resource Constraint Allocator

**ID:** `rev-23-resource-allocator` | **Version:** 1.0.0 | **Type:** orchestrator | **Tag:** revenue

## Description

Hard enforcement of daily outreach caps, per-channel budget, risk thresholds. Prevents spam, domain burn, budget waste.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `current_usage` | string | Yes | Current usage: emails sent, budget spent, outreach volume per channel |
| `limits` | string | No | Hard limits |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string |  |
| `envelope_file` | file_path |  |

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=N/A, max_improvements=N/A
- **Max Execution:** 180s
- **Max Cost:** $0.5

## Example Usage

```json
{
  "inputs": {
    "current_usage": "Emails sent today: 34 of 100 limit. Budget spent today: $8.40 of $20 limit. Outreach messages today: 22 of 50 limit. LLM calls: 89 (Anthropic 52, OpenAI 28, Google 9). Active sequences: 3 email campaigns, 2 LinkedIn sequences. Queued tasks: 8 skill executions pending. Agent utilization: revenue-closer at 78 percent, content-ops at 45 percent, outreach-agent at 91 percent.",
    "limits": "emails:100,budget:20,outreach:50"
  }
}
```
