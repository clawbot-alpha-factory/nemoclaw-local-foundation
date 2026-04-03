# System Context Mapper

**ID:** `a01-sys-context-mapper` | **Version:** 1.0.0 | **Family:** F01 | **Domain:** A | **Type:** transformer | **Tag:** internal

## Description

Takes a system name, description, and known integrations to produce a structured system context document. Outputs external actors (users, systems, services), data flows between actors and the system (direction, format, frequency), trust boundaries, system capabilities summary, constraints and assumptions, and a C4-style context narrative. All actors and flows are traceable to input description or explicitly marked as inferred.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `system_name` | string | Yes | The name of the system being mapped. |
| `system_description` | string | Yes | A prose description of the system including its purpose, users, and known behaviors. This is the primary source of truth for actor and flow extraction.  |
| `known_integrations` | string | No | A list or prose description of known external systems, APIs, or services the system integrates with. May be empty if unknown.  |
| `domain_context` | string | No | Optional domain or industry context (e.g., "healthcare", "fintech", "e-commerce") to inform trust boundary and constraint inference.  |
| `output_detail_level` | string | No | Controls the depth of the generated context document.  |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | The structured system context document in markdown, including actors, data flows, trust boundaries, capabilities summary, constraints, assumptions, and C4-style context narrative.  |
| `result_file` | file_path | Path to the written markdown artifact on disk. |
| `envelope_file` | file_path | Path to the JSON envelope containing metadata and quality scores. |

## Steps

- **step_1** — Parse Inputs and Build Extraction Plan (`local`, `general_short`)
- **step_2** — Generate Structured System Context Document (`llm`, `premium`)
- **step_3** — Evaluate Context Document Quality and Traceability (`critic`, `moderate`)
- **step_4** — Improve Context Document Based on Critic Feedback (`llm`, `premium`)
- **step_5** — Write Final Context Document Artifact (`local`, `general_short`)

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=10, max_improvements=5
- **Max Execution:** 120s
- **Max Cost:** $0.25

## Declarative Guarantees

- Every external actor in the output is tagged [STATED] or [INFERRED].
- Every [INFERRED] actor or data flow includes a brief rationale sentence.
- {'All required sections are present': 'actors, data flows, trust boundaries, capabilities, constraints, assumptions, C4 narrative.'}
- Data flows include direction, format, and frequency fields where determinable.
- No actor or flow is fabricated without explicit [INFERRED] tagging.
- The C4-style context narrative references only actors and flows enumerated in the document.
- The output is valid markdown renderable without post-processing.

## Composability

- **Output Type:** structured_system_context_document
- **Can Feed Into:** b01-architecture-decision-recorder, c01-api-contract-designer
- **Accepts Input From:** e12-market-research-analyst

## Example Usage

```json
{
  "skill_id": "a01-sys-context-mapper",
  "inputs": {
    "system_name": "NemoClaw Skill Engine",
    "system_description": "A LangGraph-based skill execution engine that routes LLM calls through a 9-alias budget-enforced system, executes 5-step skill pipelines with critic loops, and writes markdown artifacts with JSON envelopes. Integrates with Anthropic, OpenAI, and Google APIs. Uses SQLite for checkpointing."
  }
}
```
