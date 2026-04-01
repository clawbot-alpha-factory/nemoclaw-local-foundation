# out-05-outreach-personalization-engine

**ID:** `out-05-outreach-personalization-engine`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** outreach

## Description

Takes generic templates + lead data → hyper-personalized messages using company info, recent news, mutual connections.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `template` | string | Yes | Generic outreach template |
| `lead_context` | string | Yes | Lead details: company, role, recent news, connections |

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/out-05-outreach-personalization-engine/run.py --force --input template "value" --input lead_context "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)
