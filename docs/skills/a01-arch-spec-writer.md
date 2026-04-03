# Architecture Specification Writer

**ID:** `a01-arch-spec-writer` | **Version:** 1.0.0 | **Family:** F01 | **Domain:** A | **Type:** executor | **Tag:** internal

## Description

Takes a subsystem concept, boundaries, and integration context, produces a complete architecture specification with purpose, scope, layer breakdown, component descriptions with responsibilities and interfaces, data/control flow with directional steps referencing components, dependency map with direction and interaction type, risk analysis, extension points, and assumptions. Works only from provided input — states assumptions explicitly when information is missing.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `subsystem_name` | string | Yes | Name of the subsystem being specified |
| `subsystem_concept` | string | Yes | What the subsystem does, why it exists, what problem it solves |
| `boundaries` | string | No | What is in scope vs out of scope, upstream/downstream systems |
| `integration_context` | string | No | How this subsystem connects to existing systems, APIs, data stores |
| `constraints` | string | No | Known constraints: performance, cost, compatibility, tech stack requirements |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | The complete architecture specification in markdown |
| `result_file` | file_path | Path to the markdown artifact |
| `envelope_file` | file_path | Path to the JSON envelope |

## Steps

- **step_1** — Parse subsystem concept and identify architectural concerns (`local`, `general_short`)
- **step_2** — Generate complete architecture specification (`llm`, `moderate`)
- **step_3** — Evaluate specification completeness and structural rigor (`critic`, `moderate`)
- **step_4** — Strengthen specification based on critic feedback (`llm`, `moderate`)
- **step_5** — Validate final spec and write artifact (`local`, `general_short`)

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=10, max_improvements=5
- **Max Execution:** 90s
- **Max Cost:** $0.1

## Declarative Guarantees

- Every named component has an explicit responsibility and interface/contract description
- Layer boundaries are explicit — what each layer owns and does not own
- Data/control flow is directional with numbered steps referencing specific components
- Dependencies specify direction (depends on / provides to) and interaction type (API, DB, file, etc.)
- Risks are specific to this subsystem, not generic architecture risks
- Extension points identify what can change vs what is locked
- Does not introduce systems or technologies not implied by the input
- Missing information is stated as explicit assumptions, not silently filled

## Composability

- **Output Type:** architecture_specification
- **Can Feed Into:** b05-feature-impl-writer, c07-setup-guide-writer, c07-runbook-author
- **Accepts Input From:** g26-skill-spec-writer

## Example Usage

```json
{
  "skill_id": "a01-arch-spec-writer",
  "inputs": {
    "subsystem_name": "Event Processing Pipeline",
    "subsystem_concept": "A real-time event processing system that ingests user clickstream data from web and mobile apps, processes events through a rules engine, and triggers personalized notifications via email, push, and SMS channels. Must handle 10000 events per second with sub-500ms latency.",
    "constraints": "Horizontal scalability, fault tolerance with no data loss"
  }
}
```
