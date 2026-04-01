# c07-api-doc-gen

**ID:** `c07-api-doc-gen`
**Version:** 1.0.0
**Type:** executor
**Family:** F07 | **Domain:** C | **Tag:** dual-use

## Description

Generates structured API documentation from an API specification or endpoint descriptions. Produces endpoint reference, authentication guide, error handling reference, rate limiting documentation, quick start guide with curl examples, and SDK usage patterns. All examples are strictly derived from the provided specification — no fabricated endpoints or parameters.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `api_specification` | string | Yes | The API specification, endpoint descriptions, or OpenAPI/Swagger content to docu |
| `target_audience` | string | Yes | The intended audience for the documentation (e.g., "backend developers", "mobile |
| `api_name` | string | Yes | The name of the API being documented (e.g., "Payments API", "User Management API |
| `base_url` | string | No | The base URL of the API (e.g., "https://api.example.com/v1"). Used in curl examp |
| `authentication_type` | string | No | The authentication mechanism used by the API. |
| `include_sdk_patterns` | string | No | Whether to include SDK usage pattern examples in the documentation. |
| `documentation_depth` | string | No | The level of detail for the generated documentation. |

## Execution Steps

1. **Parse Specification and Build Documentation Plan** (local) — Parse and validate the provided API specification. Extract all endpoints, parameters, authentication details, error codes, and rate limiting information. Build a structured documentation plan that maps specification elements to documentation sections. Validate that the specification is non-empty and contains parseable endpoint data.

2. **Generate Comprehensive API Documentation Draft** (llm) — Generate the full API documentation draft using the parsed specification plan from step_1. Produce all required sections: endpoint reference (method, path, description, parameters, request/response examples), authentication guide, error handling reference, rate limiting documentation, quick start guide with curl examples, and SDK usage patterns if requested. All examples must be strictly derived from the provided specification — never fabricate endpoints, parameters, fields, or behaviors not present in the input.

3. **Evaluate Documentation Quality and Specification Fidelity** (critic) — Evaluate the generated API documentation on two layers. First, deterministic checks: verify all required sections are present (endpoint reference, authentication guide, error handling, rate limiting, quick start, SDK patterns if requested), verify curl examples reference the stated base_url, verify no endpoints appear that are absent from the original specification. Second, LLM scoring across quality dimensions: technical accuracy, completeness, clarity for the target audience, example correctness, and structural organization. Produce a combined quality_score (0-10) using min() of deterministic gate and LLM score. Return structured feedback for improvement.

4. **Improve Documentation Based on Critic Feedback** (llm) — Revise and improve the API documentation based on the structured feedback from the critic step. Address all identified issues: missing sections, fabricated examples, unclear parameter descriptions, incorrect curl syntax, or audience-inappropriate language. Ensure all examples remain strictly consistent with the original specification. Do not introduce any endpoints, parameters, or behaviors not present in the input.

5. **Write Final Documentation Artifact to Storage** (local) — Perform a final deterministic gate check on the selected best output, then write the API documentation artifact to the configured storage location. Return the artifact path confirmation to the runner.


## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/c07-api-doc-gen/run.py --force --input api_specification "value" --input target_audience "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)
