# SEO Technical Auditor

**ID:** `k56-seo-technical-auditor` | **Version:** 1.0.0 | **Family:** K56 | **Domain:** K | **Type:** analyzer | **Tag:** marketing

## Description

Technical SEO audit — site structure, page speed, meta tags, schema markup recommendations. Produces actionable audit reports with prioritized fixes.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `website_url` | string | Yes | Website URL to audit |
| `focus_areas` | string | No | Comma-separated focus areas (meta tags, page speed, mobile, schema markup, etc.) |
| `depth` | string | No | Audit depth: quick, standard, deep |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | The generated output |
| `result_file` | file_path | Path to the markdown artifact |
| `envelope_file` | file_path | Path to the JSON envelope for skill chaining |

## Steps

- **step_1** — Parse Request (`local`, `general_short`)
- **step_2** — Audit Structure (`llm`, `moderate`)
- **step_3** — Audit Performance (`llm`, `moderate`)
- **step_4** — Generate Recommendations (`llm`, `moderate`)
- **step_5** — Quality Review (`critic`, `moderate`)
- **step_6** — Write Artifact (`local`, `general_short`)

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=N/A, max_improvements=N/A
- **Max Execution:** 120s
- **Max Cost:** $0.3

## Composability

- **Output Type:** marketing_analyzer_output

## Example Usage

```json
{
  "inputs": {
    "website_url": "https://nemoclaw.ai",
    "focus_areas": "meta tags, page speed, mobile optimization, schema markup"
  }
}
```
