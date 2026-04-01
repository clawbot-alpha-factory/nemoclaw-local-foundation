# scl-07-cross-channel-scheduler

**ID:** `scl-07-cross-channel-scheduler`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** scale

## Description

Takes content queue → schedules across all channels at optimal times. Bridge-ready for Buffer/Hootsuite APIs.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `content_queue` | string | Yes | Content pieces ready for scheduling |
| `timezone` | string | No | Target timezone |

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/scl-07-cross-channel-scheduler/run.py --force --input content_queue "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)
