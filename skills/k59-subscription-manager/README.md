# k59-subscription-manager

**ID:** `k59-subscription-manager`
**Version:** 1.0.0
**Type:** executor
**Family:** 59 | **Domain:** K | **Tag:** revenue

## Description

Subscription lifecycle management — renewals, upgrades, downgrades, churn prediction, plan changes. Analyzes subscription health and generates actionable recommendations.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `subscription_data` | string | Yes | JSON of current subscriptions, plans, usage |
| `action` | string | Yes | Action to perform |
| `customer_id` | string | No | Optional customer identifier |
| `lookback_days` | string | No | Number of days to look back for analysis |

## Execution Steps

1. **Parse Subscription Data** (local) — Validate inputs, extract subscription parameters, prepare context.
2. **Analyze Patterns** (llm) — Analyze subscription health — MRR trends, churn signals, usage patterns, payment history, engagement decay.
3. **Generate Recommendations** (llm) — Generate specific actions — renewal timing, upsell opportunities, at-risk interventions, plan optimization, pricing adjustment recommendations.
4. **Quality Review** (critic) — Score output on analytical depth, actionability, revenue impact, and strategic value.
5. **Write Artifact** (local) — Write markdown artifact and JSON envelope.

## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/k59-subscription-manager/run.py --force --input subscription_data "value" --input action "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)
