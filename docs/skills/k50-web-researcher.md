# Web Researcher

**ID:** `k50-web-researcher` | **Version:** 1.0.0 | **Family:** K50 | **Domain:** K | **Type:** analyzer | **Tag:** research

## Description

Conducts structured web research on a given topic, synthesizes findings into a comprehensive brief with sources.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `research_query` | string | Yes | Research question or topic to investigate |
| `depth` | string | No | Research depth: quick, standard, deep |

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
- **Max Cost:** $0.3

## Composability

- **Output Type:** research_analyzer_output

## Example Usage

```json
{
  "inputs": {
    "research_query": "Current state of AI agent frameworks for enterprise sales automation in 2026, including pricing models, integration capabilities with major CRMs, and adoption rates among mid-market B2B companies",
    "depth": "standard"
  }
}
```
