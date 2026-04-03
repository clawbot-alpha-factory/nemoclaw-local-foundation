# Email Campaign Designer

**ID:** `k44-email-campaign-designer` | **Version:** 1.0.0 | **Family:** K44 | **Domain:** K | **Type:** generator | **Tag:** marketing

## Description

Creates multi-email campaign sequences with subject lines, body copy, send timing, and segmentation strategy.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `campaign_brief` | string | Yes | Campaign goal, audience, and key messages |
| `num_emails` | string | No | Number of emails in sequence |

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
    "campaign_brief": "Nurture sequence for SaaS founders who downloaded our AI Automation ROI Calculator. Goal: convert free tool users into demo bookings within 14 days. Key messages: quantify time savings, share case studies, offer personalized automation audit. Audience: technical and non-technical founders at companies with 10-100 employees.",
    "num_emails": "5"
  }
}
```
