# Tone Calibrator

**ID:** `i35-tone-calibrator` | **Version:** 1.0.0 | **Family:** F35 | **Domain:** I | **Type:** transformer | **Tag:** customer-facing

## Description

Takes text and a target tone profile, rewrites the text to match the specified tone while preserving all meaning, facts, and structure. Default humanization layer for customer-facing outputs.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `input_text` | string | Yes | The text to be tone-calibrated |
| `target_tone` | string | Yes | Target tone profile |
| `preserve_structure` | boolean | No | Whether to preserve paragraph, bullet, and heading structure |
| `intensity` | string | No | How aggressively to rewrite: subtle, moderate, aggressive |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | The tone-calibrated text |
| `result_file` | file_path | Path to the markdown artifact |
| `envelope_file` | file_path | Path to the JSON envelope for skill chaining |

## Steps

- **step_1** — Parse input and detect current tone characteristics (`local`, `general_short`)
- **step_2** — Rewrite text to match target tone profile (`llm`, `premium`)
- **step_3** — Evaluate tone match and preservation quality (`critic`, `moderate`)
- **step_4** — Improve rewrite based on critic feedback (`llm`, `premium`)
- **step_5** — Validate contracts and write artifact (`local`, `general_short`)

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=10, max_improvements=5
- **Max Execution:** 90s
- **Max Cost:** $0.1

## Declarative Guarantees

- Output preserves all factual content including numbers, names, dates, and claims
- Output matches the requested tone profile
- Output does not introduce new claims not in the original
- Output length is within intensity-appropriate range of input length

## Composability

- **Output Type:** tone_calibrated_text
- **Can Feed Into:** i35-ai-detection-bypasser, i37-cold-email-seq-writer, i38-linkedin-post-writer, d11-copywriting-specialist
- **Accepts Input From:** c08-research-brief, b05-feature-impl-writer, d11-copywriting-specialist, f18-sales-pitch-crafter

## Example Usage

```json
{
  "skill_id": "i35-tone-calibrator",
  "inputs": {
    "input_text": "The quarterly results exceeded expectations with a 23 percent increase in revenue. Our team worked really hard and we think next quarter will be even more awesome.",
    "target_tone": "professional",
    "intensity": "moderate"
  }
}
```
