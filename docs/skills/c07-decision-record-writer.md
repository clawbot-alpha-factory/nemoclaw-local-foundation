# Decision Record Writer

**ID:** `c07-decision-record-writer` | **Version:** 1.0.0 | **Family:** F07 | **Domain:** C | **Type:** executor | **Tag:** internal

## Description

Produces a structured Architecture Decision Record (ADR) following the Michael Nygard template. Takes a decision title, context, and options considered, then generates a complete ADR with status, context and problem statement, decision drivers, options with pros and cons, chosen option with justification, logically derived consequences, compliance notes, and review date. Anti-fabrication enforcement ensures consequences are grounded in the chosen option.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `decision_title` | string | Yes | The concise title of the architectural decision being recorded. |
| `decision_context` | string | Yes | The context surrounding the decision — the forces at play, the problem being solved, and any relevant background information.  |
| `options_considered` | list | Yes | A list of options that were considered. Each entry should name the option and provide enough detail for pros/cons analysis.  |
| `chosen_option` | string | Yes | The name of the option that was selected as the decision. |
| `decision_drivers` | list | No | Key factors, constraints, or goals that drove the decision. If not provided, the skill will infer drivers from the context.  |
| `status` | string | No | The current status of the ADR. |
| `compliance_domains` | list | No | Compliance or regulatory domains relevant to this decision (e.g., GDPR, SOC2, HIPAA). If empty, the skill will note no specific compliance implications.  |
| `review_date` | string | No | ISO 8601 date string for when this ADR should be reviewed (e.g., "2027-03-27"). If not provided, defaults to one year from creation.  |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | The complete ADR document in structured markdown following the Michael Nygard template. |
| `result_file` | file_path | Path to the written ADR markdown artifact file. |
| `envelope_file` | file_path | Path to the JSON envelope containing metadata and quality scores. |

## Steps

- **step_1** — Parse Inputs and Build ADR Generation Plan (`local`, `general_short`)
- **step_2** — Generate Complete ADR Document Draft (`llm`, `premium`)
- **step_3** — Evaluate ADR Quality and Structural Completeness (`critic`, `moderate`)
- **step_4** — Improve ADR Based on Critic Feedback (`llm`, `premium`)
- **step_5** — Write Final ADR Artifact to Storage (`local`, `general_short`)

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=10, max_improvements=5
- **Max Execution:** 120s
- **Max Cost:** $0.25

## Declarative Guarantees

- All ADRs follow the Michael Nygard template with every required section present.
- Consequences are logically derived from the chosen option — no fabricated outcomes.
- Options considered include explicit pros and cons for each alternative.
- Decision drivers are either provided by the caller or inferred from the context.
- Compliance notes reflect only the domains specified in the input or note their absence.
- Review date is always present — defaulting to one year from creation if not supplied.
- The chosen option justification references the decision drivers explicitly.

## Composability

- **Output Type:** architecture_decision_record
- **Can Feed Into:** d11-copywriting-specialist

## Example Usage

```json
{
  "skill_id": "c07-decision-record-writer",
  "inputs": {
    "decision_title": "Route all LLM calls through a budget-enforced proxy",
    "decision_context": "Need cost control across 3 providers (Anthropic, OpenAI, Google) with per-provider spending limits. Direct API calls have no cost guardrails. Budget overruns consumed 15 dollars in one session due to Opus pricing underestimation.",
    "options_considered": "Direct API calls with manual tracking, Centralized budget-enforced proxy, Per-skill cost limits hardcoded in each file",
    "chosen_option": "Option B: Centralized budget-enforced proxy"
  }
}
```
