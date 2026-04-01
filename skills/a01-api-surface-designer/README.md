# a01-api-surface-designer

**ID:** `a01-api-surface-designer`
**Version:** 1.0.0
**Type:** executor
**Family:** F01 | **Domain:** A | **Tag:** internal

## Description

Designs a structured API surface from a service description, target consumers, and design constraints. Produces an endpoint inventory, request/response schemas, authentication model, error taxonomy, rate limiting and pagination strategy, versioning approach, and backwards compatibility notes. All endpoints are traceable to stated service capabilities.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `service_description` | string | Yes | A detailed description of the service, its capabilities, data entities, and busi |
| `target_consumers` | string | Yes | Description of the intended API consumers (e.g., mobile clients, third-party par |
| `design_constraints` | string | No | Optional constraints such as protocol preference (REST/GraphQL), authentication  |
| `api_style` | string | No | Preferred API style. Defaults to REST if not specified. |
| `output_format` | string | No | Preferred output format for the API specification document. |

## Execution Steps

1. **Parse Service Capabilities and Build Design Plan** (local) — Validates all inputs, extracts the explicit service capabilities from the service description, maps them to candidate endpoints, and builds a structured generation plan including api_style, consumer profile, and constraint summary. Ensures the anti-fabrication contract is anchored before generation begins.

2. **Generate Structured API Surface Specification** (llm) — Generates the full API surface specification grounded in the service capabilities extracted in step_1. Produces: endpoint inventory (method, path, purpose), request and response schemas with field types, authentication and authorization model, error response taxonomy, rate limiting and pagination strategy, versioning approach, and backwards compatibility notes. Every endpoint must cite the service capability it serves. Uses the api_style and design_constraints from step_1_output.

3. **Evaluate API Specification Quality and Traceability** (critic) — Two-layer validation of the generated API specification. Deterministic layer checks: presence of endpoint inventory, schema definitions, authentication model, error taxonomy, rate limiting section, versioning section, and backwards compatibility notes. LLM layer scores: endpoint traceability to service capabilities (anti-fabrication), schema completeness, error taxonomy coverage, design consistency, and consumer-appropriateness. Combines scores with min() and emits a quality_score 0-10.

4. **Improve API Specification Based on Critic Feedback** (llm) — Revises the API specification using the structured feedback from the critic step. Addresses identified gaps in traceability, schema completeness, error taxonomy, or design consistency. Ensures all endpoints remain anchored to stated service capabilities and no fabricated endpoints are introduced during improvement.

5. **Write Final API Specification Artifact** (local) — Deterministic final gate that selects the highest-quality API specification from the critic loop candidates, performs a final structural check, and writes the artifact to the designated output path. Returns the artifact path confirmation.


## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/a01-api-surface-designer/run.py --force --input service_description "value" --input target_consumers "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)
