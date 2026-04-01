# scl-02-partnership-proposal-writer

**ID:** `scl-02-partnership-proposal-writer`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** scale

## Description

Co-marketing, integration, white-label proposals. Personalized per partner.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `partner_info` | string | Yes | Potential partner details and synergies |
| `partnership_type` | string | No | Type: co_marketing, integration, white_label, referral |

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/scl-02-partnership-proposal-writer/run.py --force --input partner_info "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)
