# rev-13-live-experiment-runner

**ID:** `rev-13-live-experiment-runner`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** revenue

## Description

Runs A/B tests live: subject lines, offers, hooks. Routes traffic 50/50, collects results in real-time, declares winners with confidence scores.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `experiment_spec` | string | Yes | What to test: variants, success metric, sample size |
| `confidence_threshold` | string | No | Statistical confidence required to declare winner |

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/rev-13-live-experiment-runner/run.py --force --input experiment_spec "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)
