# Proposal Generator

**ID:** `biz-01-proposal-generator` | **Version:** 1.0.0 | **Type:** generator | **Tag:** business

## Description

Client-specific proposals with scope, pricing from catalog, timeline, case studies, terms. Uses rev-08 Agentic Service Packager output.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `client_needs` | string | Yes | Client requirements and pain points |
| `services` | string | Yes | Services to propose with pricing |

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
    "client_needs": "Mid-size e-commerce company struggling with abandoned cart rates above 72 percent, seeking AI-driven retargeting and personalized follow-up sequences to recover lost revenue and improve customer lifetime value",
    "services": "AI-powered abandoned cart recovery automation at $2,500/month, personalized email sequence builder at $1,200/month, real-time customer behavior analytics dashboard at $800/month"
  }
}
```
