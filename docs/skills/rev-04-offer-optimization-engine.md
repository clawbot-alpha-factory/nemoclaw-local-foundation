# Offer Optimization Engine

**ID:** `rev-04-offer-optimization-engine` | **Version:** 1.0.0 | **Type:** analyzer | **Tag:** revenue

## Description

Tests which offer converts best. Tracks win rates per pricing/packaging variant. Outputs insight + recommended_action + trigger_skill.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `offer_performance_data` | string | Yes | Offer variants with conversion rates and revenue |
| `market_context` | string | No | Market context |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | The generated output |
| `result_file` | file_path | Path to the markdown artifact |
| `envelope_file` | file_path | Path to JSON envelope for skill chaining |
| `insight` | string | Key insight from analysis |
| `recommended_action` | string | Specific action to take |
| `trigger_skill` | string | Skill ID to trigger (or null to stop) |
| `confidence` | float | Confidence score 0-1 |

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=N/A, max_improvements=N/A
- **Max Execution:** 120s
- **Max Cost:** $0.3

## Composability

- **Output Type:** revenue_analyzer_output

## Example Usage

```json
{
  "inputs": {
    "offer_performance_data": "Offer A (Monthly retainer $2,500/mo): 45 proposals sent, 8 closed (17.8 percent), avg LTV $15,000. Offer B (Project-based $8,500 one-time): 30 proposals sent, 11 closed (36.7 percent), avg LTV $8,500. Offer C (Hybrid: $5,000 setup + $1,200/mo): 22 proposals sent, 6 closed (27.3 percent), avg LTV $19,400. Offer D (Free audit + $3,500/mo): 18 proposals sent, 2 closed (11.1 percent), avg LTV $21,000.",
    "market_context": "B2B SaaS automation services"
  }
}
```
