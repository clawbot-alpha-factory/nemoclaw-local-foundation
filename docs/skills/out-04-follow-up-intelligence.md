# Follow-Up Intelligence

**ID:** `out-04-follow-up-intelligence` | **Version:** 1.0.0 | **Type:** analyzer | **Tag:** outreach

## Description

Analyzes reply sentiment, determines next best action (schedule call, send case study, handle objection, disengage). Enforced action output.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `conversation_history` | string | Yes | Full email/message thread with prospect |
| `deal_stage` | string | No | Current deal stage |

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
    "conversation_history": "Day 1 - Our email: Mentioned their LinkedIn post about onboarding challenges, offered 15-min walkthrough. Day 3 - Their reply: 'Sounds interesting, but we are in the middle of a product launch. Can you send more details?' Day 4 - Our reply: Sent one-pager with case study link and ROI calculator. Day 10 - No response. Day 14 - Our follow-up: Asked if they had a chance to review the materials. Day 16 - Their reply: 'Reviewed it. The numbers look promising. What does implementation look like?' Day 17 - Our reply: Detailed implementation timeline and pricing. Day 24 - No response since.",
    "deal_stage": "outreach"
  }
}
```
