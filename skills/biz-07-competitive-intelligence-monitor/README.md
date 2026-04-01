# biz-07-competitive-intelligence-monitor

**ID:** `biz-07-competitive-intelligence-monitor`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** business

## Description

Daily scan of competitor pricing, features, messaging. Weekly summary. Alerts on major changes. Enforced action output.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `competitors` | string | Yes | Competitors to monitor: names, URLs, focus areas |
| `focus_areas` | string | No | What to monitor |

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
.venv313/bin/python3 skills/biz-07-competitive-intelligence-monitor/run.py --force --input competitors "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)
