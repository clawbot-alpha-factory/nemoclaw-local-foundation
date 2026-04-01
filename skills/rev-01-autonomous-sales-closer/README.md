# rev-01-autonomous-sales-closer

**ID:** `rev-01-autonomous-sales-closer`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** revenue

## Description

Multi-step deal progression: qualify, pitch, handle objections, propose, close. Chains 5+ skills per deal. Thread-aware conversation memory. Triggers out-02 Email Executor, WhatsApp bridge, calendar hooks.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `lead_data` | string | Yes | Lead information: name, company, role, pain points, engagement history |
| `offer_context` | string | No | What we're selling |

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/rev-01-autonomous-sales-closer/run.py --force --input lead_data "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)
