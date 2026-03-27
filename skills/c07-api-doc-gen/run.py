#!/usr/bin/env python3
"""
Skill ID: c07-api-doc-gen
Version: 1.0.0
Family: F07
Domain: C
Tag: dual-use
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


def load_env():
    p = os.path.expanduser("~/nemoclaw-local-foundation/config/.env")
    k = {}
    if os.path.exists(p):
        with open(p) as f:
            for ln in f:
                ln = ln.strip()
                if "=" in ln and not ln.startswith("#"):
                    a, b = ln.split("=", 1)
                    k[a.strip()] = b.strip()
    return k


def call_openai(messages, model="gpt-5.4-mini", max_tokens=4000):
    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage, SystemMessage
        env = load_env()
        api_key = env.get("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
        llm = ChatOpenAI(model=model, max_tokens=max_tokens, api_key=api_key)
        lc = [SystemMessage(content=m["content"]) if m["role"] == "system"
              else HumanMessage(content=m["content"]) for m in messages]
        return llm.invoke(lc).content, None
    except Exception as e:
        return None, str(e)


def call_anthropic(messages, model="claude-sonnet-4-6", max_tokens=4000):
    try:
        from langchain_anthropic import ChatAnthropic
        from langchain_core.messages import HumanMessage, SystemMessage
        env = load_env()
        api_key = env.get("ANTHROPIC_API_KEY", os.environ.get("ANTHROPIC_API_KEY", ""))
        llm = ChatAnthropic(model=model, max_tokens=max_tokens, api_key=api_key)
        lc = [SystemMessage(content=m["content"]) if m["role"] == "system"
              else HumanMessage(content=m["content"]) for m in messages]
        return llm.invoke(lc).content, None
    except Exception as e:
        return None, str(e)


def call_google(messages, model="gemini-2.5-flash", max_tokens=4000):
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import HumanMessage, SystemMessage
        env = load_env()
        api_key = env.get("GOOGLE_API_KEY", os.environ.get("GOOGLE_API_KEY", ""))
        llm = ChatGoogleGenerativeAI(model=model, max_output_tokens=max_tokens, google_api_key=api_key)
        lc = [SystemMessage(content=m["content"]) if m["role"] == "system"
              else HumanMessage(content=m["content"]) for m in messages]
        return llm.invoke(lc).content, None
    except Exception as e:
        return None, str(e)


def call_resolved(messages, context, max_tokens=4000):
    provider = context.get("resolved_provider", "openai")
    model = context.get("resolved_model", "gpt-5.4-mini")
    try:
        if provider == "anthropic":
            return call_anthropic(messages, model=model, max_tokens=max_tokens)
        elif provider == "google":
            return call_google(messages, model=model, max_tokens=max_tokens)
        else:
            return call_openai(messages, model=model, max_tokens=max_tokens)
    except Exception as e:
        return None, str(e)


TOKEN_BUDGET = {"concise": 4000, "standard": 8000, "comprehensive": 12000}

REQUIRED_SECTIONS = [
    "endpoint reference",
    "authentication",
    "error",
    "rate limit",
    "quick start",
]

SDK_SECTION_KEYWORDS = ["sdk", "usage pattern", "client library"]

VALID_AUTH_TYPES = {"bearer_token", "api_key", "oauth2", "basic_auth", "none"}
VALID_DEPTHS = {"concise", "standard", "comprehensive"}
VALID_SDK_OPTIONS = {"yes", "no"}


def check_required_sections(text):
    text_lower = text.lower()
    missing = []
    for section in REQUIRED_SECTIONS:
        if section not in text_lower:
            missing.append(section)
    return missing


def check_sdk_section(text):
    text_lower = text.lower()
    return any(kw in text_lower for kw in SDK_SECTION_KEYWORDS)


def check_curl_examples(text):
    return "curl" in text.lower()


def extract_section(text, heading_keywords):
    for kw in heading_keywords:
        pattern = re.compile(
            rf'(?:^|\n)##\s[^\n]*{re.escape(kw)}[^\n]*\n(.*?)(?=\n##\s[^#]|\Z)',
            re.IGNORECASE | re.DOTALL)
        m = pattern.search(text)
        if m:
            return m.group(1).strip()
    return ""


def step_1_local(inputs, context):
    """Parse Specification and Build Documentation Plan."""
    api_spec = inputs.get("api_specification", "")
    target_audience = inputs.get("target_audience", "developers")
    api_name = inputs.get("api_name", "API")
    base_url = inputs.get("base_url", "https://api.example.com/v1")
    auth_type = inputs.get("authentication_type", "bearer_token")
    include_sdk = inputs.get("include_sdk_patterns", "yes")
    depth = inputs.get("documentation_depth", "standard")

    # Input validation
    if not api_spec or len(api_spec.strip()) < 100:
        return None, "api_specification is too short or empty (minimum 100 characters required)"
    if not target_audience or len(target_audience.strip()) < 3:
        return None, "target_audience is too short (minimum 3 characters required)"
    if not api_name or len(api_name.strip()) < 2:
        return None, "api_name is too short (minimum 2 characters required)"
    if auth_type not in VALID_AUTH_TYPES:
        return None, f"authentication_type must be one of: {', '.join(sorted(VALID_AUTH_TYPES))}"
    if depth not in VALID_DEPTHS:
        return None, f"documentation_depth must be one of: {', '.join(sorted(VALID_DEPTHS))}"
    if include_sdk not in VALID_SDK_OPTIONS:
        return None, "include_sdk_patterns must be 'yes' or 'no'"

    spec_lower = api_spec.lower()

    # Detect spec format
    spec_format = "text"
    if api_spec.strip().startswith("{") or api_spec.strip().startswith("["):
        spec_format = "json"
    elif "openapi:" in spec_lower or "swagger:" in spec_lower:
        spec_format = "yaml_openapi"
    elif "paths:" in spec_lower or "components:" in spec_lower:
        spec_format = "yaml"

    # Extract endpoint hints
    endpoint_patterns = re.findall(
        r'(?:GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+[/\w\{\}:.-]+',
        api_spec, re.IGNORECASE
    )
    path_patterns = re.findall(r'["\']?(/[/\w\{\}:.-]+)["\']?', api_spec)
    unique_paths = list(dict.fromkeys(path_patterns))[:30]

    # Detect auth hints
    auth_hints = []
    if "bearer" in spec_lower or "authorization" in spec_lower:
        auth_hints.append("bearer_token")
    if "api_key" in spec_lower or "x-api-key" in spec_lower:
        auth_hints.append("api_key")
    if "oauth" in spec_lower:
        auth_hints.append("oauth2")
    if "basic" in spec_lower:
        auth_hints.append("basic_auth")

    # Detect error codes
    error_codes = re.findall(r'\b[45]\d{2}\b', api_spec)
    unique_error_codes = list(dict.fromkeys(error_codes))[:20]

    # Detect rate limiting hints
    rate_limit_hints = "rate_limit" in spec_lower or "x-ratelimit" in spec_lower or "throttl" in spec_lower

    doc_plan = {
        "api_name": api_name,
        "base_url": base_url,
        "target_audience": target_audience,
        "auth_type": auth_type,
        "auth_hints": auth_hints,
        "include_sdk": include_sdk,
        "depth": depth,
        "spec_format": spec_format,
        "detected_endpoints": endpoint_patterns[:20],
        "detected_paths": unique_paths,
        "detected_error_codes": unique_error_codes,
        "rate_limit_hints": rate_limit_hints,
        "spec_length": len(api_spec),
        "sections_to_generate": [
            "overview",
            "authentication_guide",
            "endpoint_reference",
            "error_handling_reference",
            "rate_limiting_documentation",
            "quick_start_guide",
        ] + (["sdk_usage_patterns"] if include_sdk == "yes" else []),
        "token_budget": TOKEN_BUDGET.get(depth, 8000),
    }

    return {"output": doc_plan}, None


def step_2_llm(inputs, context):
    """Generate Comprehensive API Documentation Draft."""
    doc_plan = context.get("step_1_output", {})
    api_spec = inputs.get("api_specification", "")
    depth = inputs.get("documentation_depth", "standard")
    token_budget = TOKEN_BUDGET.get(depth, 8000)

    api_name = doc_plan.get("api_name", inputs.get("api_name", "API"))
    base_url = doc_plan.get("base_url", inputs.get("base_url", "https://api.example.com/v1"))
    target_audience = doc_plan.get("target_audience", inputs.get("target_audience", "developers"))
    auth_type = doc_plan.get("auth_type", inputs.get("authentication_type", "bearer_token"))
    include_sdk = doc_plan.get("include_sdk", inputs.get("include_sdk_patterns", "yes"))

    system_prompt = """You are a senior technical writer and API documentation specialist. You produce precise, developer-friendly API documentation that is strictly consistent with the provided specification. You never invent endpoints, parameters, or behaviors not present in the input.

CRITICAL RULES:
- Only document endpoints, parameters, fields, and behaviors explicitly present in the provided specification.
- Never fabricate example values, endpoints, or parameters not in the specification.
- All curl examples must use only real endpoints and parameters from the specification.
- Use the exact base URL provided for all examples.
- Structure output as clean markdown with H2 section headings (##).
- Every section must begin with a ## heading.
- The Endpoint Reference section must include a curl example for each endpoint using the exact base URL.
- The Authentication Guide must show the exact header format required.
- The Error Handling Reference must list every HTTP error code found in the specification.
- The Rate Limiting section must describe headers and 429 handling.
- The Quick Start Guide must be a numbered step-by-step walkthrough with curl examples."""

    sdk_instruction = ""
    if include_sdk == "yes":
        sdk_instruction = "\n- ## SDK Usage Patterns: Provide Python, JavaScript/Node.js, and cURL patterns for the most common operations. Derive all method names, endpoints, and parameters strictly from the specification."

    user_prompt = f"""Generate comprehensive API documentation for the **{api_name}** based on the specification below.

**Target Audience:** {target_audience}
**Base URL:** {base_url}
**Authentication Type:** {auth_type}
**Documentation Depth:** {depth}

**Required Sections — use ## H2 headings for each section listed:**

## Overview
Describe the API purpose, key capabilities, and intended use cases based strictly on the specification.

## Authentication Guide
Explain how to authenticate using {auth_type}. Show the exact request header format. Provide a curl example demonstrating authentication against {base_url}.

## Endpoint Reference
For EACH endpoint present in the specification, document:
- HTTP method and full path (e.g., POST /users)
- Description of what the endpoint does
- All path parameters, query parameters, and request body fields (name, type, required/optional, description)
- Response schema with field descriptions
- A complete curl example using {base_url} with realistic but spec-derived values

## Error Handling Reference
List every HTTP error code (4xx, 5xx) present in the specification. For each: status code, name, description, and recommended resolution steps.

## Rate Limiting
Describe the rate limiting policy. List all rate limit response headers. Show how to detect a 429 response and implement retry logic with a curl example.

## Quick Start Guide
Provide a numbered step-by-step guide showing the most common end-to-end use case. Each step must include a curl command using {base_url}.{sdk_instruction}

**API Specification (source of truth — base ALL content strictly on this):**
{api_spec}

IMPORTANT: Do NOT invent any endpoints, parameters, fields, or behaviors not explicitly present in the specification above. Every curl example must use {base_url} and only real endpoints from the specification."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    content, error = call_resolved(messages, context, max_tokens=token_budget)
    if error:
        content, error = call_openai(messages, model="gpt-5.4-mini", max_tokens=token_budget)
    if error:
        return None, error

    return {"output": content}, None


def step_3_critic(inputs, context):
    """Evaluate Documentation Quality and Specification Fidelity."""
    generated_doc = context.get("improved_documentation", context.get("generated_documentation", ""))
    api_spec = inputs.get("api_specification", "")
    include_sdk = inputs.get("include_sdk_patterns", "yes")

    if not generated_doc:
        return None, "No generated documentation found in context"

    # Deterministic checks
    missing_sections = check_required_sections(generated_doc)
    has_curl = check_curl_examples(generated_doc)
    has_sdk = check_sdk_section(generated_doc) if include_sdk == "yes" else True

    structural_issues = []
    if missing_sections:
        structural_issues.append(f"Missing required sections: {', '.join(missing_sections)}")
    if not has_curl:
        structural_issues.append("No curl examples found in documentation")
    if include_sdk == "yes" and not has_sdk:
        structural_issues.append("SDK usage patterns section missing or incomplete")

    structural_score = 10
    structural_score -= len(missing_sections) * 2
    if not has_curl:
        structural_score -= 2
    if include_sdk == "yes" and not has_sdk:
        structural_score -= 1
    structural_score = max(1, structural_score)

    system_prompt = """You are a senior technical writer and API documentation quality evaluator. You assess API documentation for accuracy, completeness, and fidelity to the source specification.

Your job is to identify:
1. SPECIFICATION FIDELITY: Does the documentation only describe what is in the spec? Deduct for any fabricated endpoints, parameters, fields, or behaviors not present in the specification.
2. DOCUMENTATION QUALITY: Is the documentation clear, complete, and developer-friendly? Are examples correct and useful? Are all required sections present and well-written?

You respond ONLY with valid JSON — no markdown fences, no explanation text."""

    user_prompt = f"""Evaluate this API documentation against the source specification on two dimensions.

**Source API Specification:**
{api_spec[:3000]}

**Generated Documentation:**
{generated_doc[:4000]}

**Structural Issues Already Detected by Automated Checks:**
{json.dumps(structural_issues)}

Score each dimension from 1 (very poor) to 10 (excellent).

For specification_fidelity: Start at 10. Deduct 2 points for each fabricated endpoint, parameter, or behavior not in the spec. Deduct 1 point for each inaccurate description.

For documentation_quality: Start at 10. Deduct points for missing sections, unclear explanations, missing curl examples, poor parameter documentation, or unhelpful quick start guide.

Respond with ONLY this JSON (no markdown fences, no extra text):
{{
  "specification_fidelity": <integer 1-10>,
  "documentation_quality": <integer 1-10>,
  "fidelity_issues": ["<specific fabricated or inaccurate item>", ...],
  "quality_issues": ["<specific quality or clarity problem>", ...],
  "improvement_priorities": ["<most important fix needed>", "<second>", "<third>"],
  "overall_assessment": "<one sentence summary of the documentation quality>"
}}"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    content, error = call_resolved(messages, context, max_tokens=2000)
    if error:
        content, error = call_openai(messages, model="gpt-5.4-mini", max_tokens=2000)
    if error:
        return None, error

    try:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
            cleaned = re.sub(r'\s*```$', '', cleaned)
        scores = json.loads(cleaned)
    except Exception as e:
        scores = {
            "specification_fidelity": 5,
            "documentation_quality": 5,
            "fidelity_issues": [],
            "quality_issues": [f"Could not parse critic response: {str(e)}"],
            "improvement_priorities": ["Review documentation manually"],
            "overall_assessment": "Critic evaluation incomplete due to parse error.",
        }

    fidelity_score = int(scores.get("specification_fidelity", 5))
    quality_score_llm = int(scores.get("documentation_quality", 5))
    quality_score = min(structural_score, fidelity_score, quality_score_llm)

    result = {
        "quality_score": quality_score,
        "structural_score": structural_score,
        "specification_fidelity": fidelity_score,
        "documentation_quality": quality_score_llm,
        "structural_issues": structural_issues,
        "fidelity_issues": scores.get("fidelity_issues", []),
        "quality_issues": scores.get("quality_issues", []),
        "improvement_priorities": scores.get("improvement_priorities", []),
        "overall_assessment": scores.get("overall_assessment", ""),
        "missing_sections": missing_sections,
        "has_curl_examples": has_curl,
        "has_sdk_section": has_sdk,
    }

    return {"output": result}, None


def step_4_llm(inputs, context):
    """Improve Documentation Based on Critic Feedback."""
    critic_output = context.get("step_3_output", {})
    generated_doc = context.get("generated_documentation", "")
    api_spec = inputs.get("api_specification", "")
    depth = inputs.get("documentation_depth", "standard")
    token_budget = TOKEN_BUDGET.get(depth, 8000)

    api_name = inputs.get("api_name", "API")
    base_url = inputs.get("base_url", "https://api.example.com/v1")
    include_sdk = inputs.get("include_sdk_patterns", "yes")

    if not generated_doc:
        return None, "No generated documentation found in context for improvement"

    structural_issues = critic_output.get("structural_issues", [])
    fidelity_issues = critic_output.get("fidelity_issues", [])
    quality_issues = critic_output.get("quality_issues", [])
    improvement_priorities = critic_output.get("improvement_priorities", [])
    missing_sections = critic_output.get("missing_sections", [])

    feedback_parts = []
    if structural_issues:
        feedback_parts.append("STRUCTURAL ISSUES TO FIX:\n" + "\n".join(f"- {i}" for i in structural_issues))
    if fidelity_issues:
        feedback_parts.append("SPECIFICATION FIDELITY ISSUES (remove or correct these fabricated items):\n" + "\n".join(f"- {i}" for i in fidelity_issues))
    if quality_issues:
        feedback_parts.append("QUALITY ISSUES TO IMPROVE:\n" + "\n".join(f"- {i}" for i in quality_issues))
    if improvement_priorities:
        feedback_parts.append("TOP IMPROVEMENT PRIORITIES:\n" + "\n".join(f"- {i}" for i in improvement_priorities))
    if missing_sections:
        feedback_parts.append("MISSING SECTIONS TO ADD:\n" + "\n".join(f"- {s}" for s in missing_sections))

    feedback_text = "\n\n".join(feedback_parts) if feedback_parts else "General quality improvement needed — ensure all required sections are present, all curl examples use the correct base URL, and all content is derived strictly from the specification."

    sdk_instruction = ""
    if include_sdk == "yes":
        sdk_instruction = "\n- ## SDK Usage Patterns: Python, JavaScript/Node.js, and cURL patterns for common operations — derived strictly from the specification."

    system_prompt = """You are a senior technical writer and API documentation specialist. You revise API documentation to address specific quality and accuracy issues identified by a critic.

CRITICAL RULES:
- Only document endpoints, parameters, fields, and behaviors explicitly present in the provided specification.
- Remove or correct any fabricated endpoints, parameters, or behaviors identified in the critic feedback.
- All curl examples must use only real endpoints and parameters from the specification.
- Fix ALL issues listed in the critic feedback.
- Produce the COMPLETE revised documentation — not just the changed sections.
- Every required section must be present with a ## H2 heading."""

    user_prompt = f"""Revise and improve the following API documentation for **{api_name}** based on the critic feedback below.

**Base URL for all curl examples:** {base_url}

**CRITIC FEEDBACK — ADDRESS ALL OF THESE:**
{feedback_text}

**REQUIRED SECTIONS (ensure ALL are present with ## H2 headings):**
- ## Overview
- ## Authentication Guide (with header format and curl example)
- ## Endpoint Reference (with curl examples using {base_url} for every endpoint)
- ## Error Handling Reference (all error codes with descriptions and resolution steps)
- ## Rate Limiting (headers, 429 handling, retry guidance)
- ## Quick Start Guide (numbered steps with curl examples){sdk_instruction}

**API Specification (source of truth — do NOT deviate from this):**
{api_spec[:3000]}

**Current Documentation (revise this to address all feedback above):**
{generated_doc}

Produce the complete revised documentation. Every piece of content must be traceable to the specification above."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    content, error = call_resolved(messages, context, max_tokens=token_budget)
    if error:
        content, error = call_openai(messages, model="gpt-5.4-mini", max_tokens=token_budget)
    if error:
        return None, error

    return {"output": content}, None


def step_5_local(inputs, context):
    """Write Final Documentation Artifact to Storage."""
    improved_doc = context.get("improved_documentation", "")
    generated_doc = context.get("generated_documentation", "")
    final_content = improved_doc if improved_doc else generated_doc

    if not final_content or len(final_content.strip()) < 50:
        return None, "Final documentation content is empty or too short to write"

    missing = check_required_sections(final_content)
    if len(missing) > 3:
        return None, f"Final documentation is missing too many required sections: {', '.join(missing)}"

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