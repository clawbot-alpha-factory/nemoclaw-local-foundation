# biz-05-client-health-monitor

**ID:** `biz-05-client-health-monitor`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** business

## Description

Scores client satisfaction 0-100. Tracks deliverable completion, response times, sentiment. Triggers proactive outreach on decline.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `client_data` | string | Yes | Client engagement data: deliverables, communications, feedback |
| `threshold` | string | No | Health score threshold for intervention |

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
.venv313/bin/python3 skills/biz-05-client-health-monitor/run.py --force --input client_data "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)
