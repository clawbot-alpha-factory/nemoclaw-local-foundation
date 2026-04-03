# Review Monitor

**ID:** `k54-review-monitor` | **Version:** 1.0.0 | **Family:** K54 | **Domain:** K | **Type:** analyzer | **Tag:** research

## Description

Monitors and synthesizes product/service reviews, extracts sentiment trends, and flags critical issues.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `review_data` | string | Yes | Reviews, ratings, or feedback to analyze |
| `product_name` | string | No | Product or service name |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | The generated output |
| `result_file` | file_path | Path to the markdown artifact |
| `envelope_file` | file_path | Path to the JSON envelope for skill chaining |

## Steps

- **step_1** — Parse input and prepare analysis context (`local`, `general_short`)
- **step_2** — Generate primary output (`llm`, `moderate`)
- **step_3** — Evaluate output quality (`critic`, `moderate`)
- **step_5** — Validate and write artifact (`local`, `general_short`)

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=N/A, max_improvements=N/A
- **Max Execution:** 120s
- **Max Cost:** $0.3

## Composability

- **Output Type:** research_analyzer_output

## Example Usage

```json
{
  "inputs": {
    "review_data": "Review 1 (G2, 5 stars): 'NemoClaw automated our entire proposal workflow. Saving 15 hours per week.' Review 2 (G2, 3 stars): 'Good tool but the onboarding documentation could be clearer. Took 2 weeks to fully set up.' Review 3 (Capterra, 4 stars): 'Excellent AI accuracy but wish it had native Salesforce integration.' Review 4 (TrustRadius, 5 stars): 'Game changer for our small sales team. ROI in the first month.' Review 5 (G2, 2 stars): 'Support response times are slow. Had to wait 3 days for a critical issue.'",
    "product_name": "NemoClaw"
  }
}
```
