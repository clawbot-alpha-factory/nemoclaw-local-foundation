# Contract Template Engine

**ID:** `k58-contract-template-engine` | **Version:** 1.0.0 | **Family:** K58 | **Domain:** K | **Type:** generator | **Tag:** legal

## Description

Generate MSA (Master Service Agreement) and SLA (Service Level Agreement) templates. Produces professional contract documents with MENA-aware legal terms.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `contract_type` | string | Yes | Type of contract: MSA, SLA, or SOW |
| `provider_info` | string | Yes | Service provider name, location, and description |
| `client_info` | string | Yes | Client name, location, and business type |
| `service_description` | string | Yes | Description of services to be provided |
| `jurisdiction` | string | No | Legal jurisdiction |
| `payment_terms` | string | No | Payment terms and billing schedule |
| `sla_metrics` | string | No | SLA metrics and targets (for SLA type contracts) |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | The generated output |
| `result_file` | file_path | Path to the markdown artifact |
| `envelope_file` | file_path | Path to the JSON envelope for skill chaining |

## Steps

- **step_1** — Parse Contract Request (`local`, `general_short`)
- **step_2** — Draft Contract (`llm`, `moderate`)
- **step_3** — Legal Compliance Check (`critic`, `moderate`)
- **step_4** — Write Artifact (`local`, `general_short`)

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=N/A, max_improvements=N/A
- **Max Execution:** 120s
- **Max Cost:** $0.35

## Composability

- **Output Type:** legal_generator_output

## Example Usage

```json
{
  "inputs": {
    "contract_type": "MSA",
    "provider_info": "NemoClaw AI Ltd, Amman Jordan, AI automation services",
    "client_info": "Acme Corp, Dubai UAE, marketing agency",
    "service_description": "AI-powered marketing automation, content generation, and sales pipeline management",
    "jurisdiction": "Jordan",
    "payment_terms": "Net 30, monthly billing"
  }
}
```
