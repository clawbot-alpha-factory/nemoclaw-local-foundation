# Newsletter Composer

**ID:** `k49-newsletter-composer` | **Version:** 1.0.0 | **Family:** K49 | **Domain:** K | **Type:** generator | **Tag:** content

## Description

Composes engaging newsletters with curated sections, headlines, summaries, and CTAs.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `newsletter_brief` | string | Yes | Key topics, updates, and announcements to include |
| `audience` | string | No | Newsletter audience |

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
- **Max Cost:** $0.35

## Composability

- **Output Type:** content_generator_output

## Example Usage

```json
{
  "inputs": {
    "newsletter_brief": "This week: launched new AI proposal generator feature (3x faster proposals), published case study on Pinnacle Logistics (97 percent faster quotes), upcoming webinar on AI-driven sales pipelines next Thursday. Industry news: OpenAI released new function calling improvements relevant to our automation stack. Tip of the week: how to use our content repurposer to generate a full week of social posts from one blog article.",
    "audience": "B2B SaaS professionals"
  }
}
```
