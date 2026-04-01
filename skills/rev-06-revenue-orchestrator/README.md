# rev-06-revenue-orchestrator

**ID:** `rev-06-revenue-orchestrator`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** revenue

## Description

Meta-skill: decides what to do next based on pipeline state. No leads → trigger content. Low conversion → trigger offer optimizer. Stale deals → trigger follow-up. Consumes all analyzer outputs. Confidence gating: auto-execute if confidence > 0.8 and demand_volume high.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `pipeline_state` | string | Yes | Current pipeline: leads, deals, conversion rates, revenue, bottlenecks |
| `available_budget` | string | No | Available daily budget in USD |

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/rev-06-revenue-orchestrator/run.py --force --input pipeline_state "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)
