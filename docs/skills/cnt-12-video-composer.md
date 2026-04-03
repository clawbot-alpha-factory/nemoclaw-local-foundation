# Video Composer

**ID:** `cnt-12-video-composer` | **Version:** 1.0.0 | **Type:** executor | **Tag:** content-factory

## Description

Composes short-form videos from script text. Generates image prompts from script visual cues, calls the video composer tool, and runs quality checks via critic loop.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `script_text` | string | Yes | Full video script with scenes and visual cues |
| `agent_id` | string | Yes | Agent character featured in the video |
| `platform` | string | Yes | Target platform (tiktok, instagram_reel, youtube_short) |
| `visual_style` | string | No | Visual style for the video |

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
- **Max Execution:** 90s
- **Max Cost:** $0.25

## Composability

- **Output Type:** content_executor_output

## Example Usage

```json
{
  "inputs": {
    "script_text": "Hook: Did you know AI agents can close deals while you sleep? Scene 1: Show a pipeline dashboard with deals moving. Scene 2: Hassan the AI sales agent working. Scene 3: Revenue chart going up. CTA: Follow for more AI automation tips.",
    "agent_id": "hassan",
    "platform": "tiktok"
  }
}
```
