# Global State Engine

**ID:** `rev-20-global-state-engine` | **Version:** 1.0.0 | **Type:** tracker | **Tag:** revenue

## Description

Reads and updates the global state layer. Stores leads, deals, content performance, experiments, channel ROI. Makes the system stateful across all runs.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `state_update` | string | Yes | What to update: new lead, deal stage change, performance metric |
| `collection` | string | No | Collection: leads, deals, content, experiments, channels, learnings |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string |  |
| `result_file` | file_path |  |
| `envelope_file` | file_path |  |

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=N/A, max_improvements=N/A
- **Max Execution:** 90s
- **Max Cost:** $0.2

## Composability

- **Output Type:** revenue_tracker_output

## Example Usage

```json
{
  "inputs": {
    "state_update": "New lead from inbound: Karim Benchekroun, CTO at Payflow (32 employees, fintech SaaS, Casablanca). Source: downloaded whitepaper on AI automation ROI. Company details: processing 50K transactions/month, looking to automate fraud detection alerts and customer communication workflows. Lead score: pending evaluation.",
    "collection": "leads"
  }
}
```
