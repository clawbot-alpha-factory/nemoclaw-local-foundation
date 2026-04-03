# Content Calendar Builder

**ID:** `cnt-06-content-calendar-builder` | **Version:** 1.0.0 | **Type:** generator | **Tag:** content

## Description

30-day content plan across all channels. Maps content to funnel stages. Balances education/entertainment/conversion.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `business_context` | string | Yes | Business, audience, goals for the month |
| `channels` | string | No | Active channels |

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

- **Output Type:** content_generator_output

## Example Usage

```json
{
  "inputs": {
    "business_context": "NemoClaw AI automation agency targeting B2B SaaS founders with 10-200 employees in MENA and global markets. Goal: establish thought leadership in AI-driven business operations and generate 30 qualified inbound leads per month. Key themes: AI automation ROI, operational efficiency, founder productivity.",
    "channels": "linkedin,instagram,tiktok,youtube,email"
  }
}
```
