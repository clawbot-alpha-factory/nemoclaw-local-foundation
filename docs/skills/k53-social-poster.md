# Social Poster

**ID:** `k53-social-poster` | **Version:** 1.0.0 | **Family:** K53 | **Domain:** K | **Type:** generator | **Tag:** marketing

## Description

Generates platform-specific social media posts with hashtags, CTAs, and optimal posting recommendations.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `topic` | string | Yes | Post topic or key message |
| `platform` | string | Yes | Target platform: linkedin, twitter, instagram |

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

- **Output Type:** marketing_generator_output

## Example Usage

```json
{
  "inputs": {
    "topic": "The hidden cost of manual processes in B2B SaaS: why companies with 20-100 employees lose an average of $180K per year to inefficient workflows and how AI automation closes the gap",
    "platform": "linkedin"
  }
}
```
