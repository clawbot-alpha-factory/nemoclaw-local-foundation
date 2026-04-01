# rev-09-payment-execution-engine

**ID:** `rev-09-payment-execution-engine`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** revenue

## Description

Sends payment links (Lemon Squeezy/Stripe), tracks payment status, triggers onboarding when paid, handles retries for failed payments.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `invoice_data` | string | Yes | Invoice details: client, amount, services, terms |
| `payment_provider` | string | No | Payment provider |

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/rev-09-payment-execution-engine/run.py --force --input invoice_data "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)
