# k54-review-monitor

**ID:** `k54-review-monitor`
**Version:** 1.0.0
**Type:** executor
**Family:** K54 | **Domain:** K | **Tag:** research

## Description

Monitors and synthesizes product/service reviews, extracts sentiment trends, and flags critical issues.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `review_data` | string | Yes | Reviews, ratings, or feedback to analyze |
| `product_name` | string | No | Product or service name |

## Execution Steps

1. **Parse input and prepare analysis context** (local) — Validate inputs, extract key parameters, prepare context for generation.
2. **Generate primary output** (llm) — Core generation step using execution_role persona.
3. **Evaluate output quality** (critic) — Score output on relevance, completeness, and actionability.
4. **Validate and write artifact** (local) — Write markdown artifact and JSON envelope.

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/k54-review-monitor/run.py --force --input review_data "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)
