# API Surface Designer

**ID:** `a01-api-surface-designer` | **Version:** 1.0.0 | **Family:** F01 | **Domain:** A | **Type:** executor | **Tag:** internal

## Description

Designs a structured API surface from a service description, target consumers, and design constraints. Produces an endpoint inventory, request/response schemas, authentication model, error taxonomy, rate limiting and pagination strategy, versioning approach, and backwards compatibility notes. All endpoints are traceable to stated service capabilities.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `service_description` | string | Yes | A detailed description of the service, its capabilities, data entities, and business operations it exposes. All designed endpoints must be traceable to this description.  |
| `target_consumers` | string | Yes | Description of the intended API consumers (e.g., mobile clients, third-party partners, internal microservices). Influences authentication model, versioning, and pagination design.  |
| `design_constraints` | string | No | Optional constraints such as protocol preference (REST/GraphQL), authentication requirements, rate limit tiers, pagination style, or backwards compatibility requirements.  |
| `api_style` | string | No | Preferred API style. Defaults to REST if not specified. |
| `output_format` | string | No | Preferred output format for the API specification document. |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | The complete API surface specification including endpoint inventory, schemas, authentication model, error taxonomy, rate limiting, pagination, versioning, and backwards compatibility notes.  |
| `result_file` | file_path | Path to the written API specification artifact file. |
| `envelope_file` | file_path | Path to the execution envelope JSON file. |

## Steps

- **step_1** — Parse Service Capabilities and Build Design Plan (`local`, `general_short`)
- **step_2** — Generate Structured API Surface Specification (`llm`, `premium`)
- **step_3** — Evaluate API Specification Quality and Traceability (`critic`, `moderate`)
- **step_4** — Improve API Specification Based on Critic Feedback (`llm`, `premium`)
- **step_5** — Write Final API Specification Artifact (`local`, `general_short`)

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=10, max_improvements=5
- **Max Execution:** 180s
- **Max Cost:** $0.8

## Declarative Guarantees

- All endpoints in the specification are traceable to explicitly stated service capabilities.
- No endpoints are fabricated beyond what the service description supports.
- The specification includes endpoint inventory, request/response schemas, authentication model, error taxonomy, rate limiting, pagination strategy, versioning approach, and backwards compatibility notes.
- Schema field types are explicitly declared for all request and response objects.
- The error response taxonomy covers standard HTTP error classes relevant to the service.
- The versioning approach addresses backwards compatibility explicitly.
- The specification is appropriate for the stated target consumers.

## Composability

- **Output Type:** structured_api_surface_specification
- **Can Feed Into:** b02-openapi-schema-generator, c05-sdk-documentation-writer
- **Accepts Input From:** e12-market-research-analyst, f03-service-capability-mapper

## Example Usage

```json
{
  "skill_id": "a01-api-surface-designer",
  "inputs": {
    "service_description": "A REST API for managing AI skill executions. Supports submitting execution requests, checking status, retrieving results, and managing skill configurations. Async execution with webhook callbacks. Must authenticate via API keys and enforce per-client rate limits.",
    "target_consumers": "External developers building integrations with the NemoClaw skill system using Python or JavaScript"
  }
}
```
