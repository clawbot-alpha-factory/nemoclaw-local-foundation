# biz-02-contract-drafter

**ID:** `biz-02-contract-drafter`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** business

## Description

SOW/MSA from proposal. Customizable clauses. MENA-aware legal terms.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `proposal_summary` | string | Yes | Approved proposal details: scope, pricing, timeline |
| `jurisdiction` | string | No | Legal jurisdiction |

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/biz-02-contract-drafter/run.py --force --input proposal_summary "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)
