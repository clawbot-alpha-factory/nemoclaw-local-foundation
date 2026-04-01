# rev-08-agentic-service-packager

**ID:** `rev-08-agentic-service-packager`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** revenue

## Description

Packages NemoClaw capabilities as sellable services. Generates pricing, scope, deliverables, timeline for client proposals.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `capability_description` | string | Yes | What the system can do for this client |
| `client_industry` | string | No | Client's industry |

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/rev-08-agentic-service-packager/run.py --force --input capability_description "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)
