# Daily Content Factory

**ID:** `cnt-15-daily-content-factory` | **Version:** 1.0.0 | **Type:** orchestrator | **Tag:** content-factory

## Description

Master orchestrator that runs the daily content pipeline. Analyzes yesterday's performance, plans content mix, generates scripts in batch, composes videos via cnt-12, distributes via cnt-08/cnt-09, and produces a daily report.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `date` | string | Yes | Target date for content production (YYYY-MM-DD) |
| `content_mix` | string | No | Override content mix (JSON object) |
| `theme` | string | No | Daily theme or narrative arc |
| `accounts` | string | No | Comma-separated account IDs to produce for |

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

- **Output Type:** content_orchestrator_output

## Example Usage

```json
{
  "inputs": {
    "date": "2026-04-02",
    "theme": "AI automation journey week 1"
  }
}
```
