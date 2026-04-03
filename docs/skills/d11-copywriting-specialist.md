# Copywriting Specialist

**ID:** `d11-copywriting-specialist` | **Version:** 1.0.0 | **Family:** F11 | **Domain:** D | **Type:** executor | **Tag:** customer-facing

## Description

Takes a copy brief, target audience, format, brand voice, and reference material. Produces polished, conversion-oriented marketing copy with single CTA enforcement, persuasion mechanics, format-specific structure, and anti-hallucination controls. Supports landing pages, emails, ads, product descriptions, sales pages, and general copy.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `copy_brief` | string | Yes | What to write: product/service, key message, goal, context |
| `target_audience` | string | Yes | Who reads this: role, pain points, decision stage, objections |
| `copy_format` | string | Yes | landing_page, email, ad_copy, product_description, sales_page, general |
| `brand_voice` | string | No | Tone, style, vocabulary constraints, personality |
| `reference_material` | string | No | Existing copy, product specs, testimonials, data points to incorporate |
| `copy_length` | string | No | short (under 300 words), standard (300-800), long (800+) |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | The polished marketing copy in markdown |
| `result_file` | file_path | Path to the markdown artifact |
| `envelope_file` | file_path | Path to the JSON envelope |

## Steps

- **step_1** — Parse copy brief and build generation plan (`local`, `general_short`)
- **step_2** — Generate polished marketing copy (`llm`, `premium`)
- **step_3** — Evaluate copy quality and conversion readiness (`critic`, `moderate`)
- **step_4** — Strengthen copy based on critic feedback (`llm`, `premium`)
- **step_5** — Validate final copy and write artifact (`local`, `general_short`)

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=10, max_improvements=5
- **Max Execution:** 300s
- **Max Cost:** $0.2

## Declarative Guarantees

- Single primary CTA per piece — no competing asks
- Headlines contain a benefit, hook, or curiosity element — not labels
- At least 2 persuasion techniques identifiable in standard/long copy
- Benefits framed as outcomes, not just features listed
- No fabricated testimonials, customer quotes, or statistics
- Tone consistent with brand voice throughout
- Format-specific structure followed
- All claims traceable to input brief or reference material
- Placeholder markers used where social proof data is missing
- Banned filler phrases avoided

## Composability

- **Output Type:** marketing_copy
- **Can Feed Into:** i35-tone-calibrator, d11-video-script-writer
- **Accepts Input From:** f09-product-req-writer, e12-market-research-analyst, f09-pricing-strategist

## Example Usage

```json
{
  "skill_id": "d11-copywriting-specialist",
  "inputs": {
    "copy_brief": "Write a landing page for ClawBot AI, an intelligent automation platform that reduces manual data entry by 85 percent. Include a clear call to action: Start Your Free Trial.",
    "target_audience": "VP of Customer Success at B2B SaaS companies with 50-200 employees who are frustrated with manual processes",
    "copy_format": "landing_page",
    "brand_voice": "Professional but warm, direct, benefit-focused",
    "reference_material": "ClawBot AI beta: 85 percent reduction in manual entry, 500 plus companies, 3x faster onboarding, 49 dollars per user per month",
    "copy_length": "standard"
  }
}
```
