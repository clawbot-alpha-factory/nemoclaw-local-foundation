# Lead Source Engine

**ID:** `rev-10-lead-source-engine` | **Version:** 1.0.0 | **Type:** orchestrator | **Tag:** revenue

## Description

Pulls leads from Apollo, LinkedIn, website inbound, referrals. Feeds directly into rev-02 Lead Qualification Engine. Closes top-of-funnel gap.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `target_icp` | string | Yes | Target ICP for lead sourcing |
| `sources` | string | No | Lead sources to activate |

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
    "target_icp": "B2B SaaS companies with 20-200 employees in MENA and North America, preferably in growth stage (Series A/B), with pain points around manual sales processes, customer onboarding, or content operations. Decision makers: CEO, CTO, VP of Operations, Head of Growth.",
    "sources": "apollo,linkedin,inbound,referral"
  }
}
```
