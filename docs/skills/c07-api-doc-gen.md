# API Documentation Generator

**ID:** `c07-api-doc-gen` | **Version:** 1.0.0 | **Family:** F07 | **Domain:** C | **Type:** executor | **Tag:** dual-use

## Description

Generates structured API documentation from an API specification or endpoint descriptions. Produces endpoint reference, authentication guide, error handling reference, rate limiting documentation, quick start guide with curl examples, and SDK usage patterns. All examples are strictly derived from the provided specification — no fabricated endpoints or parameters.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `api_specification` | string | Yes | The API specification, endpoint descriptions, or OpenAPI/Swagger content to document. May be raw text, JSON, YAML, or structured endpoint descriptions.  |
| `target_audience` | string | Yes | The intended audience for the documentation (e.g., "backend developers", "mobile developers", "third-party integrators", "internal teams").  |
| `api_name` | string | Yes | The name of the API being documented (e.g., "Payments API", "User Management API"). |
| `base_url` | string | No | The base URL of the API (e.g., "https://api.example.com/v1"). Used in curl examples. |
| `authentication_type` | string | No | The authentication mechanism used by the API. |
| `include_sdk_patterns` | string | No | Whether to include SDK usage pattern examples in the documentation. |
| `documentation_depth` | string | No | The level of detail for the generated documentation. |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | The complete structured API documentation in markdown format. |
| `result_file` | file_path | Path to the written API documentation artifact file. |
| `envelope_file` | file_path | Path to the JSON envelope containing metadata and quality scores. |

## Steps

- **step_1** — Parse Specification and Build Documentation Plan (`local`, `general_short`)
- **step_2** — Generate Comprehensive API Documentation Draft (`llm`, `premium`)
- **step_3** — Evaluate Documentation Quality and Specification Fidelity (`critic`, `moderate`)
- **step_4** — Improve Documentation Based on Critic Feedback (`llm`, `premium`)
- **step_5** — Write Final Documentation Artifact to Storage (`local`, `general_short`)

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=10, max_improvements=5
- **Max Execution:** 180s
- **Max Cost:** $0.8

## Declarative Guarantees

- All documented endpoints, parameters, and fields are derived exclusively from the provided API specification.
- No examples, endpoints, or behaviors are fabricated beyond what is stated in the input.
- Curl examples reference the stated base_url and use the specified authentication_type.
- Documentation includes all required sections — endpoint reference, authentication guide, error handling, rate limiting, quick start, and SDK patterns when requested.
- Output is structured markdown suitable for developer portals or internal wikis.
- Quality score of 7 or higher is required before artifact is written.

## Composability

- **Output Type:** structured_api_documentation_markdown

## Example Usage

```json
{
  "skill_id": "c07-api-doc-gen",
  "inputs": {
    "api_specification": "REST API with endpoints: POST /skills/run (submit execution, body: skill_id + inputs), GET /skills/status/{id} (check status, returns pending/running/complete/failed), GET /skills/result/{id} (get result artifact), GET /skills (list available skills). Auth via X-API-Key header. Returns JSON. Rate limited to 60 requests per minute per key.",
    "target_audience": "developer",
    "api_name": "NemoClaw Skill Execution API"
  }
}
```
