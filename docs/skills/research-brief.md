# research-brief

**ID:** `research-brief` | **Version:** 1.0.0

## Description

Takes a topic and produces a structured research brief with background, key findings, open questions, and recommendations.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `topic` | string | Yes | The research topic to investigate |
| `depth` | string | No | Depth of research |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `brief` | string | Structured research brief in markdown |
| `brief_file` | file_path | Path to the written markdown artifact |

## Steps

- **step_1** — Validate Input and Plan Research (`local`, `general_short`)
- **step_2** — Deep Research on Topic (`llm`, `complex_reasoning`)
- **step_3** — Structure Findings into Brief (`local`, `moderate`)
- **step_4** — Evaluate Research Brief Quality (`critic`, `structured_short`)
- **step_4b** — Improve Research Brief Based on Critic Feedback (`llm`, `complex_reasoning`)
- **step_5** — Write artifact to output (`local`, `general_short`)

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=10, max_improvements=5
- **Max Execution:** 120s
- **Max Cost:** $0.35

## Example Usage

```json
{
  "skill_id": "research-brief",
  "inputs": {
    "topic": "AI agent frameworks for enterprise automation",
    "depth": "standard"
  }
}
```
