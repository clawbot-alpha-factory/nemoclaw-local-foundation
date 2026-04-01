# k61-weekly-client-reporter

**ID:** `k61-weekly-client-reporter`
**Version:** 1.0.0
**Type:** executor
**Family:** 61 | **Domain:** K | **Tag:** client-success

## Description

Automated weekly client report generation — metrics aggregation, progress summary, next steps. Produces professional client-ready reports with executive summary, detailed metrics, and recommendations.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `client_data` | string | Yes | Client name, services, KPIs, recent activity |
| `report_period` | string | Yes | Report time period |
| `include_sections` | string | No | Which sections to include |
| `tone` | string | No | Report tone |

## Execution Steps

1. **Parse Client Data** (local) — Validate inputs, extract client parameters, prepare context.
2. **Generate Executive Summary** (llm) — Generate 2-3 paragraph executive summary — what was delivered, key wins, any issues, overall health.
3. **Generate Detailed Metrics** (llm) — Generate detailed metrics section — tasks completed, skills executed, costs, revenue attributed, SLA compliance, engagement.
4. **Generate Next Steps** (llm) — Generate next steps and recommendations — upcoming deliverables, optimization opportunities, expansion suggestions, risk flags.
5. **Quality Review** (critic) — Score output on clarity, completeness, client-readiness, and strategic value.
6. **Write Artifact** (local) — Write markdown artifact and JSON envelope.

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/k61-weekly-client-reporter/run.py --force --input client_data "value" --input report_period "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)
