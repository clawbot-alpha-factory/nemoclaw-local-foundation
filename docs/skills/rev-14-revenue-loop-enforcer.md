# Revenue Loop Enforcer

**ID:** `rev-14-revenue-loop-enforcer` | **Version:** 1.0.0 | **Type:** orchestrator | **Tag:** revenue

## Description

Ensures every opportunity completes full cycle: Demand → Offer → Content → Outreach → Close → Payment → Feedback. Auto-fixes broken loops, re-triggers missing steps.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `active_opportunities` | string | Yes | List of active opportunities with their current stage and status |
| `loop_stages` | string | No | Expected stages |

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
    "active_opportunities": "Opp 1: AI Proposal Generator micro-SaaS. Stage: content (landing page live). Status: 340 visitors, 2.1 percent conversion. Blocked: no outreach sequence created yet. Opp 2: Sales Automation Service for MENA SaaS. Stage: outreach (3 sequences active). Status: 12 replies from 200 sends. Next: schedule demos. Opp 3: Content Automation Package. Stage: close (verbal agreement from GreenLeaf). Status: awaiting contract. Blocked: contract not drafted. Opp 4: Onboarding Automation Pilot. Stage: demand (signals collected). Status: 89 demand signals, not yet validated.",
    "loop_stages": "demand,offer,content,outreach,close,payment,feedback"
  }
}
```
