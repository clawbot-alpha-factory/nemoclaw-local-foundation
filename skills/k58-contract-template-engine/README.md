# k58-contract-template-engine

**ID:** `k58-contract-template-engine`
**Version:** 1.0.0
**Type:** executor
**Family:** K58 | **Domain:** K | **Tag:** legal

## Description

Generate MSA (Master Service Agreement) and SLA (Service Level Agreement) templates. Produces professional contract documents with MENA-aware legal terms.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `contract_type` | string | Yes | Type of contract: MSA, SLA, or SOW |
| `provider_info` | string | Yes | Service provider name, location, and description |
| `client_info` | string | Yes | Client name, location, and business type |
| `service_description` | string | Yes | Description of services to be provided |
| `jurisdiction` | string | No | Legal jurisdiction |
| `payment_terms` | string | No | Payment terms and billing schedule |
| `sla_metrics` | string | No | SLA metrics and targets (for SLA type contracts) |

## Execution Steps

1. **Parse Contract Request** (local) — Validate inputs, extract contract parameters, prepare drafting context.
2. **Draft Contract** (llm) — Draft complete contract document with all standard clauses and party-specific terms.
3. **Legal Compliance Check** (critic) — Score contract on legal completeness, enforceability, clarity, and jurisdiction compliance.
4. **Write Artifact** (local) — Write markdown artifact and JSON envelope.

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/k58-contract-template-engine/run.py --force --input contract_type "value" --input provider_info "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)
