# Payment Execution Engine

**ID:** `rev-09-payment-execution-engine` | **Version:** 1.0.0 | **Type:** executor | **Tag:** revenue

## Description

Sends payment links (Lemon Squeezy/Stripe), tracks payment status, triggers onboarding when paid, handles retries for failed payments.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `invoice_data` | string | Yes | Invoice details: client, amount, services, terms |
| `payment_provider` | string | No | Payment provider |

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
- **Max Execution:** 90s
- **Max Cost:** $0.25

## Composability

- **Output Type:** revenue_executor_output

## Example Usage

```json
{
  "inputs": {
    "invoice_data": "Client: NovaTech MENA (Layla Haddad, CEO). Invoice #NMC-2026-0051. Services: AI Sales Automation Suite Setup ($12,000), Monthly Management Fee - First Month ($3,500), Custom CRM Integration ($6,500). Total: $22,000. Payment terms: 50 percent upfront, 50 percent on delivery. First payment due: $11,000.",
    "payment_provider": "lemon_squeezy"
  }
}
```
