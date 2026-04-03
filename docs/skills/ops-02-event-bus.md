# Event Bus Controller

**ID:** `ops-02-event-bus` | **Version:** 1.0.0 | **Type:** executor | **Tag:** operations

## Description

Routes real-time events: email opens, payments, scraper signals, deal advances. Feeds orchestrator + priority engine.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `event_data` | string | Yes | Event details: type, source, payload |

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
- **Max Execution:** 90s
- **Max Cost:** $0.25

## Example Usage

```json
{
  "inputs": {
    "event_data": "Event type: deal_stage_change. Source: rev-07-deal-progression-tracker. Payload: deal_id=DEAL-2026-0089, client=NovaTech MENA, previous_stage=proposal, new_stage=negotiation, deal_value=22000, agent=revenue-closer-agent, timestamp=2026-04-01T14:32:00Z."
  }
}
```
