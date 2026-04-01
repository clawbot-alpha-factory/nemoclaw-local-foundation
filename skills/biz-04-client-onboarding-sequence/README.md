# biz-04-client-onboarding-sequence

**ID:** `biz-04-client-onboarding-sequence`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** business

## Description

Payment confirmed → welcome email (Resend) → setup checklist → first deliverable schedule → 7-day check-in. Bridge-connected.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `client_info` | string | Yes | New client details: name, service purchased, start date |
| `service_type` | string | No | Service purchased |

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/biz-04-client-onboarding-sequence/run.py --force --input client_info "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)
