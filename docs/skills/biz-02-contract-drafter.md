# Contract Drafter

**ID:** `biz-02-contract-drafter` | **Version:** 1.0.0 | **Type:** generator | **Tag:** business

## Description

SOW/MSA from proposal. Customizable clauses. MENA-aware legal terms.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `proposal_summary` | string | Yes | Approved proposal details: scope, pricing, timeline |
| `jurisdiction` | string | No | Legal jurisdiction |

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
    "proposal_summary": "Approved proposal for TechVentures MENA: 6-month AI automation engagement covering workflow optimization, chatbot deployment, and analytics dashboard. Total value $18,000 paid in 3 monthly installments of $6,000. Deliverables include initial audit (week 1-2), chatbot MVP (week 3-6), dashboard build (week 7-10), training and handoff (week 11-12).",
    "jurisdiction": "Jordan/MENA"
  }
}
```
