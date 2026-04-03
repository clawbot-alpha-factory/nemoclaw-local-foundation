# Weekly Client Reporter

**ID:** `k61-weekly-client-reporter` | **Version:** 1.0.0 | **Family:** 61 | **Domain:** K | **Type:** generator | **Tag:** client-success

## Description

Automated weekly client report generation — metrics aggregation, progress summary, next steps. Produces professional client-ready reports with executive summary, detailed metrics, and recommendations.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `client_data` | string | Yes | Client name, services, KPIs, recent activity |
| `report_period` | string | Yes | Report time period |
| `include_sections` | string | No | Which sections to include |
| `tone` | string | No | Report tone |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | The generated output |
| `result_file` | file_path | Path to the markdown artifact |
| `envelope_file` | file_path | Path to the JSON envelope for skill chaining |

## Steps

- **step_1** — Parse Client Data (`local`, `general_short`)
- **step_2** — Generate Executive Summary (`llm`, `moderate`)
- **step_3** — Generate Detailed Metrics (`llm`, `moderate`)
- **step_4** — Generate Next Steps (`llm`, `moderate`)
- **step_5** — Quality Review (`critic`, `moderate`)
- **step_6** — Write Artifact (`local`, `general_short`)

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=N/A, max_improvements=N/A
- **Max Execution:** 120s
- **Max Cost:** $0.35

## Composability

- **Output Type:** client_success_generator_output

## Example Usage

```json
{
  "inputs": {
    "client_data": "Client: Acme Corp. Services: AI marketing automation + content generation. This week: 47 tasks completed, 12 blog posts generated, 3 ad campaigns launched (ROAS 3.2x), 2 leads converted to meetings. Monthly spend: $500. Pipeline generated: $12,000. Client health score: 8.5/10. No support tickets.",
    "report_period": "March 24-31 2026"
  }
}
```
