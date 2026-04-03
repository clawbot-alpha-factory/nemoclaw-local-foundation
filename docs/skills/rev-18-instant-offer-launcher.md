# Instant Offer Launcher

**ID:** `rev-18-instant-offer-launcher` | **Version:** 1.0.0 | **Type:** orchestrator | **Tag:** revenue

## Description

Full loop: demand signal → generate offer → create landing page → deploy payment link → start outreach → activate content loop → engage sales closer. Zero human intervention from detection to revenue.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `demand_signal` | string | Yes | Validated demand signal with urgency score and target ICP |
| `speed_mode` | string | No | Launch speed: fast (24h), standard (72h), thorough (1wk) |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | The generated output |
| `result_file` | file_path | Path to the markdown artifact |
| `envelope_file` | file_path | Path to JSON envelope for skill chaining |

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=N/A, max_improvements=N/A
- **Max Execution:** 180s
- **Max Cost:** $0.5

## Composability

- **Output Type:** revenue_orchestrator_output

## Example Usage

```json
{
  "inputs": {
    "demand_signal": "Validated demand: 156 signals for AI-powered proposal generation from discovery call notes. Urgency score: 8.4/10 (many commenters expressing immediate need). Target ICP: B2B service companies with 5-50 employees who send 10+ proposals per month. Willingness to pay signals: multiple comments mentioning budgets of $100-300/month for this capability. Competitive landscape: no dedicated solution exists, current alternatives are generic AI writing tools.",
    "speed_mode": "fast"
  }
}
```
