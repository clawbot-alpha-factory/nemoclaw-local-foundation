# scl-05-community-growth-engine

**ID:** `scl-05-community-growth-engine`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** scale

## Description

Content strategy + engagement rules + member acquisition sequence + retention triggers. Full community lifecycle.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `community_vision` | string | Yes | Community purpose, target members, platform |
| `platform` | string | No | Community platform |

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/scl-05-community-growth-engine/run.py --force --input community_vision "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)
