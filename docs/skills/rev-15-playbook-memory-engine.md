# Playbook Memory Engine

**ID:** `rev-15-playbook-memory-engine` | **Version:** 1.0.0 | **Type:** analyzer | **Tag:** revenue

## Description

Stores winning campaigns, failed experiments, best offers, top channels per niche. System stops starting from zero. Persists to ~/.nemoclaw/playbooks.json.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `campaign_results` | string | Yes | Recent campaign/experiment results with outcomes |
| `existing_playbooks` | string | No | Current playbook entries for context |

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
    "campaign_results": "Experiment 1: Subject line A/B test on cold emails. Winner: company-specific references (Variant B), 34 percent open rate vs 21 percent for generic (Variant A). Sample: 200 per variant. Experiment 2: LinkedIn outreach timing. Winner: Tuesday 9am local time, 18 percent accept rate vs 11 percent for Thursday afternoon. Experiment 3: Pricing page layout. Winner: single-plan with enterprise CTA, 3.2 percent conversion vs 1.8 percent for 3-tier pricing. Campaign: Referral program launch generated 4 qualified leads from 12 referrals in first week.",
    "existing_playbooks": "Playbook entry 1: Cold email works best with 3-touch sequence over 10 days. Playbook entry 2: MENA prospects prefer WhatsApp follow-up over email."
  }
}
```
