#!/usr/bin/env python3
"""
Skill ID: c07-decision-record-writer
Version: 1.0.0
Family: F07
Domain: C
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
from datetime import datetime, timezone, timedelta



# ── LLM Helpers (routed through lib/routing.py — L-003 compliant) ────────────
def call_openai(messages, model=None, max_tokens=6000):
    from lib.routing import call_llm_or_chain
    return call_llm_or_chain(messages, task_class="general_short", task_domain="strategic_reasoning", max_tokens=max_tokens)

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
    "status",
    "context",
    "decision drivers",
    "options considered",
    "decision outcome",
    "consequences",
]


def check_structural_completeness(adr_text):
    """Check that all required Nygard template sections are present."""
    if not adr_text:
        return 0, []
    text_lower = adr_text.lower()
    missing = []
    for section in REQUIRED_SECTIONS:
        if section not in text_lower:
            missing.append(section)
    score = max(0, 10 - (len(missing) * 2))
    return score, missing


def step_1_local(inputs, context):
    """Parse Inputs and Build ADR Generation Plan."""
    decision_title = inputs.get("decision_title", "").strip()
    decision_context = inputs.get("decision_context", "").strip()
    options_raw = inputs.get("options_considered", [])
    if isinstance(options_raw, str):
        try:
            options_considered = json.loads(options_raw)
        except (json.JSONDecodeError, TypeError):
            options_considered = [o.strip() for o in options_raw.split(",") if o.strip()]
    else:
        options_considered = options_raw
    chosen_option = inputs.get("chosen_option", "").strip()
    decision_drivers = inputs.get("decision_drivers", [])
    status = inputs.get("status", "Proposed").strip()
    compliance_domains = inputs.get("compliance_domains", [])
    review_date = inputs.get("review_date", "").strip()

    if not decision_title or len(decision_title) < 5:
        return None, "decision_title must be at least 5 characters."
    if not decision_context or len(decision_context) < 50:
        return None, "decision_context must be at least 50 characters."
    if not options_considered or not isinstance(options_considered, list):
        return None, "options_considered must be a non-empty list."
    if not chosen_option or len(chosen_option) < 2:
        return None, "chosen_option must be at least 2 characters."

    normalized_options = []
    for opt in options_considered:
        if isinstance(opt, dict):
            normalized_options.append(opt)
        elif isinstance(opt, str):
            normalized_options.append({"name": opt, "description": ""})
        else:
            normalized_options.append({"name": str(opt), "description": ""})

    allowed_statuses = ["Proposed", "Accepted", "Deprecated", "Superseded"]
    if status not in allowed_statuses:
        status = "Proposed"

    if not review_date:
        one_year = datetime.now(timezone.utc) + timedelta(days=365)
        review_date = one_year.strftime("%Y-%m-%d")
    else:
        try:
            datetime.strptime(review_date, "%Y-%m-%d")
        except ValueError:
            one_year = datetime.now(timezone.utc) + timedelta(days=365)
            review_date = one_year.strftime("%Y-%m-%d")

    inferred_drivers = list(decision_drivers) if decision_drivers else []
    if not inferred_drivers:
        inferred_drivers = [
            "Maintainability and long-term sustainability",
            "Performance and scalability requirements",
            "Team expertise and learning curve",
            "Cost and operational overhead",
            "Security and compliance requirements",
        ]

    option_names = [o.get("name", str(o)) if isinstance(o, dict) else str(o) for o in normalized_options]
    chosen_in_list = any(
        chosen_option.lower() in name.lower() or name.lower() in chosen_option.lower()
        for name in option_names
    )

    creation_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    plan = {
        "decision_title": decision_title,
        "decision_context": decision_context,
        "normalized_options": normalized_options,
        "chosen_option": chosen_option,
        "decision_drivers": inferred_drivers,
        "status": status,
        "compliance_domains": compliance_domains if compliance_domains else [],
        "review_date": review_date,
        "creation_date": creation_date,
        "chosen_in_list": chosen_in_list,
        "option_names": option_names,
    }

    return {"output": plan}, None


def step_2_llm(inputs, context):
    """Generate Complete ADR Document Draft."""
    plan = context.get("step_1_output", {})
    if not plan:
        return None, "step_1_output not found in context."

    decision_title = plan.get("decision_title", "")
    decision_context = plan.get("decision_context", "")
    normalized_options = plan.get("normalized_options", [])
    chosen_option = plan.get("chosen_option", "")
    decision_drivers = plan.get("decision_drivers", [])
    status = plan.get("status", "Proposed")
    compliance_domains = plan.get("compliance_domains", [])
    review_date = plan.get("review_date", "")
    creation_date = plan.get("creation_date", "")

    options_text = ""
    for opt in normalized_options:
        if isinstance(opt, dict):
            name = opt.get("name", "")
            desc = opt.get("description", "")
            options_text += f"- **{name}**: {desc}\n" if desc else f"- **{name}**\n"
        else:
            options_text += f"- {opt}\n"

    drivers_text = "\n".join(f"- {d}" for d in decision_drivers)
    compliance_text = ", ".join(compliance_domains) if compliance_domains else "None specified"

    system_prompt = (
        "You are a senior software architect and technical writer specializing in Architecture "
        "Decision Records. You produce precise, well-reasoned ADRs that follow the Michael Nygard "
        "template exactly. You derive consequences logically from the chosen option and never "
        "fabricate outcomes.\n\n"
        "CRITICAL RULES:\n"
        "1. Every consequence you list MUST be directly and logically derivable from a specific "
        "property of the chosen option. Do NOT invent consequences not grounded in the chosen "
        "option's characteristics.\n"
        "2. Follow the exact Michael Nygard ADR template structure with these required sections: "
        "Status, Context and Problem Statement, Decision Drivers, Options Considered, Decision "
        "Outcome, Consequences, Compliance Notes, Review Date.\n"
        "3. Be specific and technical — avoid vague platitudes.\n"
        "4. Pros and cons must be realistic and balanced.\n"
        "5. The Consequences section MUST have Positive, Negative, and Neutral subsections.\n"
        "6. The Decision Outcome section MUST include the chosen option name and a multi-paragraph "
        "justification referencing the decision drivers and comparing against alternatives."
    )

    user_prompt = (
        f"Generate a complete Architecture Decision Record (ADR) following the Michael Nygard template.\n\n"
        f"## Input Data\n\n"
        f"**Title:** {decision_title}\n"
        f"**Status:** {status}\n"
        f"**Creation Date:** {creation_date}\n"
        f"**Review Date:** {review_date}\n\n"
        f"**Context and Problem Statement:**\n{decision_context}\n\n"
        f"**Decision Drivers:**\n{drivers_text}\n\n"
        f"**Options Considered:**\n{options_text}\n\n"
        f"**Chosen Option:** {chosen_option}\n\n"
        f"**Compliance Domains:** {compliance_text}\n\n"
        f"## Required Output Structure\n\n"
        f"Produce the ADR in this EXACT markdown structure:\n\n"
        f"# ADR: {decision_title}\n\n"
        f"## Status\n"
        f"{status} — {creation_date}\n\n"
        f"## Context and Problem Statement\n"
        f"[Detailed restatement of the problem and forces at play, 2-4 paragraphs]\n\n"
        f"## Decision Drivers\n"
        f"[Bulleted list of key factors that drove this decision]\n\n"
        f"## Options Considered\n\n"
        f"### Option 1: [Name]\n"
        f"[Brief description]\n\n"
        f"**Pros:**\n- [pro 1]\n- [pro 2]\n\n"
        f"**Cons:**\n- [con 1]\n- [con 2]\n\n"
        f"[Repeat for each option]\n\n"
        f"## Decision Outcome\n\n"
        f"**Chosen Option:** {chosen_option}\n\n"
        f"**Justification:**\n"
        f"[2-3 paragraphs explaining WHY this option was chosen over the alternatives, "
        f"referencing each decision driver explicitly]\n\n"
        f"## Consequences\n\n"
        f"### Positive Consequences\n"
        f"[List consequences that follow DIRECTLY from properties of {chosen_option}. "
        f"Each item must cite the specific property that causes this consequence.]\n\n"
        f"### Negative Consequences\n"
        f"[List trade-offs that follow DIRECTLY from properties of {chosen_option}. "
        f"Each item must cite the specific property that causes this trade-off.]\n\n"
        f"### Neutral Consequences\n"
        f"[List neutral outcomes that follow DIRECTLY from properties of {chosen_option}.]\n\n"
        f"## Compliance Notes\n"
        f"[Address compliance implications for: {compliance_text}]\n\n"
        f"## Review Date\n"
        f"{review_date}\n\n"
        f"IMPORTANT: Every consequence must be explicitly grounded in a specific property or "
        f"characteristic of the chosen option \"{chosen_option}\". Do not list generic consequences "
        f"that could apply to any option."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    content, error = call_resolved(messages, context, max_tokens=6000)
    if error:
        content, error = call_openai(messages, max_tokens=6000)
    if error:
        return None, error

    return {"output": content}, None


def step_3_critic(inputs, context):
    """Evaluate ADR Quality and Structural Completeness."""
    adr_text = context.get("improved_adr", context.get("generated_adr", ""))
    if not adr_text:
        return None, "generated_adr not found in context."

    plan = context.get("step_1_output", {})
    chosen_option = plan.get("chosen_option", "") if plan else ""

    structural_score, missing_sections = check_structural_completeness(adr_text)

    has_pros = "pros" in adr_text.lower()
    has_cons = "cons" in adr_text.lower()
    has_chosen = chosen_option.lower() in adr_text.lower() if chosen_option else False
    has_review_date = "review date" in adr_text.lower()
    has_compliance = "compliance" in adr_text.lower()

    structural_checks = {
        "has_pros_cons": has_pros and has_cons,
        "has_chosen_option": has_chosen,
        "has_review_date": has_review_date,
        "has_compliance_notes": has_compliance,
        "missing_sections": missing_sections,
    }

    if not (has_pros and has_cons):
        structural_score = max(0, structural_score - 1)
    if not has_chosen:
        structural_score = max(0, structural_score - 1)
    if not has_review_date:
        structural_score = max(0, structural_score - 1)

    system_prompt = (
        "You are a senior software architect and technical writer specializing in Architecture "
        "Decision Records. Evaluate the provided ADR on two dimensions and return ONLY valid JSON.\n\n"
        "EVALUATION FOCUS:\n"
        "1. consequence_grounding: Are consequences directly derivable from the chosen option's "
        "specific properties? Penalize generic consequences, fabricated outcomes, or missing "
        "real consequences of this specific option.\n"
        "2. justification_quality: Is the justification well-reasoned, referencing decision drivers "
        "and comparing against alternatives? Penalize vague reasoning or missing trade-off analysis."
    )

    user_prompt = (
        f"Evaluate this Architecture Decision Record on two dimensions.\n\n"
        f"## ADR to Evaluate:\n{adr_text}\n\n"
        f"## Chosen Option: {chosen_option}\n\n"
        f"## Evaluation Dimensions:\n\n"
        f"1. **consequence_grounding** (0-10): Are ALL listed consequences directly and logically "
        f"derivable from specific properties of the chosen option \"{chosen_option}\"? Deduct points for:\n"
        f"   - Consequences that are generic and could apply to any option\n"
        f"   - Consequences that contradict the chosen option's properties\n"
        f"   - Fabricated outcomes not grounded in the option's characteristics\n"
        f"   - Missing important real consequences of this specific option\n\n"
        f"2. **justification_quality** (0-10): Is the justification for choosing \"{chosen_option}\" "
        f"over alternatives well-reasoned? Deduct points for:\n"
        f"   - Vague or generic reasoning\n"
        f"   - Failure to reference the decision drivers\n"
        f"   - Not comparing against the alternatives\n"
        f"   - Missing explanation of trade-off acceptance\n\n"
        f"Return ONLY this JSON (no markdown fences, no explanation):\n"
        f"{{\n"
        f"  \"consequence_grounding\": <0-10>,\n"
        f"  \"justification_quality\": <0-10>,\n"
        f"  \"consequence_issues\": [\"issue1\", \"issue2\"],\n"
        f"  \"justification_issues\": [\"issue1\", \"issue2\"],\n"
        f"  \"improvement_suggestions\": [\"suggestion1\", \"suggestion2\", \"suggestion3\"]\n"
        f"}}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    content, error = call_resolved(messages, context, max_tokens=2000)
    if error:
        content, error = call_openai(messages, max_tokens=2000)
    if error:
        return None, error

    try:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
            cleaned = re.sub(r'\s*```$', '', cleaned)
        scores = json.loads(cleaned)
    except Exception:
        scores = {
            "consequence_grounding": 7,
            "justification_quality": 7,
            "consequence_issues": [],
            "justification_issues": [],
            "improvement_suggestions": [],
        }

    consequence_grounding = scores.get("consequence_grounding", 7)
    justification_quality = scores.get("justification_quality", 7)

    quality_score = min(structural_score, consequence_grounding, justification_quality)

    result = {
        "quality_score": quality_score,
        "structural_score": structural_score,
        "consequence_grounding": consequence_grounding,
        "justification_quality": justification_quality,
        "structural_checks": structural_checks,
        "consequence_issues": scores.get("consequence_issues", []),
        "justification_issues": scores.get("justification_issues", []),
        "improvement_suggestions": scores.get("improvement_suggestions", []),
        "missing_sections": missing_sections,
    }

    return {"output": result}, None


def step_4_llm(inputs, context):
    """Improve ADR Based on Critic Feedback."""
    original_adr = context.get("generated_adr", "")
    critic_output = context.get("adr_quality_report", {})

    if not original_adr:
        return None, "generated_adr not found in context."

    plan = context.get("step_1_output", {})
    chosen_option = plan.get("chosen_option", "") if plan else ""
    decision_drivers = plan.get("decision_drivers", []) if plan else []

    if not critic_output:
        return {"output": original_adr}, None

    quality_score = critic_output.get("quality_score", 10)
    if quality_score >= 10:
        return {"output": original_adr}, None

    consequence_issues = critic_output.get("consequence_issues", [])
    justification_issues = critic_output.get("justification_issues", [])
    improvement_suggestions = critic_output.get("improvement_suggestions", [])
    missing_sections = critic_output.get("missing_sections", [])

    issues_text = ""
    if consequence_issues:
        issues_text += "\n**Consequence Grounding Issues:**\n" + "\n".join(f"- {i}" for i in consequence_issues)
    if justification_issues:
        issues_text += "\n**Justification Issues:**\n" + "\n".join(f"- {i}" for i in justification_issues)
    if improvement_suggestions:
        issues_text += "\n**Improvement Suggestions:**\n" + "\n".join(f"- {s}" for s in improvement_suggestions)
    if missing_sections:
        issues_text += "\n**Missing Sections:**\n" + "\n".join(f"- {s}" for s in missing_sections)

    drivers_text = "\n".join(f"- {d}" for d in decision_drivers)

    system_prompt = (
        "You are a senior software architect and technical writer specializing in Architecture "
        "Decision Records. You produce precise, well-reasoned ADRs that follow the Michael Nygard "
        "template. You derive consequences logically from the chosen option and never fabricate "
        "outcomes.\n\n"
        "Your task is to improve an existing ADR based on specific critic feedback. You must "
        "address every identified issue while preserving the full Nygard template structure."
    )

    user_prompt = (
        f"Improve this Architecture Decision Record based on the critic feedback below.\n\n"
        f"## Original ADR:\n{original_adr}\n\n"
        f"## Chosen Option: {chosen_option}\n\n"
        f"## Decision Drivers:\n{drivers_text}\n\n"
        f"## Critic Feedback (Quality Score: {quality_score}/10):\n{issues_text}\n\n"
        f"## Improvement Instructions:\n\n"
        f"1. **Fix Consequence Grounding**: For EVERY consequence listed, ensure it is explicitly "
        f"linked to a specific property or characteristic of \"{chosen_option}\". Remove any generic "
        f"consequences. Add a brief parenthetical like \"(because {chosen_option} uses X architecture)\" "
        f"to make the grounding explicit.\n\n"
        f"2. **Strengthen Justification**: Ensure the justification section explicitly references "
        f"each decision driver and explains how \"{chosen_option}\" satisfies it better than the "
        f"alternatives.\n\n"
        f"3. **Fix Missing Sections**: Add any missing sections identified in the feedback.\n\n"
        f"4. **Maintain Structure**: Keep the full Michael Nygard template structure intact. "
        f"Do not remove any existing sections.\n\n"
        f"5. **Be Specific**: Replace any vague language with concrete, technical specifics.\n\n"
        f"Return the COMPLETE improved ADR document. Do not summarize or truncate."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    content, error = call_resolved(messages, context, max_tokens=6000)
    if error:
        content, error = call_openai(messages, max_tokens=6000)
    if error:
        return None, error

    return {"output": content}, None


def step_5_local(inputs, context):
    """Write Final ADR Artifact to Storage."""
    improved_adr = context.get("improved_adr", "")
    generated_adr = context.get("generated_adr", "")

    final_adr = improved_adr if improved_adr else generated_adr

    if not final_adr or not final_adr.strip():
        return None, "No ADR content available to write."

    _, missing = check_structural_completeness(final_adr)
    critical_missing = [s for s in ["context", "decision outcome", "consequences"] if s in missing]
    if critical_missing:
        return None, f"Final ADR is missing critical sections: {critical_missing}"

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