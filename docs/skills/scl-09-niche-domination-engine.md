# Niche Domination Engine

**ID:** `scl-09-niche-domination-engine` | **Version:** 1.0.0 | **Type:** orchestrator | **Tag:** scale

## Description

Picks niche from demand signals. Floods content, outreach, comments, partnerships simultaneously. Builds authority fast. Strategy: compress 6 months of presence into 2 weeks.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `niche_definition` | string | Yes | Target niche with demand data and competitive landscape |
| `timeline` | string | No | Domination timeline |

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

- **Output Type:** scale_orchestrator_output

## Example Usage

```json
{
  "inputs": {
    "niche_definition": "Target niche: AI-powered sales automation for B2B SaaS companies with 20-100 employees in MENA region. Demand data: 156 high-intent signals in last 30 days, growing 22 percent week-over-week. Competitive landscape: no dedicated player in MENA, global competitors (Apollo, Clay, Instantly) lack Arabic language support and MENA-specific integrations. Current market share estimate: under 2 percent. Unique advantages: bilingual capability, MENA payment integrations, local timezone support.",
    "timeline": "14_days"
  }
}
```
