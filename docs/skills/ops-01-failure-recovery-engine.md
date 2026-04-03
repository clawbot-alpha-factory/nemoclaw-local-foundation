# Failure Recovery Engine

**ID:** `ops-01-failure-recovery-engine` | **Version:** 1.0.0 | **Type:** executor | **Tag:** operations

## Description

Handles skill/bridge failures. Retry (2x) → fallback skill → escalate to different agent → log pattern. Prevents silent failures.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `failure_context` | string | Yes | What failed: skill_id, error, agent, inputs |
| `severity` | string | No | Severity: low, medium, high, critical |

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
- **Max Cost:** $0.25

## Composability

- **Output Type:** operations_executor_output

## Example Usage

```json
{
  "inputs": {
    "failure_context": "Skill k44-email-campaign-designer failed at step 3 (Generate Email Sequence). Error: LLM routing returned empty response after 3 retries. Agent: content-ops-agent. Input was a campaign brief for SaaS onboarding nurture sequence. Provider: anthropic. Budget remaining: $4.20.",
    "severity": "medium"
  }
}
```
