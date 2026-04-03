# Refund & Dispute Handler

**ID:** `k60-refund-dispute-handler` | **Version:** 1.0.0 | **Family:** 60 | **Domain:** K | **Type:** executor | **Tag:** revenue

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

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | The generated output |
| `result_file` | file_path | Path to the markdown artifact |
| `envelope_file` | file_path | Path to the JSON envelope for skill chaining |

## Steps

- **step_1** — Parse Dispute (`local`, `general_short`)
- **step_2** — Analyze Case (`llm`, `moderate`)
- **step_3** — Generate Resolution (`llm`, `moderate`)
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
    "dispute_context": "Client Acme Corp claims they were billed for March but AI automation service was down for 3 days due to API outage. Invoice amount $500. Service was restored on March 4th. Client requests full month refund.",
    "dispute_type": "partial_refund",
    "client_info": "Acme Corp, 12-month subscriber, $500/mo plan, good payment history",
    "amount_usd": "500",
    "service_period": "March 2026"
  }
}
```
