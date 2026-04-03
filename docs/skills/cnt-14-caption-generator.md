# Caption Generator

**ID:** `cnt-14-caption-generator` | **Version:** 1.0.0 | **Type:** transformer | **Tag:** content-factory

## Description

Generates styled captions for video content. Transcribes audio via whisper bridge, applies platform-specific caption styling, and validates output.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `audio_path` | string | Yes | Path to audio file for transcription |
| `style` | string | No | Caption style preset (tiktok, youtube, instagram) |
| `highlight_color` | string | No | Highlight color for emphasized words |

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
- **Max Cost:** $0.3

## Composability

- **Output Type:** content_transformer_output

## Example Usage

```json
{
  "inputs": {
    "audio_path": "assets/voices/generated/hassan_voice.wav",
    "style": "tiktok"
  }
}
```
