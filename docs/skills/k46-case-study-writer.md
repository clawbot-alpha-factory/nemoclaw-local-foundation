# Case Study Writer

**ID:** `k46-case-study-writer` | **Version:** 1.0.0 | **Family:** K46 | **Domain:** K | **Type:** generator | **Tag:** content

## Description

Produces professional case studies with challenge-solution-results structure and quantified outcomes.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `client_context` | string | Yes | Client name, industry, challenge, solution applied, results achieved |
| `tone` | string | No | Writing tone |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | The generated output |
| `result_file` | file_path | Path to the markdown artifact |
| `envelope_file` | file_path | Path to the JSON envelope for skill chaining |

## Steps

- **step_1** — Parse input and prepare analysis context (`local`, `general_short`)
- **step_2** — Generate primary output (`llm`, `premium`)
- **step_3** — Evaluate output quality (`critic`, `moderate`)
- **step_5** — Validate and write artifact (`local`, `general_short`)

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=N/A, max_improvements=N/A
- **Max Execution:** 120s
- **Max Cost:** $0.35

## Composability

- **Output Type:** content_generator_output

## Example Usage

```json
{
  "inputs": {
    "client_context": "Client: Pinnacle Logistics, a mid-size freight forwarding company with 85 employees in Amman, Jordan. Challenge: manual quote generation taking 4 hours per quote with 23 percent error rate, losing deals to faster competitors. Solution: deployed AI-powered quote automation system integrated with their ERP. Results: quote generation reduced to 12 minutes (97 percent faster), error rate dropped to 1.4 percent, win rate improved from 18 to 31 percent, $420,000 additional revenue in first 6 months.",
    "tone": "professional"
  }
}
```
