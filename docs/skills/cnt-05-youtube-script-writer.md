# YouTube Script Writer

**ID:** `cnt-05-youtube-script-writer` | **Version:** 1.0.0 | **Type:** generator | **Tag:** content

## Description

Full script: hook → intro → 3-5 sections → CTA → end screen. SEO-optimized title + description + tags.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `video_topic` | string | Yes | Video topic and target keyword |
| `video_length` | string | No | Target video length |

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
    "video_topic": "Building an AI-powered sales pipeline from scratch: step-by-step guide for B2B founders who want to automate lead generation and outreach",
    "video_length": "10min"
  }
}
```
