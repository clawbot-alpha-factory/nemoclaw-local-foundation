# Reality Check Engine

**ID:** `int-04-reality-check-engine` | **Version:** 1.0.0 | **Type:** analyzer | **Tag:** intelligence

## Description

Challenges assumptions. Cross-checks demand vs actual conversions. Prevents false positives and vanity metric traps. Can output trigger_skill: null to STOP revenue cycle.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `opportunity_data` | string | Yes | Opportunity details with demand signals, engagement data, conversion data |
| `historical_results` | string | No | Past similar opportunities and their outcomes |

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

- **Output Type:** intelligence_analyzer_output

## Example Usage

```json
{
  "inputs": {
    "opportunity_data": "Opportunity: AI Proposal Generator SaaS. Demand signals: 156 comments requesting this feature across 3 platforms. Target ICP: B2B SaaS founders with 5-50 employees. Proposed pricing: $149/month. Estimated build time: 3 weeks. Engagement rate on related content: 4.7 percent. Initial landing page conversion: 2.1 percent from 340 visitors.",
    "historical_results": "Previous AI writing tool launch: 2.8 percent landing page conversion, 12 percent trial-to-paid, $4,200 MRR after 60 days. Previous automation service: 18 percent close rate on qualified leads, avg deal $3,500."
  }
}
```
