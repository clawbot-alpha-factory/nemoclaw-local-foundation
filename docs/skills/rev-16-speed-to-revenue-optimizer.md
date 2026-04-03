# Speed-to-Revenue Optimizer

**ID:** `rev-16-speed-to-revenue-optimizer` | **Version:** 1.0.0 | **Type:** orchestrator | **Tag:** revenue

## Description

Prioritizes actions that generate fastest cash. Deprioritizes long-term branding when cash is needed. Aligns system with real business constraint: cash flow.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `current_state` | string | Yes | Cash position, pipeline, active campaigns, conversion rates |
| `urgency` | string | No | Cash urgency: low, moderate, critical |

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
    "current_state": "Cash position: $12,400 in account, monthly burn $8,200. Pipeline: $94,000 across 8 deals (2 in negotiation worth $37,000). Active campaigns: 3 outreach sequences, 1 content funnel. Conversion rates: lead-to-close 6.2 percent overall, fastest close cycle was 7 days (referral). Channels with revenue: LinkedIn outreach ($8,500), content inbound ($14,000), referrals ($6,000). Runway: approximately 6 weeks at current burn without new revenue.",
    "urgency": "moderate"
  }
}
```
