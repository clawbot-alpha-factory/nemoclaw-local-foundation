# scl-10-micro-saas-generator

**ID:** `scl-10-micro-saas-generator`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** scale

## Description

Detects repeated problem from demand signals. Generates tool idea, landing page, MVP spec, deployment plan. Turns service revenue into product revenue. Bridge-ready for no-code APIs.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `problem_pattern` | string | Yes | Repeated problem detected from demand signals with volume data |
| `build_constraint` | string | No | Build approach: no_code_first, api_integration, full_build |

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/scl-10-micro-saas-generator/run.py --force --input problem_pattern "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)
