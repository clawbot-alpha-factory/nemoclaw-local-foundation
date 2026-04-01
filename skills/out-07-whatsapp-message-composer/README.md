# out-07-whatsapp-message-composer

**ID:** `out-07-whatsapp-message-composer`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** outreach

## Description

MENA-optimized. Relationship-first tone. Arabic + English. Ready for WhatsApp bridge. Warm intro weighting 3x.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `recipient_context` | string | Yes | Recipient details and relationship stage |
| `language` | string | No | Language: en, ar, bilingual |

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/out-07-whatsapp-message-composer/run.py --force --input recipient_context "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)
