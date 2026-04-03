# Affiliate Program Engine

**ID:** `scl-01-affiliate-program-engine` | **Version:** 1.0.0 | **Type:** generator | **Tag:** scale

## Description

Designs affiliate program: commission structure, tracking, partner recruitment outreach, performance dashboard spec.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `product_context` | string | Yes | Product/service details and target partners |
| `commission_model` | string | No | Commission model preference |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | The generated output |
| `result_file` | file_path | Path to the markdown artifact |
| `envelope_file` | file_path | Path to JSON envelope for skill chaining |

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=N/A, max_improvements=N/A
- **Max Execution:** 120s
- **Max Cost:** $0.35

## Composability

- **Output Type:** scale_generator_output

## Example Usage

```json
{
  "inputs": {
    "product_context": "NemoClaw AI Automation Platform at $149/month. Target partners: SaaS consultants, business coaches, digital agency owners, and AI newsletter creators who serve B2B founders. Current customer base: 85 paying customers. Average LTV: $2,400. Product is self-serve with onboarding automation.",
    "commission_model": "recurring_20pct"
  }
}
```
