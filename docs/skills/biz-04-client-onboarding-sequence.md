# Client Onboarding Sequence

**ID:** `biz-04-client-onboarding-sequence` | **Version:** 1.0.0 | **Type:** orchestrator | **Tag:** business

## Description

Payment confirmed → welcome email (Resend) → setup checklist → first deliverable schedule → 7-day check-in. Bridge-connected.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `client_info` | string | Yes | New client details: name, service purchased, start date |
| `service_type` | string | No | Service purchased |

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

- **Output Type:** business_orchestrator_output

## Example Usage

```json
{
  "inputs": {
    "client_info": "New client: Horizon Digital Solutions, contact Sarah Al-Rashid (COO). Purchased AI Content Automation package. Start date: 2026-04-07. Timezone: GMT+3. Preferred communication: Slack and email.",
    "service_type": "ai_automation"
  }
}
```
