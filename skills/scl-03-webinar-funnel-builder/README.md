# scl-03-webinar-funnel-builder

**ID:** `scl-03-webinar-funnel-builder`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** scale

## Description

Full funnel: landing page copy → registration sequence → reminder emails → webinar script → follow-up sequence → offer.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `webinar_topic` | string | Yes | Webinar topic and value proposition |
| `target_audience` | string | Yes | Who should attend |

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/scl-03-webinar-funnel-builder/run.py --force --input webinar_topic "value" --input target_audience "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)
