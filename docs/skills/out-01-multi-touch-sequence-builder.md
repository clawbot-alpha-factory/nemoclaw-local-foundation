# Multi-Touch Sequence Builder

**ID:** `out-01-multi-touch-sequence-builder` | **Version:** 1.0.0 | **Type:** generator | **Tag:** outreach

## Description

Full 7-day sequence: Day 1 email → Day 2 LinkedIn view → Day 3 connect → Day 5 follow-up → Day 7 objection handler → Day 10 break-up email.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `prospect_profile` | string | Yes | Target prospect details and pain points |
| `value_prop` | string | Yes | Core value proposition |

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

- **Output Type:** outreach_generator_output

## Example Usage

```json
{
  "inputs": {
    "prospect_profile": "Ahmad Khalil, CTO at CloudServe (45 employees, B2B SaaS in Amman). Pain points: manual onboarding taking 3 weeks, high churn in first 60 days, engineering team spending 30 percent of time on support tickets instead of product development. Recently posted on LinkedIn about needing better automation tooling.",
    "value_prop": "AI-powered customer onboarding automation that reduces time-to-value by 60 percent and cuts support ticket volume by 45 percent within 90 days of deployment"
  }
}
```
