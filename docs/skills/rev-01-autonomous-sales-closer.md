# Autonomous Sales Closer

**ID:** `rev-01-autonomous-sales-closer` | **Version:** 1.0.0 | **Type:** executor | **Tag:** revenue

## Description

Multi-step deal progression: qualify, pitch, handle objections, propose, close. Chains 5+ skills per deal. Thread-aware conversation memory. Triggers out-02 Email Executor, WhatsApp bridge, calendar hooks.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `lead_data` | string | Yes | Lead information: name, company, role, pain points, engagement history |
| `offer_context` | string | No | What we're selling |

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
    "lead_data": "Lead: James Chen, CEO at DataPulse (18 employees, analytics SaaS, San Francisco). Raised Series A ($4.2M) last month. Pain points: scaling sales outreach without hiring SDRs, current manual process handles only 20 prospects/week. Engagement: attended webinar, downloaded ROI calculator, booked and completed demo call. Demo feedback: impressed with automation capabilities but concerned about integration with their custom CRM. Budget authority: confirmed. Timeline: wants to decide within 2 weeks.",
    "offer_context": "NemoClaw AI automation services"
  }
}
```
