# NDA Generator

**ID:** `k57-nda-generator` | **Version:** 1.0.0 | **Family:** K57 | **Domain:** K | **Type:** generator | **Tag:** legal

## Description

Generate NDA (Non-Disclosure Agreement) documents from party details. Supports mutual and unilateral NDAs with MENA-aware legal terms.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `disclosing_party` | string | Yes | Disclosing party name and details |
| `receiving_party` | string | Yes | Receiving party name and details |
| `jurisdiction` | string | No | Legal jurisdiction for the NDA |
| `nda_type` | string | No | Type of NDA: mutual or unilateral |
| `confidential_scope` | string | No | Scope of confidential information covered |
| `duration_months` | string | No | Duration of NDA in months |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | The generated output |
| `result_file` | file_path | Path to the markdown artifact |
| `envelope_file` | file_path | Path to the JSON envelope for skill chaining |

## Steps

- **step_1** — Parse Parties (`local`, `general_short`)
- **step_2** — Draft NDA (`llm`, `moderate`)
- **step_3** — Legal Review (`critic`, `moderate`)
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
    "disclosing_party": "NemoClaw AI Ltd, Amman Jordan",
    "receiving_party": "Acme Corp, Dubai UAE",
    "jurisdiction": "Jordan",
    "nda_type": "mutual",
    "confidential_scope": "AI automation technology, client data, business strategies",
    "duration_months": "24"
  }
}
```
