# Invoice Generator

**ID:** `biz-03-invoice-generator` | **Version:** 1.0.0 | **Type:** generator | **Tag:** business

## Description

From contract → invoice with payment link (Lemon Squeezy bridge ready). Professional formatting.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `contract_details` | string | Yes | Contract details: client, services, amounts, payment terms |
| `payment_method` | string | No | Payment provider for link generation |

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
- **Max Execution:** 120s
- **Max Cost:** $0.35

## Composability

- **Output Type:** business_generator_output

## Example Usage

```json
{
  "inputs": {
    "contract_details": "Client: TechVentures MENA, Invoice #NMC-2026-0042. Services: AI Workflow Automation Phase 1 ($6,000), Chatbot MVP Development ($4,500), Analytics Dashboard Setup ($2,500). Total: $13,000. Payment terms: Net 15. Due date: 2026-04-15.",
    "payment_method": "lemon_squeezy"
  }
}
```
