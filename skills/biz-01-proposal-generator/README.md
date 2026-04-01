# biz-01-proposal-generator

**ID:** `biz-01-proposal-generator`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** business

## Description

Client-specific proposals with scope, pricing from catalog, timeline, case studies, terms. Uses rev-08 Agentic Service Packager output.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `client_needs` | string | Yes | Client requirements and pain points |
| `services` | string | Yes | Services to propose with pricing |

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/biz-01-proposal-generator/run.py --force --input client_needs "value" --input services "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)
