# Live Experiment Runner

**ID:** `rev-13-live-experiment-runner` | **Version:** 1.0.0 | **Type:** executor | **Tag:** revenue

## Description

Runs A/B tests live: subject lines, offers, hooks. Routes traffic 50/50, collects results in real-time, declares winners with confidence scores.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `experiment_spec` | string | Yes | What to test: variants, success metric, sample size |
| `confidence_threshold` | string | No | Statistical confidence required to declare winner |

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
    "experiment_spec": "Test: Subject line personalization impact on cold email open rates. Variant A: Generic industry reference ('Scaling [Industry] operations with AI'). Variant B: Company-specific reference ('How [Company] can automate [specific pain point]'). Variant C: Mutual connection reference ('Noticed we both know [connection]'). Success metric: open rate and reply rate. Sample size per variant: 100 sends. Duration: 7 days.",
    "confidence_threshold": "0.90"
  }
}
```
