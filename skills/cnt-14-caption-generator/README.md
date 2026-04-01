# cnt-14-caption-generator

**ID:** `cnt-14-caption-generator`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** content-factory

## Description

Generates styled captions for video content. Transcribes audio via whisper bridge, applies platform-specific caption styling, and validates output.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `audio_path` | string | Yes | Path to audio file for transcription |
| `style` | string | No | Caption style preset (tiktok, youtube, instagram) |
| `highlight_color` | string | No | Highlight color for emphasized words |

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/cnt-14-caption-generator/run.py --force --input audio_path "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)
