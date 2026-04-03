# Auto Business Launcher

**ID:** `rev-22-auto-business-launcher` | **Version:** 1.0.0 | **Type:** orchestrator | **Tag:** revenue

## Description

Full autonomous loop: detect demand → generate offer → create landing page → payment link → content → outreach → sales. Zero human intervention from signal to revenue.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `demand_signal` | string | Yes | Validated demand signal with confidence score and ICP |
| `budget_limit` | string | No | Maximum budget in USD for launch |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string |  |
| `result_file` | file_path |  |
| `envelope_file` | file_path |  |

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
    "demand_signal": "Validated demand for AI-powered proposal generator. Confidence: 0.87. ICP: B2B service companies (agencies, consultancies, IT services) with 5-50 employees sending 10+ proposals monthly. Signal volume: 156 across 3 platforms. Price sensitivity: $100-300/month range. Build complexity: moderate (leverages existing LLM routing and template engine). Estimated time to MVP: 2 weeks.",
    "budget_limit": "50"
  }
}
```
