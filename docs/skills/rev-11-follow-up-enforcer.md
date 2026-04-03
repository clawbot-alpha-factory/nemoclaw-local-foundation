# Follow-Up Enforcer

**ID:** `rev-11-follow-up-enforcer` | **Version:** 1.0.0 | **Type:** executor | **Tag:** revenue

## Description

Auto follow-up on stale deals. If no reply in X days → auto follow-up. If deal idle → escalate. If near close → push urgency sequence.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `deal_context` | string | Yes | Deal details: stage, last contact, conversation history |
| `days_since_contact` | string | No | Days since last contact |

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
- **Max Cost:** $0.25

## Composability

- **Output Type:** revenue_executor_output

## Example Usage

```json
{
  "inputs": {
    "deal_context": "Deal: CloudFirst Solutions, $15,000 proposal for AI content automation. Stage: Proposal Sent. Last contact: 5 days ago (sent detailed proposal with pricing breakdown and implementation timeline). Previous interactions: discovery call went well, CTO Mark expressed strong interest but mentioned needing board approval. Competitor mentioned: they are also evaluating Jasper AI enterprise plan.",
    "days_since_contact": "5"
  }
}
```
