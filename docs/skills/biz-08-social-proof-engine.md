# Social Proof Engine

**ID:** `biz-08-social-proof-engine` | **Version:** 1.0.0 | **Type:** generator | **Tag:** business

## Description

Auto-generates case studies, testimonials from real outputs, before/after results. Injects into landing pages, outreach, proposals. Conversion multiplier across entire system.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `client_results` | string | Yes | Raw client outcomes: metrics, feedback, deliverables completed |
| `output_formats` | string | No | Proof formats to generate |

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

- **Output Type:** business_generator_output

## Example Usage

```json
{
  "inputs": {
    "client_results": "Client: Meridian SaaS. Engagement: 4-month AI automation project. Results: reduced manual data entry by 78 percent, onboarding time cut from 14 days to 3 days, customer support ticket volume decreased 45 percent, annual cost savings estimated at $180,000. Client quote from CEO: 'Transformed our operations beyond expectations.' NPS improvement from 42 to 71.",
    "output_formats": "case_study,testimonial,before_after,quote_card"
  }
}
```
