# Agentic Service Packager

**ID:** `rev-08-agentic-service-packager` | **Version:** 1.0.0 | **Type:** generator | **Tag:** revenue

## Description

Packages NemoClaw capabilities as sellable services. Generates pricing, scope, deliverables, timeline for client proposals.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `capability_description` | string | Yes | What the system can do for this client |
| `client_industry` | string | No | Client's industry |

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
- **Max Execution:** 120s
- **Max Cost:** $0.35

## Composability

- **Output Type:** revenue_generator_output

## Example Usage

```json
{
  "inputs": {
    "capability_description": "For this client we can deploy: AI-powered lead scoring that integrates with their HubSpot CRM, automated multi-channel outreach sequences (email + LinkedIn), real-time sales analytics dashboard, AI proposal generator trained on their service catalog, and automated follow-up engine that triggers based on prospect engagement signals.",
    "client_industry": "B2B SaaS"
  }
}
```
