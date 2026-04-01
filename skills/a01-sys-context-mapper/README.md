# a01-sys-context-mapper

**ID:** `a01-sys-context-mapper`
**Version:** 1.0.0
**Type:** executor
**Family:** F01 | **Domain:** A | **Tag:** internal

## Description

Takes a system name, description, and known integrations to produce a structured system context document. Outputs external actors (users, systems, services), data flows between actors and the system (direction, format, frequency), trust boundaries, system capabilities summary, constraints and assumptions, and a C4-style context narrative. All actors and flows are traceable to input description or explicitly marked as inferred.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `system_name` | string | Yes | The name of the system being mapped. |
| `system_description` | string | Yes | A prose description of the system including its purpose, users, and known behavi |
| `known_integrations` | string | No | A list or prose description of known external systems, APIs, or services the sys |
| `domain_context` | string | No | Optional domain or industry context (e.g., "healthcare", "fintech", "e-commerce" |
| `output_detail_level` | string | No | Controls the depth of the generated context document.
 |

## Execution Steps

1. **Parse Inputs and Build Extraction Plan** (local) — Validates all inputs, normalizes the system description and integrations text, and constructs a structured extraction plan that guides the LLM generation step. Identifies whether domain_context and known_integrations are present to adjust inference scope. Produces a normalized input bundle.

2. **Generate Structured System Context Document** (llm) — Generates the full system context document from the normalized input bundle. Extracts and enumerates external actors (human users, external systems, third-party services), maps data flows with direction, format, and frequency, identifies trust boundaries, summarizes system capabilities, lists constraints and assumptions, and writes a C4-style context narrative. Every actor and flow is tagged as either [STATED] (traceable to input) or [INFERRED] (reasoned from context). Inferred items include a brief rationale.

3. **Evaluate Context Document Quality and Traceability** (critic) — Two-layer validation of the generated context document. Deterministic checks: verifies presence of all required sections (actors, data flows, trust boundaries, capabilities, constraints, assumptions, C4 narrative), confirms all actors are tagged [STATED] or [INFERRED], and checks that inferred items include rationale. LLM evaluation: scores completeness, traceability fidelity, flow specificity (direction/format/frequency populated), trust boundary clarity, narrative coherence, and anti-fabrication compliance. Final score is min(deterministic_pass * 10, llm_score).

4. **Improve Context Document Based on Critic Feedback** (llm) — Revises the system context document using the structured feedback from the critic step. Addresses specific deficiencies: adds missing sections, corrects untagged actors or flows, fills in missing direction/format/frequency for data flows, sharpens trust boundary definitions, and improves C4 narrative coherence. Preserves all [STATED] content unchanged and only refines [INFERRED] items or adds missing structure. Returns the improved full document.

5. **Write Final Context Document Artifact** (local) — Deterministic final gate. Confirms the selected output contains all required section headers before writing. Writes the markdown artifact to the configured storage location and returns the artifact path. The runner handles envelope generation automatically.


## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/a01-sys-context-mapper/run.py --force --input system_name "value" --input system_description "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)
