# Subscription Manager

**ID:** `k59-subscription-manager` | **Version:** 1.0.0 | **Family:** 59 | **Domain:** K | **Type:** executor | **Tag:** revenue

## Description

Subscription lifecycle management — renewals, upgrades, downgrades, churn prediction, plan changes. Analyzes subscription health and generates actionable recommendations.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `subscription_data` | string | Yes | JSON of current subscriptions, plans, usage |
| `action` | string | Yes | Action to perform |
| `customer_id` | string | No | Optional customer identifier |
| `lookback_days` | string | No | Number of days to look back for analysis |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | The generated output |
| `result_file` | file_path | Path to the markdown artifact |
| `envelope_file` | file_path | Path to the JSON envelope for skill chaining |

## Steps

- **step_1** — Parse Subscription Data (`local`, `general_short`)
- **step_2** — Analyze Patterns (`llm`, `moderate`)
- **step_3** — Generate Recommendations (`llm`, `moderate`)
- **step_4** — Quality Review (`critic`, `moderate`)
- **step_5** — Write Artifact (`local`, `general_short`)

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=N/A, max_improvements=N/A
- **Max Execution:** 90s
- **Max Cost:** $0.25

## Composability

- **Output Type:** revenue_executor_output

## Example Usage

```json
{
  "inputs": {
    "subscription_data": "5 active subscriptions: Acme Corp $500/mo (12 months, usage declining 15%), TechFlow $200/mo (3 months, usage growing 40%), DataPrime $1000/mo (6 months, stable), QuickBuild $150/mo (1 month trial ending), MenaDigital $300/mo (9 months, 2 support tickets this week)",
    "action": "churn_prediction"
  }
}
```
