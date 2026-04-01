# cnt-16-screen-capture-video

**ID:** `cnt-16-screen-capture-video`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** content-factory

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

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/cnt-16-screen-capture-video/run.py --force --input task_description "value" --input agent_id "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)
