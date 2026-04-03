# Lead Enricher

**ID:** `k52-lead-enricher` | **Version:** 1.0.0 | **Family:** K52 | **Domain:** K | **Type:** transformer | **Tag:** sales

## Description

Takes raw lead data and enriches with company info, decision-maker identification, and outreach recommendations.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `lead_list` | string | Yes | Raw lead data (names, companies, titles) |
| `enrichment_depth` | string | No | Enrichment level: basic, standard, deep |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | The generated output |
| `result_file` | file_path | Path to the markdown artifact |
| `envelope_file` | file_path | Path to the JSON envelope for skill chaining |

## Steps

- **step_1** — Parse input and prepare analysis context (`local`, `general_short`)
- **step_2** — Generate primary output (`llm`, `moderate`)
- **step_3** — Evaluate output quality (`critic`, `moderate`)
- **step_5** — Validate and write artifact (`local`, `general_short`)

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=N/A, max_improvements=N/A
- **Max Execution:** 120s
- **Max Cost:** $0.3

## Composability

- **Output Type:** sales_transformer_output

## Example Usage

```json
{
  "inputs": {
    "lead_list": "Lead 1: Faris Al-Khatib, TechBridge Solutions, Amman. Lead 2: Elena Voroshilova, ScaleOps Platform, Dubai. Lead 3: Ryan Mitchell, GrowthEngine AI, San Francisco. Lead 4: Nadia Hasan, DataStream Analytics, Riyadh. Lead 5: Tom Eriksen, NordicSaaS, Stockholm.",
    "enrichment_depth": "standard"
  }
}
```
