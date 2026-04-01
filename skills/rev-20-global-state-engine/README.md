# rev-20-global-state-engine

**ID:** `rev-20-global-state-engine`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** revenue

## Description

Reads and updates the global state layer. Stores leads, deals, content performance, experiments, channel ROI. Makes the system stateful across all runs.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `state_update` | string | Yes | What to update: new lead, deal stage change, performance metric |
| `collection` | string | No | Collection: leads, deals, content, experiments, channels, learnings |

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/rev-20-global-state-engine/run.py --force --input state_update "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)
