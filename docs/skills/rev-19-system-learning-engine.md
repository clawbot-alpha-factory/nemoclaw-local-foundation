# System Learning Engine

**ID:** `rev-19-system-learning-engine` | **Version:** 1.0.0 | **Type:** analyzer | **Tag:** revenue

## Description

Tracks which skills lead to revenue, which sequences close deals, which content drives pipeline. Adjusts orchestrator priorities, sequence selection, offer focus. Turns static automation into adaptive intelligence. Persists to ~/.nemoclaw/system-learnings.json.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `system_performance_data` | string | Yes | Full system metrics: skill executions, outcomes, revenue events, conversion data |
| `learning_period` | string | No | Analysis period |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | The generated output |
| `result_file` | file_path | Path to the markdown artifact |
| `envelope_file` | file_path | Path to JSON envelope for skill chaining |
| `insight` | string | Key insight from analysis |
| `recommended_action` | string | Specific action to take |
| `trigger_skill` | string | Skill ID to trigger (or null to stop) |
| `confidence` | float | Confidence score 0-1 |

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=N/A, max_improvements=N/A
- **Max Execution:** 120s
- **Max Cost:** $0.3

## Composability

- **Output Type:** revenue_analyzer_output

## Example Usage

```json
{
  "inputs": {
    "system_performance_data": "Skill executions: 342 total (287 successful, 55 failed, 83.9 percent success rate). Top performing skills: k48-blog-post-writer (98 percent success), out-01-multi-touch-sequence-builder (95 percent success). Worst: rev-09-payment-execution-engine (62 percent success, mostly timeout errors). Revenue events: 11 deals closed ($127,500 total). Conversion data: LinkedIn outreach 8.2 percent reply rate (up from 5.4 percent last week), cold email 4.1 percent reply rate (flat). Content performance: blog posts driving 52 percent of inbound leads. LLM costs: $18.40 this week ($12.20 Anthropic, $4.80 OpenAI, $1.40 Google).",
    "learning_period": "last_7_days"
  }
}
```
