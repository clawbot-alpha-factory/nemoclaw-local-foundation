# k60-refund-dispute-handler

**ID:** `k60-refund-dispute-handler`
**Version:** 1.0.0
**Type:** executor
**Family:** 60 | **Domain:** K | **Tag:** revenue

## Description

Payment dispute resolution — refund processing, dispute analysis, resolution recommendations, credit notes. Analyzes disputes and generates fair, defensible resolution recommendations.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `dispute_context` | string | Yes | What happened, client complaint, invoice details |
| `dispute_type` | string | Yes | Type of dispute |
| `client_info` | string | Yes | Client name, subscription details, history |
| `amount_usd` | string | No | Disputed amount in USD |
| `service_period` | string | No | Service period in question |

## Execution Steps

1. **Parse Dispute** (local) — Validate inputs, extract dispute parameters, prepare context.
2. **Analyze Case** (llm) — Analyze the dispute — validity assessment, service delivery vs promise, contract terms, precedent, financial impact.
3. **Generate Resolution** (llm) — Generate resolution recommendation — refund/partial/credit/deny with rationale, client communication draft, prevention measures.
4. **Quality Review** (critic) — Score output on fairness, completeness, client retention impact, and legal defensibility.
5. **Write Artifact** (local) — Write markdown artifact and JSON envelope.

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/k60-refund-dispute-handler/run.py --force --input dispute_context "value" --input dispute_type "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)
