# biz-03-invoice-generator

**ID:** `biz-03-invoice-generator`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** business

## Description

From contract → invoice with payment link (Lemon Squeezy bridge ready). Professional formatting.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `contract_details` | string | Yes | Contract details: client, services, amounts, payment terms |
| `payment_method` | string | No | Payment provider for link generation |

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/biz-03-invoice-generator/run.py --force --input contract_details "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)
