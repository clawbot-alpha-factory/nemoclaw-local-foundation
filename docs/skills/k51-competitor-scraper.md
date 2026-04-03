# Competitor Scraper

**ID:** `k51-competitor-scraper` | **Version:** 1.0.0 | **Family:** K51 | **Domain:** K | **Type:** analyzer | **Tag:** research

## Description

Analyzes competitor presence: pricing, positioning, features, messaging, and produces comparison matrix.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `competitors` | string | Yes | List of competitors to analyze |
| `focus_areas` | string | No | Analysis dimensions |

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
- **Max Cost:** $0.3

## Composability

- **Output Type:** research_analyzer_output

## Example Usage

```json
{
  "inputs": {
    "competitors": "Clay.com (data enrichment and outreach), Apollo.io (sales intelligence platform), Instantly.ai (cold email automation), Lemlist (multi-channel outreach), Salesforge (AI sales engagement)",
    "focus_areas": "pricing,features,positioning"
  }
}
```
