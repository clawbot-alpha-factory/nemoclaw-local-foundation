# SEO Keyword Researcher

**ID:** `k55-seo-keyword-researcher` | **Version:** 1.0.0 | **Family:** K55 | **Domain:** K | **Type:** analyzer | **Tag:** marketing

## Description

SEO keyword research, SERP analysis, and content gap identification. Produces prioritized keyword clusters with search volume estimates, difficulty scores, and content strategy recommendations.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `niche` | string | Yes | Target niche or industry for keyword research |
| `competitor_urls` | string | No | Comma-separated competitor URLs for competitive analysis |
| `target_audience` | string | No | Target audience persona for intent matching |
| `content_goals` | string | No | Content marketing goals (traffic, leads, authority, etc.) |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | The generated output |
| `result_file` | file_path | Path to the markdown artifact |
| `envelope_file` | file_path | Path to the JSON envelope for skill chaining |

## Steps

- **step_1** — Parse Niche (`local`, `general_short`)
- **step_2** — Research Keywords (`llm`, `moderate`)
- **step_3** — Analyze Competition (`llm`, `moderate`)
- **step_4** — Generate Strategy (`llm`, `moderate`)
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
    "niche": "AI automation for B2B SaaS companies in the MENA region",
    "target_audience": "CTOs and VPs of Marketing at 20-200 employee companies"
  }
}
```
