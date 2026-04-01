# k57-nda-generator

**ID:** `k57-nda-generator`
**Version:** 1.0.0
**Type:** executor
**Family:** K57 | **Domain:** K | **Tag:** legal

## Description

Generate NDA (Non-Disclosure Agreement) documents from party details. Supports mutual and unilateral NDAs with MENA-aware legal terms.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `disclosing_party` | string | Yes | Disclosing party name and details |
| `receiving_party` | string | Yes | Receiving party name and details |
| `jurisdiction` | string | No | Legal jurisdiction for the NDA |
| `nda_type` | string | No | Type of NDA: mutual or unilateral |
| `confidential_scope` | string | No | Scope of confidential information covered |
| `duration_months` | string | No | Duration of NDA in months |

## Execution Steps

1. **Parse Parties** (local) — Validate inputs, extract party details, prepare NDA context.
2. **Draft NDA** (llm) — Draft complete NDA document with all standard clauses and party-specific terms.
3. **Legal Review** (critic) — Score NDA on legal completeness, enforceability, clarity, and jurisdiction compliance.
4. **Write Artifact** (local) — Write markdown artifact and JSON envelope.

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/k57-nda-generator/run.py --force --input disclosing_party "value" --input receiving_party "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)
