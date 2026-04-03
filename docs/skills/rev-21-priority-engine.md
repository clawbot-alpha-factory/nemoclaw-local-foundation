# Priority Scoring Engine

**ID:** `rev-21-priority-engine` | **Version:** 1.0.0 | **Type:** analyzer | **Tag:** revenue

## Description

Scores all pending tasks by urgency, value, staleness, confidence, agent fit. Outputs ranked priority queue. Used by rev-06 orchestrator.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `pending_tasks` | string | Yes | List of pending tasks with context |
| `current_pipeline` | string | No | Current pipeline state for context |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string |  |
| `result_file` | file_path |  |
| `envelope_file` | file_path |  |
| `insight` | string |  |
| `recommended_action` | string |  |
| `trigger_skill` | string |  |
| `confidence` | float |  |

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
    "pending_tasks": "Task 1: Follow up with CloudFirst (proposal sent 5 days ago, $15,000 deal, competitor evaluating). Task 2: Draft contract for GreenLeaf verbal agreement ($18,500). Task 3: Create outreach sequence for 12 new qualified leads from last week. Task 4: Publish blog post on AI onboarding (drafted, needs review). Task 5: Launch A/B test on landing page pricing section. Task 6: Respond to 3 inbound demo requests from yesterday. Task 7: Analyze last week content performance metrics. Task 8: Send invoice to DataBridge for completed project.",
    "current_pipeline": "8 active deals worth $94,000. Monthly target: $50,000. Closed so far: $34,500. Days remaining: 15. Two deals in negotiation stage."
  }
}
```
