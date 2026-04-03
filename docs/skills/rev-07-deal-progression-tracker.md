# Deal Progression Tracker

**ID:** `rev-07-deal-progression-tracker` | **Version:** 1.0.0 | **Type:** tracker | **Tag:** revenue

## Description

Maintains state per deal: last touch, next action, days in stage, risk score. Triggers agent actions on stale deals automatically.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `deals_data` | string | Yes | Active deals with stage, last activity, value |
| `stale_threshold_days` | string | No | Days before a deal is flagged stale |

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
- **Max Execution:** 90s
- **Max Cost:** $0.2

## Composability

- **Output Type:** revenue_tracker_output

## Example Usage

```json
{
  "inputs": {
    "deals_data": "Deal 1: Apex Digital, Discovery, $8,500, last activity 2 days ago, contact: Sarah (VP Ops). Deal 2: CloudFirst, Proposal Sent, $15,000, last activity 5 days ago, contact: Mark (CTO). Deal 3: NovaTech MENA, Negotiation, $22,000, last activity 1 day ago, contact: Layla (CEO). Deal 4: SwiftOps, Discovery, $6,000, last activity 9 days ago, contact: John (Ops Manager). Deal 5: Horizon Digital, Demo Scheduled, $11,000, last activity 3 days ago, contact: Sarah Al-Rashid (COO). Deal 6: GreenLeaf, Verbal Agreement, $18,500, last activity 4 days ago, awaiting contract signing.",
    "stale_threshold_days": "3"
  }
}
```
