# Revenue Orchestrator

**ID:** `rev-06-revenue-orchestrator` | **Version:** 1.0.0 | **Type:** orchestrator | **Tag:** revenue

## Description

Meta-skill: decides what to do next based on pipeline state. No leads → trigger content. Low conversion → trigger offer optimizer. Stale deals → trigger follow-up. Consumes all analyzer outputs. Confidence gating: auto-execute if confidence > 0.8 and demand_volume high.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `pipeline_state` | string | Yes | Current pipeline: leads, deals, conversion rates, revenue, bottlenecks |
| `available_budget` | string | No | Available daily budget in USD |

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
- **Max Execution:** 180s
- **Max Cost:** $0.5

## Composability

- **Output Type:** revenue_orchestrator_output

## Example Usage

```json
{
  "inputs": {
    "pipeline_state": "Active leads: 28 (12 qualified). Active deals: 8 worth $94,000. Conversion rates: lead-to-qualified 43 percent, qualified-to-demo 62 percent, demo-to-close 28 percent. Revenue this month: $34,500 closed. Monthly target: $50,000. Pipeline bottleneck: 5 deals stalled in proposal stage for 7+ days. Top channel: LinkedIn outreach (38 percent of qualified leads). Content pipeline: 4 posts scheduled, 2 emails drafted. Budget spent: $8.40 of $20 daily.",
    "available_budget": "20.0"
  }
}
```
