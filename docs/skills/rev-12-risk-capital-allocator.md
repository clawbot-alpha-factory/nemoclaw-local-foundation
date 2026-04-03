# Risk & Capital Allocator

**ID:** `rev-12-risk-capital-allocator` | **Version:** 1.0.0 | **Type:** orchestrator | **Tag:** revenue

## Description

Allocates time, budget, API spend, outreach volume based on confidence, past success rates, current revenue. Prevents spam and budget waste. Sits above rev-06.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `portfolio_state` | string | Yes | Current campaigns, budgets, performance, available resources |
| `risk_tolerance` | string | No | Risk tolerance: conservative, moderate, aggressive |

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
    "portfolio_state": "Campaign 1: LinkedIn Outreach - $400 spent, 12 qualified leads, 3 demos, 1 close ($8,500 revenue), ROAS 21.25x. Campaign 2: Google Ads - $1,200 spent, 8 qualified leads, 2 demos, 0 closes, ROAS 0x (still in pipeline). Campaign 3: Content Marketing - $600 spent, 22 inbound leads, 5 demos, 2 closes ($14,000 revenue), ROAS 23.3x. Campaign 4: Cold Email - $200 spent, 6 leads, 1 demo, 0 closes. Available unallocated budget: $1,600. Total monthly budget: $5,000.",
    "risk_tolerance": "moderate"
  }
}
```
