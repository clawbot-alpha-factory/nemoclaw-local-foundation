# Thumbnail Generator

**ID:** `cnt-13-thumbnail-generator` | **Version:** 1.0.0 | **Type:** generator | **Tag:** content-factory

## Description

Generates scroll-stopping thumbnails for video content. Uses LLM for design concept, calls image generation bridge, and validates quality via critic loop.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `title` | string | Yes | Video or post title for the thumbnail |
| `agent_id` | string | Yes | Agent character to feature |
| `platform` | string | Yes | Target platform |
| `subtitle` | string | No | Optional subtitle or tagline |

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
    "title": "How AI Agents Close Deals",
    "agent_id": "hassan",
    "platform": "tiktok"
  }
}
```
