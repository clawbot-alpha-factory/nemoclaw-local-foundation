#!/usr/bin/env python3
"""
Skill ID: a01-sys-context-mapper
Version: 1.0.0
Family: F01
Domain: A
Tag: internal
Type: transformer
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
    from lib.routing import call_llm_or_chain
    return call_llm_or_chain(messages, task_class="general_short", task_domain="architecture", max_tokens=max_tokens)

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


REQUIRED_SECTIONS = [
    "External Actors",
    "Data Flows",
    "Trust Boundaries",
    "System Capabilities",
    "Constraints",
    "Assumptions",
    "Context Narrative",
]

TOKEN_BUDGET = {"minimal": 4000, "standard": 8000, "detailed": 12000}


def check_required_sections(text):
    missing = []
    for section in REQUIRED_SECTIONS:
        pattern = re.compile(rf'##\s[^\n]*{re.escape(section)}', re.IGNORECASE)
        if not pattern.search(text):
            missing.append(section)
    return missing


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
    """Parse Inputs and Build Extraction Plan."""
    system_name = inputs.get("system_name", "").strip()
    system_description = inputs.get("system_description", "").strip()
    known_integrations = inputs.get("known_integrations", "").strip()
    domain_context = inputs.get("domain_context", "").strip()
    output_detail_level = inputs.get("output_detail_level", "standard").strip()

    if not system_name or len(system_name) < 2:
        return None, "system_name is required and must be at least 2 characters."
    if len(system_name) > 120:
        return None, "system_name must not exceed 120 characters."
    if not system_description or len(system_description) < 50:
        return None, "system_description is required and must be at least 50 characters."
    if len(system_description) > 8000:
        return None, "system_description must not exceed 8000 characters."
    if len(known_integrations) > 4000:
        return None, "known_integrations must not exceed 4000 characters."
    if len(domain_context) > 500:
        return None, "domain_context must not exceed 500 characters."

    allowed_levels = list(TOKEN_BUDGET.keys())
    if output_detail_level not in allowed_levels:
        output_detail_level = "standard"

    has_integrations = bool(known_integrations)
    has_domain = bool(domain_context)

    inference_scope = "full"
    if has_integrations and has_domain:
        inference_scope = "constrained"
    elif has_integrations:
        inference_scope = "integration-guided"
    elif has_domain:
        inference_scope = "domain-guided"

    extraction_plan = {
        "system_name": system_name,
        "system_description": system_description,
        "known_integrations": known_integrations,
        "domain_context": domain_context,
        "output_detail_level": output_detail_level,
        "has_integrations": has_integrations,
        "has_domain": has_domain,
        "inference_scope": inference_scope,
        "required_sections": REQUIRED_SECTIONS,
        "token_budget": TOKEN_BUDGET.get(output_detail_level, 8000),
    }

    return {"output": extraction_plan}, None


def step_2_llm(inputs, context):
    """Generate Structured System Context Document."""
    plan = context.get("step_1_output", {})
    if not plan:
        return None, "step_1_output not found in context."

    system_name = plan.get("system_name", inputs.get("system_name", ""))
    system_description = plan.get("system_description", inputs.get("system_description", ""))
    known_integrations = plan.get("known_integrations", "")
    domain_context = plan.get("domain_context", "")
    output_detail_level = plan.get("output_detail_level", "standard")
    inference_scope = plan.get("inference_scope", "full")
    token_budget = plan.get("token_budget", 8000)

    if not system_name:
        return None, "system_name missing from extraction plan."
    if not system_description:
        return None, "system_description missing from extraction plan."

    integrations_block = (
        f"\n\nKnown Integrations:\n{known_integrations}"
        if known_integrations
        else "\n\nKnown Integrations: None provided — infer from description."
    )
    domain_block = (
        f"\n\nDomain Context: {domain_context}"
        if domain_context
        else "\n\nDomain Context: Not specified — infer from description."
    )

    detail_instructions = {
        "minimal": (
            "Be concise. List actors and flows briefly. Keep narrative to 2-3 sentences. "
            "Each section should be short — bullet points preferred over prose."
        ),
        "standard": (
            "Provide moderate detail. Each actor and flow should have a brief description. "
            "Narrative should be 1-2 paragraphs. Include direction and data type for flows."
        ),
        "detailed": (
            "Be comprehensive. Include sub-types of actors, detailed flow attributes "
            "(direction, format, frequency, protocol), layered trust boundaries with security "
            "implications, and a full C4-style narrative with explicit rationale for every inference."
        ),
    }.get(output_detail_level, "Provide moderate detail.")

    system_prompt = (
        "You are a senior software architect specializing in system context analysis and "
        "C4 model documentation. You produce precise, traceable system context documents "
        "that clearly distinguish between stated facts and inferred relationships. "
        "You MUST tag every actor, flow, trust boundary, and constraint with either "
        "[STATED] (directly mentioned in the input) or [INFERRED] (derived by you). "
        "For every [INFERRED] item, include a brief parenthetical explaining the basis "
        "for the inference. Never fabricate integrations or actors not supported by the input. "
        "Output ONLY the markdown document — no preamble, no commentary, no code fences."
    )

    user_prompt = f"""Produce a structured system context document for the following system.

System Name: {system_name}

System Description:
{system_description}{integrations_block}{domain_block}

Inference Scope: {inference_scope}
Detail Level: {output_detail_level} — {detail_instructions}

---

Your output MUST be a markdown document with ALL of the following H2 sections in this exact order:

## External Actors
List every external actor (human users, external systems, third-party services) that interacts with {system_name}.
For each actor include:
- Actor name
- Actor type (human user / external system / third-party service)
- Brief description of their role
- Source tag: [STATED] if mentioned in the description or integrations, [INFERRED] if derived

## Data Flows
List every data flow between external actors and {system_name}.
For each flow include:
- Flow name or label
- Direction (actor → system, system → actor, or bidirectional)
- Data format or type (if known or inferable)
- Frequency or trigger (if known or inferable)
- Source tag: [STATED] or [INFERRED]

## Trust Boundaries
Identify trust boundaries relevant to {system_name}.
For each boundary include:
- Boundary name
- What it separates (e.g., public internet vs. internal network)
- Security or trust implications
- Source tag: [STATED] or [INFERRED]

## System Capabilities
Summarize the core capabilities of {system_name} as understood from the description.
List each capability with a brief description. No source tags required here.

## Constraints
List known or inferred constraints on {system_name} (technical, regulatory, operational, performance).
Tag each as [STATED] or [INFERRED]. For [INFERRED] constraints, state the basis.

## Assumptions
List all assumptions made during this analysis, especially where information was absent or ambiguous.
Tag each as [INFERRED] and briefly state what was assumed and why.

## Context Narrative
Write a C4-style context narrative describing {system_name}, its purpose, its external actors,
and its key interactions. This should read as a coherent architectural summary suitable for a
technical audience. Reference the actors and flows identified above. Length: {detail_instructions.split('.')[0]}.

---

CRITICAL RULES:
1. Every actor, flow, trust boundary, and constraint MUST have a [STATED] or [INFERRED] tag.
2. Every [INFERRED] item MUST include a brief parenthetical basis: e.g., (inferred: typical for SaaS platforms).
3. Do NOT invent integrations or actors not supported by the input description.
4. Do NOT omit any of the 7 required H2 sections.
5. Output ONLY the markdown document — no preamble, no code fences."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    content, error = call_resolved(messages, context, max_tokens=token_budget)
    if error:
        content, error = call_openai(messages, max_tokens=token_budget)
    if error:
        return None, error

    return {"output": content}, None


def step_3_critic(inputs, context):
    """Evaluate Context Document Quality and Traceability."""
    generated = context.get("improved_context_doc", context.get("generated_context_doc", ""))
    if not generated:
        return None, "generated_context_doc not found in context."

    plan = context.get("step_1_output", {})
    system_name = plan.get("system_name", inputs.get("system_name", ""))

    # Deterministic structural checks
    missing_sections = check_required_sections(generated)
    structural_score = 10 if not missing_sections else max(1, 10 - (len(missing_sections) * 2))

    has_stated_tags = bool(re.search(r'\[STATED\]', generated, re.IGNORECASE))
    has_inferred_tags = bool(re.search(r'\[INFERRED\]', generated, re.IGNORECASE))
    traceability_ok = has_stated_tags or has_inferred_tags

    actors_section = extract_section(generated, ["External Actors"])
    flows_section = extract_section(generated, ["Data Flows"])
    has_actors = bool(actors_section.strip())
    has_flows = bool(flows_section.strip())

    deterministic_issues = []
    if missing_sections:
        deterministic_issues.append(f"Missing required sections: {', '.join(missing_sections)}")
    if not traceability_ok:
        deterministic_issues.append("No [STATED] or [INFERRED] tags found — traceability missing.")
    if not has_actors:
        deterministic_issues.append("External Actors section appears empty.")
    if not has_flows:
        deterministic_issues.append("Data Flows section appears empty.")

    system_prompt = (
        "You are a senior software architect specializing in system context analysis and "
        "C4 model documentation. You evaluate context documents for completeness, accuracy, "
        "and traceability. You are rigorous and specific in your feedback. Return ONLY valid JSON."
    )

    user_prompt = f"""Evaluate the following system context document for the system: {system_name}.

Score each dimension from 1 to 10:

- traceability_score: Are ALL actors, flows, trust boundaries, and constraints tagged [STATED] or [INFERRED]?
  Are [INFERRED] items accompanied by a brief basis for the inference?
  10 = every item tagged with clear basis; 1 = no tags at all.

- completeness_score: Are all 7 required sections present and substantively filled?
  Are actors and flows comprehensive given the input description?
  Are trust boundaries, constraints, and assumptions meaningful?
  10 = all sections complete and thorough; 1 = multiple sections missing or empty.

Also provide:
- feedback: A list of 3-6 specific, actionable improvement suggestions as strings.
  Focus on what is missing, vague, or incorrect — not what is good.
- pass_threshold: true if BOTH traceability_score >= 7 AND completeness_score >= 7, false otherwise.

Deterministic issues already identified (these MUST lower your scores accordingly):
{json.dumps(deterministic_issues, indent=2)}

Return ONLY this JSON structure with no markdown fences:
{{
  "traceability_score": <int 1-10>,
  "completeness_score": <int 1-10>,
  "feedback": ["<specific issue 1>", "<specific issue 2>", ...],
  "pass_threshold": <bool>
}}

System Context Document to evaluate:
---
{generated}
---"""

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
        scores = {
            "traceability_score": 5,
            "completeness_score": 5,
            "feedback": ["Could not parse LLM critic response."] + deterministic_issues,
            "pass_threshold": False,
        }

    traceability_score = int(scores.get("traceability_score", 5))
    completeness_score = int(scores.get("completeness_score", 5))
    quality_score = min(structural_score, traceability_score, completeness_score)

    result = {
        "quality_score": quality_score,
        "structural_score": structural_score,
        "traceability_score": traceability_score,
        "completeness_score": completeness_score,
        "pass_threshold": scores.get("pass_threshold", quality_score >= 7),
        "feedback": scores.get("feedback", []) + deterministic_issues,
        "missing_sections": missing_sections,
        "deterministic_issues": deterministic_issues,
    }

    return {"output": result}, None


def step_4_llm(inputs, context):
    """Improve Context Document Based on Critic Feedback."""
    generated = context.get("generated_context_doc", "")
    critic_output = context.get("step_3_output", {})

    if not generated:
        return None, "generated_context_doc not found in context."

    plan = context.get("step_1_output", {})
    system_name = plan.get("system_name", inputs.get("system_name", ""))
    output_detail_level = plan.get("output_detail_level", "standard")
    token_budget = plan.get("token_budget", 8000)

    feedback = critic_output.get("feedback", [])
    missing_sections = critic_output.get("missing_sections", [])
    quality_score = critic_output.get("quality_score", 0)
    traceability_score = critic_output.get("traceability_score", 0)
    completeness_score = critic_output.get("completeness_score", 0)

    feedback_block = "\n".join(f"- {f}" for f in feedback) if feedback else "- No specific feedback provided."
    missing_block = ", ".join(missing_sections) if missing_sections else "None"

    system_prompt = (
        "You are a senior software architect specializing in system context analysis and "
        "C4 model documentation. You revise system context documents to address specific "
        "quality deficiencies while preserving all correct content. "
        "You are meticulous about traceability: every actor, flow, trust boundary, and "
        "constraint MUST be tagged [STATED] or [INFERRED], with a brief basis for all [INFERRED] items. "
        "Output ONLY the revised markdown document — no preamble, no commentary, no code fences."
    )

    user_prompt = f"""Revise the following system context document for {system_name} to address the critic feedback below.

Critic Scores: quality={quality_score}/10, traceability={traceability_score}/10, completeness={completeness_score}/10
Missing Sections: {missing_block}

Critic Feedback (address ALL of these):
{feedback_block}

Revision Instructions:
1. Add any missing required sections in order: External Actors, Data Flows, Trust Boundaries,
   System Capabilities, Constraints, Assumptions, Context Narrative.
2. Ensure EVERY actor, flow, trust boundary, and constraint is tagged [STATED] or [INFERRED].
3. For every [INFERRED] item, add a brief parenthetical basis: e.g., (inferred: typical for SaaS platforms).
4. Fill in missing direction, data format, or frequency for data flows where inferable.
5. Ensure Trust Boundaries section identifies what each boundary separates and its security implications.
6. Ensure Assumptions section lists all analytical assumptions made, each tagged [INFERRED].
7. Preserve all correct content from the original document — do not remove valid actors or flows.
8. Maintain the same detail level: {output_detail_level}.
9. Return the COMPLETE revised document — do not summarize, truncate, or omit sections.

Original Document:
---
{generated}
---

Return the complete revised markdown document with all 7 required H2 sections."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    content, error = call_resolved(messages, context, max_tokens=token_budget)
    if error:
        content, error = call_openai(messages, max_tokens=token_budget)
    if error:
        return None, error

    return {"output": content}, None


def step_5_local(inputs, context):
    """Write Final Context Document Artifact."""
    improved = context.get("improved_context_doc", "")
    generated = context.get("generated_context_doc", "")
    final_content = improved if improved else generated

    if not final_content:
        return None, "No context document found to write (neither improved_context_doc nor generated_context_doc)."

    missing = check_required_sections(final_content)
    if missing:
        return None, f"Final document is missing required sections: {', '.join(missing)}"

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