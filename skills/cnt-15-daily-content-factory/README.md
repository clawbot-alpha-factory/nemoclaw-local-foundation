# cnt-15-daily-content-factory

**ID:** `cnt-15-daily-content-factory`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** content-factory

## Description

Master orchestrator that runs the daily content pipeline. Analyzes yesterday's performance, plans content mix, generates scripts in batch, composes videos via cnt-12, distributes via cnt-08/cnt-09, and produces a daily report.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `date` | string | Yes | Target date for content production (YYYY-MM-DD) |
| `content_mix` | string | No | Override content mix (JSON object) |
| `theme` | string | No | Daily theme or narrative arc |
| `accounts` | string | No | Comma-separated account IDs to produce for |

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/cnt-15-daily-content-factory/run.py --force --input date "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)
