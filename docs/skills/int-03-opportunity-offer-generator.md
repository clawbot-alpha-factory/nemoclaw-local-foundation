# Opportunity → Offer Generator

**ID:** `int-03-opportunity-offer-generator` | **Version:** 1.0.0 | **Type:** orchestrator | **Tag:** intelligence

## Description

Takes demand signals → generates offer, pricing, target ICP, funnel. Triggers content creation (cnt-*), outreach (out-*), proposal (biz-01).

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `demand_insights` | string | Yes | Analyzed demand patterns with confidence scores |
| `capabilities` | string | No | Available capabilities to package |

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

- **Output Type:** intelligence_orchestrator_output

## Example Usage

```json
{
  "inputs": {
    "demand_insights": "Pattern 1: High demand for automated proposal generation from discovery calls (confidence 0.87, volume 156 signals). Pattern 2: Growing frustration with manual lead scoring in teams under 20 people (confidence 0.79, volume 89 signals). Pattern 3: Need for cross-platform content scheduling without enterprise pricing (confidence 0.72, volume 67 signals).",
    "capabilities": "AI automation, content generation, outreach automation, analytics"
  }
}
```
