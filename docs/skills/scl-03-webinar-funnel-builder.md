# Webinar Funnel Builder

**ID:** `scl-03-webinar-funnel-builder` | **Version:** 1.0.0 | **Type:** orchestrator | **Tag:** scale

## Description

Full funnel: landing page copy → registration sequence → reminder emails → webinar script → follow-up sequence → offer.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `webinar_topic` | string | Yes | Webinar topic and value proposition |
| `target_audience` | string | Yes | Who should attend |

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

- **Output Type:** scale_orchestrator_output

## Example Usage

```json
{
  "inputs": {
    "webinar_topic": "From Manual to Autonomous: How to Build an AI-Powered Sales Pipeline in 30 Days Without Writing Code. Live demonstration of automating lead scoring, outreach personalization, and follow-up sequences.",
    "target_audience": "B2B SaaS founders and operations leaders at companies with 10-200 employees who are spending more than 15 hours per week on manual sales processes and want to scale without hiring additional SDRs"
  }
}
```
