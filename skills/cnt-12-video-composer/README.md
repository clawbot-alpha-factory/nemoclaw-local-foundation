# cnt-12-video-composer

**ID:** `cnt-12-video-composer`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** content-factory

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

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/cnt-12-video-composer/run.py --force --input script_text "value" --input agent_id "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)
