# Micro SaaS Generator

**ID:** `scl-10-micro-saas-generator` | **Version:** 1.0.0 | **Type:** orchestrator | **Tag:** scale

## Description

Detects repeated problem from demand signals. Generates tool idea, landing page, MVP spec, deployment plan. Turns service revenue into product revenue. Bridge-ready for no-code APIs.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `problem_pattern` | string | Yes | Repeated problem detected from demand signals with volume data |
| `build_constraint` | string | No | Build approach: no_code_first, api_integration, full_build |

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

- **Output Type:** scale_orchestrator_output

## Example Usage

```json
{
  "inputs": {
    "problem_pattern": "Repeated problem detected from 156 demand signals across Reddit, Twitter, and LinkedIn: B2B service companies spend 2-4 hours writing each client proposal manually, with 23 percent containing errors. Average 10-15 proposals per month per company. Users express willingness to pay $100-300/month for a solution. Current workarounds: generic templates in Google Docs, expensive enterprise CPQ tools ($500+/month), or hiring junior staff dedicated to proposal writing.",
    "build_constraint": "no_code_first"
  }
}
```
