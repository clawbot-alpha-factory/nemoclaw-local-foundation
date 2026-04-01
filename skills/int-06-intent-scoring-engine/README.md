# int-06-intent-scoring-engine

**ID:** `int-06-intent-scoring-engine`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** intelligence

## Description

Turns raw signals into scored buying intent. Pain level, buying intent, urgency, recommended offer type. Feeds into lead qualification.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `raw_signals` | string | Yes | Raw demand signals with context |

## Outputs

- `result`
- `envelope_file`
- `insight`
- `recommended_action`
- `trigger_skill`
- `confidence`

## Usage

```bash
.venv313/bin/python3 skills/int-06-intent-scoring-engine/run.py --force --input raw_signals "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)
