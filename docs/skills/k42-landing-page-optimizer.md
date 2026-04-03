# Landing Page Optimizer

**ID:** `k42-landing-page-optimizer` | **Version:** 1.0.0 | **Family:** K42 | **Domain:** K | **Type:** generator | **Tag:** marketing

## Description

Analyzes landing page copy and structure, produces optimized versions with improved headlines, CTAs, and social proof.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `page_content` | string | Yes | Current landing page content and structure |
| `target_action` | string | No | Desired conversion action |

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
    "page_content": "Hero: 'Automate Your Business Operations with AI'. Subheadline: 'Save 25+ hours per week'. CTA button: 'Get Started'. Features section: 3 feature cards with icons. Testimonial: one client quote. Pricing: single plan at $149/mo. Footer with standard links. Current conversion rate: 1.8 percent from 2,400 monthly visitors. Average time on page: 42 seconds. Bounce rate: 71 percent.",
    "target_action": "sign_up"
  }
}
```
