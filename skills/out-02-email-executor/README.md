# out-02-email-executor

**ID:** `out-02-email-executor`
**Version:** 1.0.0
**Type:** executor
**Family:** ? | **Domain:** ? | **Tag:** outreach

## Description

Sends emails via Resend bridge. Tracks opens/replies. Triggers next step in sequence. Bridge-connected.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `email_spec` | string | Yes | Email details: to, subject, body, from_email |
| `sequence_context` | string | No | Where in the sequence this email falls |

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/out-02-email-executor/run.py --force --input email_spec "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)
