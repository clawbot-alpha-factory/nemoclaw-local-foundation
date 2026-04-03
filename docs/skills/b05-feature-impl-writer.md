# Feature Implementation Writer

**ID:** `b05-feature-impl-writer` | **Version:** 1.0.0 | **Family:** F05 | **Domain:** B | **Type:** executor | **Tag:** dual-use

## Description

Takes a feature specification, language, and integration context, produces complete first-draft implementation code intended to be runnable after human review, integration, and testing. Includes module structure, function/class implementations, conditional error handling, inline documentation, and a separate test stub. Does NOT execute, compile, or test the code.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `feature_spec` | string | Yes | What to build: feature name, purpose, behavior, acceptance criteria |
| `language` | string | Yes | Target language or framework |
| `integration_context` | string | No | How this code connects to existing systems — imports, APIs, data formats, existing modules |
| `constraints` | string | No | Performance, security, compatibility, style requirements |
| `code_style` | string | No | minimal (lean, no comments), documented (inline docs + docstrings), defensive (heavy error handling + validation) |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | The complete implementation code in markdown with code blocks |
| `result_file` | file_path | Path to the markdown artifact |
| `envelope_file` | file_path | Path to the JSON envelope |

## Steps

- **step_1** — Parse feature spec and build structured implementation plan (`local`, `general_short`)
- **step_2** — Generate complete implementation with error handling and documentation (`llm`, `complex_reasoning`)
- **step_3** — Evaluate code quality and specification compliance (`critic`, `moderate`)
- **step_4** — Strengthen implementation based on critic feedback (`llm`, `complex_reasoning`)
- **step_5** — Validate final implementation and write artifact (`local`, `general_short`)

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=10, max_improvements=5
- **Max Execution:** 120s
- **Max Cost:** $0.15

## Declarative Guarantees

- Every planned implementation unit from step_1 has a corresponding definition in the code
- Error handling covers external-input, parsing, I/O, and integration paths — not ceremonial wrappers
- Test stub covers at least the primary function/class with meaningful assertions
- No dependencies, imports, or frameworks not present in feature_spec, language, or integration_context
- Code style matches the requested level (minimal, documented, defensive)
- No fake completeness patterns (// implementation here, pass in critical path, empty catch, return null placeholder)
- Does not claim code is tested, verified, or production-ready

## Composability

- **Output Type:** implementation_code
- **Can Feed Into:** b05-script-automator, c07-setup-guide-writer
- **Accepts Input From:** f09-product-req-writer, a01-arch-spec-writer

## Example Usage

```json
{
  "skill_id": "b05-feature-impl-writer",
  "inputs": {
    "feature_spec": "Add a rate limiting middleware to the Express.js API that limits each authenticated user to 100 requests per minute using a sliding window algorithm. Must support Redis-backed distributed counting for multi-instance deployments.",
    "language": "typescript",
    "integration_context": "Express.js REST API with Redis cache",
    "implementation_scope": "standard"
  }
}
```
