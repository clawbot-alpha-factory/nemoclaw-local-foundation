#!/usr/bin/env python3
"""
Skill ID: a01-api-surface-designer
Version: 1.0.0
Family: F01
Domain: A
Tag: internal
Type: executor
Schema: 2
Runner: >=4.0.0
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone



# ── LLM Helpers (routed through lib/routing.py — L-003 compliant) ────────────
def call_openai(messages, model=None, max_tokens=6000):
    from lib.routing import call_llm, resolve_alias, get_api_key
    if model is None:
        _, model, _ = resolve_alias("general_short")
    return call_llm(messages, task_class="general_short", max_tokens=max_tokens)

def call_anthropic(messages, model=None, max_tokens=6000):
    from lib.routing import call_llm, resolve_alias
    if model is None:
        _, model, _ = resolve_alias("complex_reasoning")
    return call_llm(messages, task_class="complex_reasoning", max_tokens=max_tokens)

def call_google(messages, model=None, max_tokens=6000):
    from lib.routing import call_llm, resolve_alias
    if model is None:
        _, model, _ = resolve_alias("moderate")
    return call_llm(messages, task_class="moderate", max_tokens=max_tokens)

def call_resolved(messages, context, max_tokens=6000):
    from lib.routing import call_llm
    return call_llm(messages, task_class="moderate", max_tokens=max_tokens)


def check_structural_sections(text):
    """Check presence of required API spec sections. Returns (score 0-10, missing list)."""
    required_sections = [
        ("endpoint inventory", ["endpoint inventory", "endpoints", "endpoint list"]),
        ("request schema", ["request schema", "request body", "request parameters", "schemas"]),
        ("response schema", ["response schema", "response body", "response format"]),
        ("authentication", ["authentication", "auth model", "security"]),
        ("error taxonomy", ["error taxonomy", "error codes", "errors", "error handling"]),
        ("rate limiting", ["rate limit", "rate-limit", "throttling"]),
        ("pagination", ["pagination", "paging", "page size"]),
        ("versioning", ["versioning", "version strategy", "api version"]),
        ("backwards compatibility", ["backwards compat", "backward compat", "breaking change"]),
        ("traceability", ["traceable", "traceability", "capability", "service capability"]),
    ]
    text_lower = text.lower()
    found = 0
    missing = []
    for section_name, keywords in required_sections:
        if any(kw in text_lower for kw in keywords):
            found += 1
        else:
            missing.append(section_name)
    score = round((found / len(required_sections)) * 10)
    return score, missing


def step_1_local(inputs, context):
    """Parse Service Capabilities and Build Design Plan."""
    service_description = inputs.get("service_description", "")
    target_consumers = inputs.get("target_consumers", "")
    design_constraints = inputs.get("design_constraints", "")
    api_style = inputs.get("api_style", "REST")
    output_format = inputs.get("output_format", "markdown")

    if not service_description or len(service_description.strip()) < 100:
        return None, "service_description must be at least 100 characters."
    if not target_consumers or len(target_consumers.strip()) < 20:
        return None, "target_consumers must be at least 20 characters."
    if len(service_description) > 8000:
        return None, "service_description exceeds maximum length of 8000 characters."
    if len(target_consumers) > 2000:
        return None, "target_consumers exceeds maximum length of 2000 characters."
    if design_constraints and len(design_constraints) > 2000:
        return None, "design_constraints exceeds maximum length of 2000 characters."

    allowed_styles = ["REST", "GraphQL", "gRPC", "REST+GraphQL"]
    if api_style not in allowed_styles:
        api_style = "REST"
    allowed_formats = ["markdown", "yaml", "json"]
    if output_format not in allowed_formats:
        output_format = "markdown"

    action_verbs = [
        "create", "read", "update", "delete", "list", "search", "upload",
        "download", "send", "receive", "process", "validate", "authenticate",
        "authorize", "notify", "subscribe", "publish", "manage", "retrieve",
        "submit", "approve", "reject", "cancel", "schedule", "export", "import",
    ]
    desc_lower = service_description.lower()
    capability_keywords = [v for v in action_verbs if v in desc_lower]

    consumer_lower = target_consumers.lower()
    consumer_profile = {
        "has_mobile": any(w in consumer_lower for w in ["mobile", "ios", "android", "app"]),
        "has_partners": any(w in consumer_lower for w in ["partner", "third-party", "external", "client"]),
        "has_internal": any(w in consumer_lower for w in ["internal", "microservice", "service", "backend"]),
        "has_web": any(w in consumer_lower for w in ["web", "browser", "frontend", "spa"]),
    }

    constraints_lower = (design_constraints or "").lower()
    constraint_signals = {
        "auth_mentioned": any(w in constraints_lower for w in ["oauth", "jwt", "api key", "bearer", "auth"]),
        "rate_limit_mentioned": any(w in constraints_lower for w in ["rate limit", "throttle", "quota"]),
        "pagination_mentioned": any(w in constraints_lower for w in ["pagination", "cursor", "offset", "page"]),
        "versioning_mentioned": any(w in constraints_lower for w in ["version", "v1", "v2", "semver"]),
        "graphql_preferred": "graphql" in constraints_lower,
        "rest_preferred": "rest" in constraints_lower,
    }

    plan = {
        "api_style": api_style,
        "output_format": output_format,
        "consumer_profile": consumer_profile,
        "constraint_signals": constraint_signals,
        "capability_keywords_found": capability_keywords,
        "service_description_length": len(service_description),
        "has_design_constraints": bool(design_constraints and design_constraints.strip()),
        "generation_plan": {
            "must_include": [
                "endpoint_inventory",
                "request_response_schemas",
                "authentication_model",
                "error_taxonomy",
                "rate_limiting_strategy",
                "pagination_strategy",
                "versioning_approach",
                "backwards_compatibility_notes",
                "traceability_to_capabilities",
            ],
            "anti_fabrication_contract": (
                "All endpoints must be traceable to explicit capabilities stated in the "
                "service_description. No endpoints may be invented beyond what the service "
                "description supports."
            ),
        },
    }

    return {"output": plan}, None


def step_2_llm(inputs, context):
    """Generate Structured API Surface Specification."""
    step_1_output = context.get("step_1_output", {})
    service_description = inputs.get("service_description", "")
    target_consumers = inputs.get("target_consumers", "")
    design_constraints = inputs.get("design_constraints", "")
    api_style = step_1_output.get("api_style", inputs.get("api_style", "REST"))
    output_format = step_1_output.get("output_format", inputs.get("output_format", "markdown"))
    consumer_profile = step_1_output.get("consumer_profile", {})
    generation_plan = step_1_output.get("generation_plan", {})
    anti_fabrication = generation_plan.get(
        "anti_fabrication_contract",
        "All endpoints must be traceable to explicit capabilities in the service description."
    )
    capability_keywords = step_1_output.get("capability_keywords_found", [])

    system_prompt = (
        "You are a senior API architect with deep expertise in RESTful and GraphQL design, "
        "OpenAPI specification, authentication patterns, and developer experience. You produce "
        "precise, traceable API surfaces grounded strictly in the stated service capabilities.\n\n"
        "ANTI-FABRICATION CONTRACT: " + anti_fabrication + "\n\n"
        "You must produce a complete, structured API surface specification covering all required "
        "sections. Every endpoint must cite the specific service capability it implements. "
        "Use clear markdown headings (## for top-level sections). Be exhaustive and precise."
    )

    consumer_context = []
    if consumer_profile.get("has_mobile"):
        consumer_context.append("mobile clients (optimize for bandwidth, use pagination)")
    if consumer_profile.get("has_partners"):
        consumer_context.append("third-party partners (strong auth, versioning, rate limits)")
    if consumer_profile.get("has_internal"):
        consumer_context.append("internal microservices (service-to-service auth, low latency)")
    if consumer_profile.get("has_web"):
        consumer_context.append("web/browser clients (CORS, session management)")
    consumer_str = ", ".join(consumer_context) if consumer_context else target_consumers

    constraints_note = ""
    if design_constraints and design_constraints.strip():
        constraints_note = f"\n\nDESIGN CONSTRAINTS:\n{design_constraints}"

    capability_note = ""
    if capability_keywords:
        capability_note = f"\n\nDETECTED CAPABILITY SIGNALS: {', '.join(capability_keywords)}"

    format_instruction = ""
    if output_format == "yaml":
        format_instruction = "\n\nOutput the schemas and endpoint definitions in YAML format where applicable."
    elif output_format == "json":
        format_instruction = "\n\nOutput the schemas and endpoint definitions in JSON format where applicable."

    user_prompt = f"""Design a complete API surface specification for the following service.

API STYLE: {api_style}
OUTPUT FORMAT: {output_format}

SERVICE DESCRIPTION:
{service_description}

TARGET CONSUMERS: {consumer_str}
{constraints_note}{capability_note}{format_instruction}

Produce ALL of the following sections. Each section heading must use ## (H2 markdown):

## Endpoint Inventory
For each endpoint provide: HTTP Method, Path, Purpose, and the exact Service Capability from the description it implements.
Format as a structured table with columns: Method | Path | Purpose | Service Capability.
Every endpoint MUST cite its source capability verbatim or by close paraphrase.

## Request and Response Schemas
For each endpoint, define:
- Request parameters (path, query, header, body) with field names, types, required/optional, and descriptions
- Response schema with all field names, types, and descriptions
- All HTTP status codes returned (success and error)
Use structured sub-sections per endpoint.

## Authentication Model
Define the complete authentication strategy:
- Auth mechanism (e.g., OAuth 2.0, API Key, JWT Bearer)
- Token format and lifetime
- Scopes or permissions model
- How each consumer type obtains and refreshes credentials
- Headers required on each request

## Error Taxonomy
Define a complete error taxonomy:
- Standard error response envelope with fields: error_code, message, details, request_id, timestamp
- Error code categories (4xx client errors, 5xx server errors)
- Minimum 8 specific error codes relevant to this service's operations, each with: code, HTTP status, description, and resolution guidance

## Rate Limiting and Pagination Strategy
Rate Limiting:
- Consumer tiers and their limits (requests/minute and requests/hour)
- Response headers returned (X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset, Retry-After)
- Behavior when limit is exceeded (429 response, backoff guidance)

Pagination:
- Pagination style (cursor-based, offset-based, or keyset)
- Request parameters (page, page_size or cursor, limit)
- Response envelope fields (data, total, next_cursor or next_page, has_more)

## Versioning Approach
- Versioning strategy (URL path prefix e.g. /v1/, header, or query param)
- Version lifecycle policy: deprecation notice period, sunset header usage
- Classification of breaking vs non-breaking changes with examples

## Backwards Compatibility Notes
- Exhaustive list of changes that constitute breaking changes
- Commitment to additive-only non-breaking changes
- Migration path guidance for consumers when breaking changes are unavoidable
- Deprecation communication process

## Traceability Matrix
A table mapping every endpoint to the specific service capability from the service description:
| Endpoint | Method | Service Capability | Description Source |

Be precise, complete, and grounded. Do not invent capabilities not stated in the service description.
Every section must be present and substantive."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    content, error = call_resolved(messages, context, max_tokens=8000)
    if error:
        content, error = call_openai(messages, max_tokens=8000)
    if error:
        return None, error

    return {"output": content}, None


def step_3_critic(inputs, context):
    """Evaluate API Specification Quality and Traceability."""
    generated_api_spec = context.get("improved_api_spec", context.get("generated_api_spec", ""))
    step_1_output = context.get("step_1_output", {})
    service_description = inputs.get("service_description", "")

    if not generated_api_spec:
        return None, "No generated API specification found in context."

    structural_score, missing_sections = check_structural_sections(generated_api_spec)

    system_prompt = (
        "You are a senior API architect and technical reviewer. You evaluate API surface "
        "specifications for completeness, correctness, traceability, and design quality. "
        "You return structured JSON scores only — no prose outside the JSON object."
    )

    capability_keywords = step_1_output.get("capability_keywords_found", [])
    api_style = step_1_output.get("api_style", "REST")

    user_prompt = f"""Evaluate the following API surface specification against the service description.

SERVICE DESCRIPTION:
{service_description}

API STYLE: {api_style}
CAPABILITY SIGNALS DETECTED: {', '.join(capability_keywords) if capability_keywords else 'none detected'}

STRUCTURAL CHECK RESULTS:
- Structural score (0-10): {structural_score}
- Missing sections: {', '.join(missing_sections) if missing_sections else 'none'}

API SPECIFICATION TO EVALUATE:
{generated_api_spec}

Score the specification on these dimensions (each 0-10):

1. traceability_score (0-10): Are all endpoints explicitly traced to service capabilities stated in the description? Deduct heavily for fabricated endpoints not supported by the service description. 10 = perfect traceability, 0 = no traceability.

2. schema_completeness_score (0-10): Are request/response schemas complete with field names, types, required/optional markers, and descriptions for every endpoint? 10 = all schemas complete, 0 = schemas missing or skeletal.

3. error_taxonomy_score (0-10): Is the error taxonomy comprehensive with a standard envelope (error_code, message, details, request_id), categorized codes, and at least 8 service-specific error codes with resolution guidance? 10 = excellent, 0 = missing or trivial.

4. design_consistency_score (0-10): Is the API style consistent, naming conventions followed (snake_case or camelCase uniformly), HTTP methods used correctly, and design patterns applied uniformly? 10 = fully consistent, 0 = inconsistent throughout.

Also provide:
- fabricated_endpoints: list of endpoint paths that appear invented beyond the service description (empty list if none)
- schema_gaps: list of endpoint paths missing adequate schema definitions
- critical_issues: list of critical problems that must be fixed (be specific)
- improvement_suggestions: list of specific, actionable improvements

Return ONLY valid JSON in this exact format:
{{
  "traceability_score": <0-10>,
  "schema_completeness_score": <0-10>,
  "error_taxonomy_score": <0-10>,
  "design_consistency_score": <0-10>,
  "fabricated_endpoints": [],
  "schema_gaps": [],
  "critical_issues": [],
  "improvement_suggestions": []
}}"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    content, error = call_resolved(messages, context, max_tokens=4000)
    if error:
        content, error = call_openai(messages, max_tokens=4000)
    if error:
        return None, error

    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
        cleaned = re.sub(r'\s*```$', '', cleaned)

    try:
        scores = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if match:
            try:
                scores = json.loads(match.group(0))
            except json.JSONDecodeError:
                return None, f"Failed to parse critic JSON response: {cleaned[:200]}"
        else:
            return None, f"No JSON object found in critic response: {cleaned[:200]}"

    traceability = scores.get("traceability_score", 5)
    schema_completeness = scores.get("schema_completeness_score", 5)
    error_taxonomy = scores.get("error_taxonomy_score", 5)
    design_consistency = scores.get("design_consistency_score", 5)

    quality_score = min(structural_score, traceability, schema_completeness,
                        error_taxonomy, design_consistency)

    result = {
        "quality_score": quality_score,
        "structural_score": structural_score,
        "traceability_score": traceability,
        "schema_completeness_score": schema_completeness,
        "error_taxonomy_score": error_taxonomy,
        "design_consistency_score": design_consistency,
        "missing_sections": missing_sections,
        "fabricated_endpoints": scores.get("fabricated_endpoints", []),
        "schema_gaps": scores.get("schema_gaps", []),
        "critical_issues": scores.get("critical_issues", []),
        "improvement_suggestions": scores.get("improvement_suggestions", []),
    }

    return {"output": result}, None


def step_4_llm(inputs, context):
    """Improve API Specification Based on Critic Feedback."""
    generated_api_spec = context.get("generated_api_spec", "")
    step_3_output = context.get("step_3_output", {})
    step_1_output = context.get("step_1_output", {})
    service_description = inputs.get("service_description", "")
    target_consumers = inputs.get("target_consumers", "")

    if not generated_api_spec:
        return None, "No generated API specification found in context for improvement."

    quality_score = step_3_output.get("quality_score", 0)
    critical_issues = step_3_output.get("critical_issues", [])
    improvement_suggestions = step_3_output.get("improvement_suggestions", [])
    missing_sections = step_3_output.get("missing_sections", [])
    fabricated_endpoints = step_3_output.get("fabricated_endpoints", [])
    schema_gaps = step_3_output.get("schema_gaps", [])
    api_style = step_1_output.get("api_style", inputs.get("api_style", "REST"))
    anti_fabrication = step_1_output.get("generation_plan", {}).get(
        "anti_fabrication_contract",
        "All endpoints must be traceable to explicit capabilities in the service description."
    )

    system_prompt = (
        "You are a senior API architect with deep expertise in RESTful and GraphQL design, "
        "OpenAPI specification, authentication patterns, and developer experience. You produce "
        "precise, traceable API surfaces grounded strictly in the stated service capabilities.\n\n"
        "ANTI-FABRICATION CONTRACT: " + anti_fabrication + "\n\n"
        "You are revising an API specification based on structured critic feedback. "
        "Address every identified issue precisely. Do not remove correct content — only add, "
        "fix, or clarify. Preserve all correct sections and improve weak ones. "
        "Use ## (H2 markdown) for all top-level section headings."
    )

    issues_text = ""
    if critical_issues:
        issues_text += "\nCRITICAL ISSUES TO FIX (address each one explicitly):\n"
        issues_text += "\n".join(f"- {i}" for i in critical_issues)
    if missing_sections:
        issues_text += "\nMISSING SECTIONS TO ADD (each must be present and substantive):\n"
        issues_text += "\n".join(f"- {s}" for s in missing_sections)
    if fabricated_endpoints:
        issues_text += "\nFABRICATED ENDPOINTS TO REMOVE OR JUSTIFY WITH CAPABILITY CITATION:\n"
        issues_text += "\n".join(f"- {e}" for e in fabricated_endpoints)
    if schema_gaps:
        issues_text += "\nSCHEMA GAPS TO FILL (add complete field definitions):\n"
        issues_text += "\n".join(f"- {g}" for g in schema_gaps)
    if improvement_suggestions:
        issues_text += "\nIMPROVEMENT SUGGESTIONS TO IMPLEMENT:\n"
        issues_text += "\n".join(f"- {s}" for s in improvement_suggestions)

    user_prompt = f"""Revise the following API surface specification to address all critic feedback.

SERVICE DESCRIPTION (ground truth — all endpoints must trace to this):
{service_description}

TARGET CONSUMERS: {target_consumers}
API STYLE: {api_style}
CURRENT QUALITY SCORE: {quality_score}/10

CRITIC FEEDBACK TO ADDRESS:
{issues_text if issues_text else 'No specific issues — perform general quality improvement across all sections.'}

CURRENT API SPECIFICATION:
{generated_api_spec}

Produce a complete, revised API specification that:
1. Fixes every critical issue listed above with specific, substantive corrections
2. Adds all missing sections with full content (not placeholders)
3. Removes any endpoints not traceable to the service description, or adds explicit capability citations
4. Fills all schema gaps with complete field definitions (name, type, required/optional, description)
5. Implements all improvement suggestions
6. Preserves and retains all correct content from the original
7. Ensures the error taxonomy has a standard envelope and at least 8 specific error codes
8. Ensures the traceability matrix maps every endpoint to a service capability

Return the COMPLETE revised specification — not just the changed parts. All sections must be present."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    content, error = call_resolved(messages, context, max_tokens=8000)
    if error:
        content, error = call_openai(messages, max_tokens=8000)
    if error:
        return None, error

    return {"output": content}, None


def step_5_local(inputs, context):
    """Write Final API Specification Artifact."""
    improved_api_spec = context.get("improved_api_spec", "")
    generated_api_spec = context.get("generated_api_spec", "")
    step_3_output = context.get("step_3_output", {})

    final_spec = improved_api_spec if improved_api_spec else generated_api_spec

    if not final_spec:
        return None, "No API specification available to write."

    structural_score, missing_sections = check_structural_sections(final_spec)
    if structural_score < 3:
        return None, (
            f"Final API specification failed structural gate (score={structural_score}/10). "
            f"Missing: {', '.join(missing_sections)}. Cannot write artifact."
        )

    workflow_id = context.get("workflow_id", "unknown")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    quality_score = step_3_output.get("quality_score", "N/A")

    header = (
        f"<!-- API Surface Designer Output\n"
        f"     Workflow ID: {workflow_id}\n"
        f"     Generated: {timestamp}\n"
        f"     Quality Score: {quality_score}/10\n"
        f"     Structural Score: {structural_score}/10\n"
        f"     Source: a01-api-surface-designer v1.0.0\n"
        f"-->\n\n"
    )

    artifact_content = header + final_spec

    output_dir = "skills/a01-api-surface-designer/outputs"
    os.makedirs(output_dir, exist_ok=True)
    filename = f"a01-api-surface-designer_{workflow_id}_{timestamp}.md"
    artifact_path = os.path.join(output_dir, filename)

    try:
        with open(artifact_path, "w", encoding="utf-8") as f:
            f.write(artifact_content)
    except Exception as e:
        return None, f"Failed to write artifact: {str(e)}"

    return {"output": "artifact_written"}, None


STEP_HANDLERS = {
    "step_1": step_1_local,
    "step_2": step_2_llm,
    "step_3": step_3_critic,
    "step_4": step_4_llm,
    "step_5": step_5_local,
}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--step", required=True)
    parser.add_argument("--input", required=True)
    a = parser.parse_args()
    with open(a.input) as f:
        spec = json.load(f)
    h = STEP_HANDLERS.get(spec["step_id"])
    if not h:
        print(json.dumps({"error": f"Unknown step: {spec['step_id']}"}))
        sys.exit(1)
    result, error = h(spec["inputs"], spec["context"])
    if error:
        print(json.dumps({"error": error}))
        sys.exit(1)
    print(json.dumps(result))