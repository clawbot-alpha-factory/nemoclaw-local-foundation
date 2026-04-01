# scl-04-podcast-guest-pitch-writer

**ID:** `scl-04-podcast-guest-pitch-writer`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** scale

## Description

Personalized pitches for podcast appearances. Includes talking points, bio, value prop for host's audience.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `podcast_info` | string | Yes | Podcast name, host, audience, recent episodes |
| `expertise` | string | Yes | Your expertise and unique angle |

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/scl-04-podcast-guest-pitch-writer/run.py --force --input podcast_info "value" --input expertise "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)
