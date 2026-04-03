# TikTok Content Engine

**ID:** `cnt-03-tiktok-content-engine` | **Version:** 1.0.0 | **Type:** generator | **Tag:** content

## Description

Full script + text overlay + sound suggestion + CTA. Batch mode: 30 pieces per run. Executor, not planner.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `niche` | string | Yes | Content niche |
| `batch_size` | string | No | Number of scripts to generate |

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
    "niche": "AI automation for small business owners and solopreneurs who want to scale without hiring, focusing on practical tools and real results",
    "batch_size": "5"
  }
}
```
