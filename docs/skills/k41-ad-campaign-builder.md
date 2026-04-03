# Ad Campaign Builder

**ID:** `k41-ad-campaign-builder` | **Version:** 1.0.0 | **Family:** K41 | **Domain:** K | **Type:** generator | **Tag:** marketing

## Description

Generates complete ad campaign plans with targeting, creative briefs, budget allocation, and A/B test variants.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `campaign_goal` | string | Yes | Campaign objective and target outcome |
| `budget` | string | Yes | Campaign budget and timeline |
| `platform` | string | No | Advertising platform |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | The generated output |
| `result_file` | file_path | Path to the markdown artifact |
| `envelope_file` | file_path | Path to the JSON envelope for skill chaining |

## Steps

- **step_1** — Parse input and prepare analysis context (`local`, `general_short`)
- **step_2** — Generate primary output (`llm`, `premium`)
- **step_3** — Evaluate output quality (`critic`, `moderate`)
- **step_5** — Validate and write artifact (`local`, `general_short`)

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=N/A, max_improvements=N/A
- **Max Execution:** 120s
- **Max Cost:** $0.35

## Composability

- **Output Type:** marketing_generator_output

## Example Usage

```json
{
  "inputs": {
    "campaign_goal": "Generate 50 qualified demo requests for our AI automation platform targeting B2B SaaS founders and operations leaders in companies with 20-200 employees, focusing on the MENA region and North America",
    "budget": "$3,000 over 30 days, with $100/day spend cap",
    "platform": "google_ads"
  }
}
```
