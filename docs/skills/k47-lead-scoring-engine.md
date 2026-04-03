# Lead Scoring Engine

**ID:** `k47-lead-scoring-engine` | **Version:** 1.0.0 | **Family:** K47 | **Domain:** K | **Type:** analyzer | **Tag:** sales

## Description

Scores leads based on fit (ICP match), intent signals, engagement data, and assigns priority tiers.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `lead_data` | string | Yes | Lead information including company, role, engagement |
| `icp_criteria` | string | No | Ideal customer profile criteria |

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

- **Output Type:** sales_analyzer_output

## Example Usage

```json
{
  "inputs": {
    "lead_data": "Lead 1: Ahmad Khalil, CTO at CloudServe (45 employees, SaaS), visited pricing page 3 times, downloaded whitepaper, attended webinar. Lead 2: Maria Santos, Ops Manager at RetailFlow (120 employees, e-commerce), opened 2 emails, no website visits. Lead 3: James Chen, CEO at DataPulse (18 employees, analytics SaaS), booked demo, engaged on LinkedIn, company raised Series A last month. Lead 4: Sarah Novak, Marketing Director at AdScale (200 employees, adtech), clicked one email link, unsubscribed from newsletter.",
    "icp_criteria": "SaaS 50-200 employees MENA"
  }
}
```
