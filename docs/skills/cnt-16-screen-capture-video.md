# Screen Capture Video

**ID:** `cnt-16-screen-capture-video` | **Version:** 1.0.0 | **Type:** executor | **Tag:** content-factory

## Description

Creates screen recording timelapse videos. Captures screenshots via PinchTab, generates narration via fish-speech, composes timelapse video, and adds captions.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `task_description` | string | Yes | Description of the task being recorded |
| `agent_id` | string | Yes | Agent performing the task |
| `narration_text` | string | Yes | Narration script for the video |
| `speed_multiplier` | string | No | Timelapse speed multiplier |

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
    "task_description": "Find 50 B2B SaaS leads in the MENA region",
    "agent_id": "hassan",
    "narration_text": "Watch our AI sales agent find 50 qualified leads in under 30 seconds."
  }
}
```
