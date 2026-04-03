# Client Health Monitor

**ID:** `biz-05-client-health-monitor` | **Version:** 1.0.0 | **Type:** analyzer | **Tag:** business

## Description

Scores client satisfaction 0-100. Tracks deliverable completion, response times, sentiment. Triggers proactive outreach on decline.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `client_data` | string | Yes | Client engagement data: deliverables, communications, feedback |
| `threshold` | string | No | Health score threshold for intervention |

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

- **Output Type:** business_analyzer_output

## Example Usage

```json
{
  "inputs": {
    "client_data": "Client: DataFlow Analytics. Contract started 2026-01-15. Deliverables: 4 of 6 milestones completed on time, milestone 5 delayed by 8 days. Last communication: 12 days ago (unusual gap). NPS survey response: 6/10 with comment about slow response times. Support tickets: 3 open, avg resolution 4.2 days. Monthly retainer: $4,500 paid on time.",
    "threshold": "70"
  }
}
```
