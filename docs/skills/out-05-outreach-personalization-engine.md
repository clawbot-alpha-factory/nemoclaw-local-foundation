# Outreach Personalization Engine

**ID:** `out-05-outreach-personalization-engine` | **Version:** 1.0.0 | **Type:** transformer | **Tag:** outreach

## Description

Takes generic templates + lead data → hyper-personalized messages using company info, recent news, mutual connections.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `template` | string | Yes | Generic outreach template |
| `lead_context` | string | Yes | Lead details: company, role, recent news, connections |

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
- **Max Execution:** 120s
- **Max Cost:** $0.3

## Composability

- **Output Type:** outreach_transformer_output

## Example Usage

```json
{
  "inputs": {
    "template": "Hi [First Name], I noticed [Company] is growing fast in the [Industry] space. Many teams at your stage struggle with [Pain Point]. We recently helped a similar company achieve [Result]. Would a quick 15-minute call to explore if we can deliver similar results for [Company] make sense?",
    "lead_context": "Ryan Mitchell, CEO at GrowthEngine AI (18 employees, San Francisco). Series A raised last month ($4.2M). Hiring for 3 SDR roles (LinkedIn job posts). Company builds analytics dashboards for e-commerce. Recent blog post about scaling sales without adding headcount."
  }
}
```
