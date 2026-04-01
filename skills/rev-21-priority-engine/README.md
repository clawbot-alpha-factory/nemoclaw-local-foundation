# rev-21-priority-engine

**ID:** `rev-21-priority-engine`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** revenue

## Description

Scores all pending tasks by urgency, value, staleness, confidence, agent fit. Outputs ranked priority queue. Used by rev-06 orchestrator.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `pending_tasks` | string | Yes | List of pending tasks with context |
| `current_pipeline` | string | No | Current pipeline state for context |

## Outputs

- `result`
- `result_file`
- `envelope_file`
- `insight`
- `recommended_action`
- `trigger_skill`
- `confidence`

## Usage

```bash
.venv313/bin/python3 skills/rev-21-priority-engine/run.py --force --input pending_tasks "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)
