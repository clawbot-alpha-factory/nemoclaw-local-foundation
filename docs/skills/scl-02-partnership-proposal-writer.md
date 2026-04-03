# Partnership Proposal Writer

**ID:** `scl-02-partnership-proposal-writer` | **Version:** 1.0.0 | **Type:** generator | **Tag:** scale

## Description

Co-marketing, integration, white-label proposals. Personalized per partner.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `partner_info` | string | Yes | Potential partner details and synergies |
| `partnership_type` | string | No | Type: co_marketing, integration, white_label, referral |

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

- **Output Type:** scale_generator_output

## Example Usage

```json
{
  "inputs": {
    "partner_info": "Potential partner: HubSpot Solutions Partner 'GrowthStack Agency' (35 employees, Dubai). They serve 120+ SMB clients in MENA with HubSpot implementation and marketing automation. Synergy: our AI automation complements their HubSpot services, we can build custom AI workflows on top of HubSpot for their clients. Their clients frequently ask about AI capabilities they cannot deliver in-house.",
    "partnership_type": "co_marketing"
  }
}
```
