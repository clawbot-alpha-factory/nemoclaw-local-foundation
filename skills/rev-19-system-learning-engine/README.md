# rev-19-system-learning-engine

**ID:** `rev-19-system-learning-engine`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** revenue

## Description

Tracks which skills lead to revenue, which sequences close deals, which content drives pipeline. Adjusts orchestrator priorities, sequence selection, offer focus. Turns static automation into adaptive intelligence. Persists to ~/.nemoclaw/system-learnings.json.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `system_performance_data` | string | Yes | Full system metrics: skill executions, outcomes, revenue events, conversion data |
| `learning_period` | string | No | Analysis period |

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
.venv313/bin/python3 skills/rev-19-system-learning-engine/run.py --force --input system_performance_data "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)
