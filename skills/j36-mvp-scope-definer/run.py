#!/usr/bin/env python3
"""
Skill: j36-mvp-scope-definer
Version: 1.0.0
Family: F36
Domain: J
Tag: dual-use
Type: executor
Schema: 2
Runner: >=4.0.0

MVP Scope Definer — produces structured MVP scope documents with MoSCoW
prioritization, user journey maps, technical boundaries, launch criteria,
risk-adjusted timelines, out-of-scope sections, and resource allocation.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Environment loader
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# LLM call functions
# ---------------------------------------------------------------------------
def call_openai(messages, model="gpt-4.1-mini", max_tokens=4000):
    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage, SystemMessage
        env = load_env()
        llm = ChatOpenAI(
            model=model,
            max_tokens=max_tokens,
            api_key=env.get("OPENAI_API_KEY", ""),
        )
        lc = [
            SystemMessage(content=m["content"]) if m["role"] == "system"
            else HumanMessage(content=m["content"])
            for m in messages
        ]
        return llm.invoke(lc).content, None
    except Exception as e:
        return None, f"openai error: {e}"


def call_anthropic(messages, model="claude-sonnet-4-20250514", max_tokens=4000):
    try:
        from langchain_anthropic import ChatAnthropic
        from langchain_core.messages import HumanMessage, SystemMessage
        env = load_env()
        llm = ChatAnthropic(
            model=model,
            max_tokens=max_tokens,
            api_key=env.get("ANTHROPIC_API_KEY", ""),
        )
        lc = [
            SystemMessage(content=m["content"]) if m["role"] == "system"
            else HumanMessage(content=m["content"])
            for m in messages
        ]
        return llm.invoke(lc).content, None
    except Exception as e:
        return None, f"anthropic error: {e}"


def call_google(messages, model="gemini-2.5-flash", max_tokens=4000):
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import HumanMessage, SystemMessage
        env = load_env()
        llm = ChatGoogleGenerativeAI(
            model=model,
            max_tokens=max_tokens,
            google_api_key=env.get("GOOGLE_API_KEY", ""),
        )
        lc = [
            SystemMessage(content=m["content"]) if m["role"] == "system"
            else HumanMessage(content=m["content"])
            for m in messages
        ]
        return llm.invoke(lc).content, None
    except Exception as e:
        return None, f"google error: {e}"


def call_resolved(messages, context, max_tokens=4000):
    provider = context.get("resolved_provider", "openai")
    model = context.get("resolved_model", "")
    if provider == "anthropic":
        return call_anthropic(messages, model=model or "claude-sonnet-4-20250514", max_tokens=max_tokens)
    elif provider == "google":
        return call_google(messages, model=model or "gemini-2.5-flash", max_tokens=max_tokens)
    else:
        return call_openai(messages, model=model or "gpt-4.1-mini", max_tokens=max_tokens)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
EXECUTION_ROLE = (
    "You are a senior product strategist and MVP scoping expert with deep experience "
    "in lean product development. You define achievable MVP scopes by ruthlessly "
    "prioritizing features using MoSCoW methodology (Must Have, Should Have, Could Have, "
    "Won't Have). You structure output as markdown with exactly seven H2 sections: "
    "MoSCoW Feature Prioritization (with H3 subsections per category, each feature as a "
    "bullet with name, description, and effort estimate grounded in stated constraints), "
    "User Journey Map (numbered steps for Must Have features only, showing touchpoint, "
    "user action, system response, and the aha moment), Technical Scope Boundaries "
    "(explicit in-scope and out-of-scope technology decisions derived from constraints), "
    "Launch Criteria Checklist (5-12 binary pass/fail criteria covering functional, quality, "
    "and operational readiness), Risk-Adjusted Timeline (phase-based with durations traceable "
    "to resource constraints, 15-25% buffer, top 3 risks with mitigations), Out of Scope "
    "(deliberate exclusions with rationale and reconsideration timeline), and Resource "
    "Allocation (team/budget allocation across phases with gap analysis). You never "
    "fabricate timeline estimates — every date and duration must trace back to the stated "
    "resource constraints and timeline inputs. You ground every recommendation in the "
    "specific product, audience, and constraints provided."
)

SCOPE_MODE_RANGES = {
    "lean": (3, 5),
    "balanced": (5, 10),
    "comprehensive": (10, 15),
}

REQUIRED_SECTIONS = [
    "MoSCoW Feature Prioritization",
    "User Journey Map",
    "Technical Scope Boundaries",
    "Launch Criteria Checklist",
    "Risk-Adjusted Timeline",
    "Out of Scope",
    "Resource Allocation",
]

TOKEN_BUDGET = {
    "lean": 6000,
    "balanced": 8000,
    "comprehensive": 12000,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def extract_section(text, heading_keywords):
    """Extract a markdown section by heading keywords (H2 level)."""
    for kw in heading_keywords:
        pattern = re.compile(
            rf'(?:^|\n)##\s[^\n]*{re.escape(kw)}[^\n]*\n(.*?)(?=\n##\s[^#]|\Z)',
            re.IGNORECASE | re.DOTALL,
        )
        m = pattern.search(text)
        if m:
            return m.group(1).strip()
    return ""


def check_required_sections(text):
    """Return list of missing required sections."""
    missing = []
    for section in REQUIRED_SECTIONS:
        pattern = re.compile(
            rf'(?:^|\n)##\s[^\n]*{re.escape(section)}',
            re.IGNORECASE,
        )
        if not pattern.search(text):
            missing.append(section)
    return missing


def count_moscow_features(text):
    """Count features in MoSCoW section by category."""
    section = extract_section(text, ["MoSCoW", "Feature Prioritization"])
    counts = {"must": 0, "should": 0, "could": 0, "wont": 0, "total": 0}
    for category, keywords in [
        ("must", ["must have", "must-have"]),
        ("should", ["should have", "should-have"]),
        ("could", ["could have", "could-have", "nice to have"]),
        ("wont", ["won't have", "wont have", "won't-have", "will not have"]),
    ]:
        for kw in keywords:
            cat_pattern = re.compile(
                rf'(?:^|\n)###?\s[^\n]*{re.escape(kw)}[^\n]*\n(.*?)(?=\n###?\s|\n##\s|\Z)',
                re.IGNORECASE | re.DOTALL,
            )
            m = cat_pattern.search(section)
            if m:
                bullets = re.findall(r'^\s*[-*]\s+', m.group(1), re.MULTILINE)
                counts[category] = max(counts[category], len(bullets))
    counts["total"] = counts["must"] + counts["should"] + counts["could"] + counts["wont"]
    if counts["total"] == 0:
        all_bullets = re.findall(r'^\s*[-*]\s+', section, re.MULTILINE)
        counts["total"] = len(all_bullets)
    return counts


def check_timeline_grounding(text, resource_constraints, timeline):
    """Check if timeline section references resource constraints."""
    timeline_section = extract_section(text, ["Timeline", "Risk-Adjusted"])
    if not timeline_section:
        return False, "Timeline section not found"
    constraint_tokens = re.findall(r'\b\d+\b', resource_constraints)
    timeline_tokens = re.findall(r'\b\d+\b', timeline)
    grounding_tokens = constraint_tokens + timeline_tokens
    if not grounding_tokens:
        return True, "No numeric constraints to verify"
    found = sum(1 for t in grounding_tokens if t in timeline_section)
    ratio = found / len(grounding_tokens) if grounding_tokens else 0
    if ratio >= 0.3:
        return True, f"Grounding ratio: {ratio:.0%}"
    return False, f"Low grounding ratio: {ratio:.0%} — timeline may not reference stated constraints"


def check_launch_criteria(text):
    """Check launch criteria section has 5-12 binary criteria."""
    section = extract_section(text, ["Launch Criteria"])
    if not section:
        return 0, False
    numbered = re.findall(r'^\s*\d+[\.\)]\s+', section, re.MULTILINE)
    bullets = re.findall(r'^\s*[-*]\s+', section, re.MULTILINE)
    count = max(len(numbered), len(bullets))
    in_range = 5 <= count <= 12
    return count, in_range


# ---------------------------------------------------------------------------
# Step 1: Parse inputs and build scoping plan (local)
# ---------------------------------------------------------------------------
def step_1_local(inputs, context):
    """Parse inputs and build scoping plan."""
    product_idea = inputs.get("product_idea", "").strip()
    target_audience = inputs.get("target_audience", "").strip()
    resource_constraints = inputs.get("resource_constraints", "").strip()
    timeline = inputs.get("timeline", "").strip()

    errors = []
    if not product_idea or len(product_idea) < 30:
        errors.append("product_idea must be at least 30 characters describing the product and its core value proposition")
    if not target_audience or len(target_audience) < 20:
        errors.append("target_audience must be at least 20 characters describing demographics and pain points")
    if not resource_constraints or len(resource_constraints) < 15:
        errors.append("resource_constraints must be at least 15 characters specifying team size, budget, or infrastructure")
    if not timeline or len(timeline) < 10:
        errors.append("timeline must be at least 10 characters specifying target delivery timeframe")

    if errors:
        return None, f"Input validation failed: {'; '.join(errors)}"

    scope_mode = inputs.get("scope_mode", "balanced").strip().lower()
    if scope_mode not in SCOPE_MODE_RANGES:
        scope_mode = "balanced"

    domain_context = inputs.get("domain_context", "").strip()
    existing_assets = inputs.get("existing_assets", "").strip()

    feature_min, feature_max = SCOPE_MODE_RANGES[scope_mode]

    team_size_match = re.search(
        r'(\d+)\s*(?:developer|engineer|person|people|member|dev)',
        resource_constraints, re.IGNORECASE,
    )
    team_size = int(team_size_match.group(1)) if team_size_match else None

    budget_match = re.search(r'\$\s*([\d,]+(?:\.\d+)?[kKmM]?)', resource_constraints)
    budget_str = budget_match.group(1) if budget_match else None

    weeks_match = re.search(r'(\d+)\s*(?:week|wk)', timeline, re.IGNORECASE)
    months_match = re.search(r'(\d+)\s*(?:month|mo)', timeline, re.IGNORECASE)
    duration_weeks = None
    if weeks_match:
        duration_weeks = int(weeks_match.group(1))
    elif months_match:
        duration_weeks = int(months_match.group(1)) * 4

    scoping_plan = {
        "scope_mode": scope_mode,
        "feature_range": {"min": feature_min, "max": feature_max},
        "extracted_signals": {
            "team_size": team_size,
            "budget": budget_str,
            "duration_weeks": duration_weeks,
        },
        "has_domain_context": bool(domain_context),
        "has_existing_assets": bool(existing_assets),
        "product_idea": product_idea,
        "target_audience": target_audience,
        "resource_constraints": resource_constraints,
        "timeline": timeline,
        "domain_context": domain_context,
        "existing_assets": existing_assets,
        "token_budget": TOKEN_BUDGET.get(scope_mode, 8000),
    }

    return {"output": scoping_plan}, None


# ---------------------------------------------------------------------------
# Step 2: Generate comprehensive MVP scope document (LLM)
# ---------------------------------------------------------------------------
def step_2_llm(inputs, context):
    """Generate comprehensive MVP scope document."""
    plan = context.get("step_1_output", {})
    if not plan:
        return None, "Missing step_1_output (scoping plan)"

    scope_mode = plan.get("scope_mode", "balanced")
    feature_range = plan.get("feature_range", {"min": 5, "max": 10})
    signals = plan.get("extracted_signals", {})
    product_idea = plan.get("product_idea", "")
    target_audience = plan.get("target_audience", "")
    resource_constraints = plan.get("resource_constraints", "")
    timeline = plan.get("timeline", "")
    domain_context = plan.get("domain_context", "")
    existing_assets = plan.get("existing_assets", "")
    token_budget = plan.get("token_budget", 8000)

    system_prompt = EXECUTION_ROLE

    team_size_display = signals.get("team_size")
    if team_size_display is None:
        team_size_display = "not explicitly stated — infer from constraints"
    budget_display = signals.get("budget")
    if budget_display is None:
        budget_display = "not explicitly stated — infer from constraints"
    duration_display = signals.get("duration_weeks")
    if duration_display is None:
        duration_display = "not explicitly stated — infer from timeline"
    else:
        duration_display = f"{duration_display} weeks"

    constraint_summary = (
        f"\nEXTRACTED SIGNALS (use these to ground your estimates):\n"
        f"- Team size: {team_size_display}\n"
        f"- Budget: {budget_display}\n"
        f"- Duration: {duration_display}\n"
    )

    optional_blocks = ""
    if domain_context:
        optional_blocks += f"\n## Domain Context\n{domain_context}\n"
    if existing_assets:
        optional_blocks += f"\n## Existing Assets to Leverage\n{existing_assets}\n"

    user_prompt = f"""Generate a comprehensive MVP scope document for the following product.

## Product Idea
{product_idea}

## Target Audience
{target_audience}

## Resource Constraints
{resource_constraints}

## Timeline
{timeline}
{optional_blocks}{constraint_summary}

## Scope Mode: {scope_mode.upper()}
Feature count target: {feature_range['min']}-{feature_range['max']} features total across all MoSCoW categories.

---

Generate the MVP scope document with EXACTLY these seven H2 sections in this order:

## MoSCoW Feature Prioritization
- Organize features into exactly four subsections using H3 headings: ### Must Have, ### Should Have, ### Could Have, ### Won't Have
- Must Have = features without which the product has zero value; the absolute minimum viable set
- Should Have = important features that significantly enhance value but product works without them
- Could Have = nice-to-have features that improve UX or add polish; first to cut if time runs short
- Won't Have = features explicitly excluded from this MVP; acknowledged but deferred
- Each feature as a bullet with: **Feature Name** — one-line description. Effort: X person-days (grounded in stated team size and timeline)
- Total feature count across all four categories MUST be between {feature_range['min']} and {feature_range['max']}
- Must Have features should be no more than 40% of total features

## User Journey Map
- Map the core user flow from first touch to key value moment using ONLY Must Have features
- Use numbered steps in this format: **Step N: Touchpoint Name** — User action → System response
- Identify the "aha moment" where the user first experiences core value and mark it explicitly
- Include entry point, key interactions, and success state
- Do NOT map Should Have or Could Have features

## Technical Scope Boundaries
- **In Scope**: List specific languages, frameworks, infrastructure, APIs, and integrations needed
- **Out of Scope**: List deferred technical decisions with brief rationale
- **Technical Constraints**: Derive explicit constraints from the stated resource constraints (e.g., "With {team_size_display} engineers, we cannot build custom infrastructure — use managed services")
- If existing assets were provided, specify exactly how each integrates into the architecture

## Launch Criteria Checklist
- Numbered checklist of 5-12 measurable criteria that must ALL pass before launch
- Three categories: Functional (features work as specified), Quality (performance, security, accessibility), Operational (monitoring, deployment, rollback)
- Each criterion MUST be binary pass/fail with a specific measurable threshold
- Example format: "1. [Functional] User can complete signup flow end-to-end in under 60 seconds"
- No subjective criteria like "feels good" or "looks professional"

## Risk-Adjusted Timeline
- Phase-based timeline with these phases at minimum: Discovery/Planning, Build Sprint(s), QA/Testing, Launch Prep, Launch
- Each phase: duration in weeks/days, key deliverables, dependencies on previous phases, assigned resources
- EVERY duration MUST be mathematically traceable: e.g., "Build Sprint 1: 2 weeks (3 Must Have features × 3 person-days each ÷ {team_size_display} engineers = 9 person-days ÷ 5 days/week ≈ 2 weeks)"
- Include explicit buffer: 15-25% of total timeline, labeled as "Risk Buffer"
- Top 3 risks table: Risk | Probability (H/M/L) | Impact (H/M/L) | Mitigation | Schedule Impact

## Out of Scope
- Explicit list of features, capabilities, and technical work deliberately excluded from this MVP
- Each item format: **Item Name** — Rationale for exclusion. Reconsider: [specific milestone, e.g., "Post-MVP v1.1" or "After 1000 users"]
- Include at least: features from Won't Have, advanced versions of Must Have features, non-essential integrations
- This section is the primary scope creep prevention tool — be thorough and specific

## Resource Allocation
- Allocation table: Phase | Team Members | % of Budget | Key Activities
- If team composition is known, assign specific roles to phases
- If budget was specified, provide percentage breakdown across phases
- Identify resource gaps: skills or capacity needed but not available in stated constraints
- Recommend specific mitigations for gaps (hire, outsource, defer, simplify)

CRITICAL RULES:
1. Every timeline estimate MUST reference the stated constraints — never invent capacity numbers
2. Feature count MUST be within {feature_range['min']}-{feature_range['max']} total
3. All seven sections MUST be present with the EXACT H2 headings listed above
4. Be specific and actionable — a development team should be able to start work from this document
5. Ground everything in the specific product, audience, and constraints provided — no generic advice
6. Use markdown formatting consistently: H2 for sections, H3 for subsections, bullets for lists, bold for emphasis
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    content, error = call_resolved(messages, context, max_tokens=token_budget)
    if error:
        content, error = call_openai(messages, model="gpt-4.1-mini", max_tokens=token_budget)
    if error:
        return None, error

    return {"output": content}, None


# ---------------------------------------------------------------------------
# Step 3: Evaluate scope quality and grounding integrity (critic)
# ---------------------------------------------------------------------------
def step_3_critic(inputs, context):
    """Evaluate scope quality and grounding integrity."""
    generated_scope = context.get("generated_scope", "")
    if not generated_scope:
        return None, "Missing generated_scope (generated scope document)"

    plan = context.get("step_1_output", {})
    scope_mode = plan.get("scope_mode", "balanced")
    feature_range = plan.get("feature_range", {"min": 5, "max": 10})
    resource_constraints = plan.get("resource_constraints", "")
    timeline = plan.get("timeline", "")

    # --- Deterministic checks ---
    missing_sections = check_required_sections(generated_scope)
    section_score = max(1, 10 - len(missing_sections) * 2)

    feature_counts = count_moscow_features(generated_scope)
    total_features = feature_counts["total"]
    feature_in_range = feature_range["min"] <= total_features <= feature_range["max"]
    if feature_in_range:
        feature_score = 10
    else:
        midpoint = (feature_range["min"] + feature_range["max"]) // 2
        feature_score = max(1, 10 - abs(total_features - midpoint))

    grounded, grounding_note = check_timeline_grounding(
        generated_scope, resource_constraints, timeline,
    )
    grounding_score = 10 if grounded else 5

    launch_count, launch_in_range = check_launch_criteria(generated_scope)
    launch_score = 10 if launch_in_range else max(3, 10 - abs(launch_count - 8))

    structural_score = min(section_score, feature_score, grounding_score, launch_score)

    # --- LLM evaluation layer ---
    system_prompt = (
        "You are a senior product management reviewer specializing in MVP scope documents. "
        "You evaluate documents for completeness, actionability, and constraint grounding. "
        "You are critical but fair — you reward specificity and penalize vagueness. "
        "You check that MoSCoW categories are well-justified, timelines are mathematically "
        "traceable to stated constraints, launch criteria are binary and measurable, and "
        "the out-of-scope section is thorough enough to prevent scope creep."
    )

    user_prompt = f"""Evaluate this MVP scope document on three dimensions. Score each 1-10.

SCOPE MODE: {scope_mode} (expected {feature_range['min']}-{feature_range['max']} features)

RESOURCE CONSTRAINTS PROVIDED:
{resource_constraints}

TIMELINE PROVIDED:
{timeline}

--- MVP SCOPE DOCUMENT ---
{generated_scope}
--- END DOCUMENT ---

Evaluate on these three dimensions:

1. **prioritization_quality** (1-10):
   - Are Must Have features truly the minimum viable set? Would the product fail without each one?
   - Are Should/Could/Won't categories logically distinct and well-justified?
   - Is the feature count within the {feature_range['min']}-{feature_range['max']} range?
   - Does each feature have a clear effort estimate grounded in constraints?
   Score 8-10: Excellent prioritization with clear rationale. Score 4-7: Some features miscategorized or missing effort estimates. Score 1-3: Categories are arbitrary or features are vague.

2. **actionability** (1-10):
   - Could a development team start work TODAY from this document alone?
   - Are features specific enough to create user stories from?
   - Are launch criteria binary and measurable (not subjective)?
   - Is the user journey map concrete with specific touchpoints?
   Score 8-10: Ready for sprint planning. Score 4-7: Needs clarification on some items. Score 1-3: Too vague to act on.

3. **constraint_grounding** (1-10):
   - Do ALL timeline durations show their math (person-days ÷ team size = weeks)?
   - Are resource allocations realistic given the stated team/budget?
   - Do risks reference real constraints, not hypothetical ones?
   - Does the resource allocation section identify actual gaps?
   Score 8-10: Every estimate traceable. Score 4-7: Some estimates lack grounding. Score 1-3: Timeline appears fabricated.

Also provide:
- **weaknesses**: List of 3-5 specific, actionable weaknesses (quote the problematic text)
- **improvement_suggestions**: One specific suggestion per weakness

Return ONLY valid JSON (no markdown fences, no commentary):
{{
  "prioritization_quality": <int 1-10>,
  "actionability": <int 1-10>,
  "constraint_grounding": <int 1-10>,
  "weaknesses": ["...", "..."],
  "improvement_suggestions": ["...", "..."]
}}"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    content, error = call_resolved(messages, context, max_tokens=2000)
    if error:
        content, error = call_openai(messages, model="gpt-4.1-mini", max_tokens=2000)
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
            "prioritization_quality": 6,
            "actionability": 6,
            "constraint_grounding": 6,
            "weaknesses": ["Could not parse critic LLM response"],
            "improvement_suggestions": ["Re-run critic evaluation"],
        }

    prioritization_quality = max(1, min(10, int(scores.get("prioritization_quality", 6))))
    actionability = max(1, min(10, int(scores.get("actionability", 6))))
    constraint_grounding = max(1, min(10, int(scores.get("constraint_grounding", 6))))

    quality_score = min(structural_score, prioritization_quality, actionability, constraint_grounding)

    result = {
        "output": {
            "quality_score": quality_score,
            "structural_score": structural_score,
            "section_score": section_score,
            "feature_score": feature_score,
            "grounding_score": grounding_score,
            "launch_score": launch_score,
            "prioritization_quality": prioritization_quality,
            "actionability": actionability,
            "constraint_grounding": constraint_grounding,
            "missing_sections": missing_sections,
            "feature_counts": feature_counts,
            "feature_in_range": feature_in_range,
            "launch_criteria_count": launch_count,
            "launch_criteria_in_range": launch_in_range,
            "grounding_note": grounding_note,
            "weaknesses": scores.get("weaknesses", []),
            "improvement_suggestions": scores.get("improvement_suggestions", []),
        }
    }

    return result, None


# ---------------------------------------------------------------------------
# Step 4: Improve scope document from critic feedback (LLM)
# ---------------------------------------------------------------------------
def step_4_llm(inputs, context):
    """Improve scope document from critic feedback."""
    generated_scope = context.get("generated_scope", "")
    critic_output = context.get("step_3_output", {})

    if not generated_scope:
        return None, "Missing generated_scope for improvement"
    if not critic_output:
        return None, "Missing step_3_output (critic feedback)"

    plan = context.get("step_1_output", {})
    scope_mode = plan.get("scope_mode", "balanced")
    feature_range = plan.get("feature_range", {"min": 5, "max": 10})
    resource_constraints = plan.get("resource_constraints", "")
    timeline = plan.get("timeline", "")
    token_budget = plan.get("token_budget", 8000)

    quality_score = critic_output.get("quality_score", 5)
    weaknesses = critic_output.get("weaknesses", [])
    suggestions = critic_output.get("improvement_suggestions", [])
    missing_sections = critic_output.get("missing_sections", [])
    feature_in_range = critic_output.get("feature_in_range", True)
    feature_counts = critic_output.get("feature_counts", {})
    grounding_note = critic_output.get("grounding_note", "")
    grounding_score = critic_output.get("grounding_score", 10)
    launch_criteria_count = critic_output.get("launch_criteria_count", 0)
    launch_criteria_in_range = critic_output.get("launch_criteria_in_range", True)

    feedback_items = []

    if missing_sections:
        feedback_items.append(
            f"CRITICAL: The following required H2 sections are MISSING and must be added with "
            f"the exact headings: {', '.join(missing_sections)}"
        )

    if not feature_in_range:
        total = feature_counts.get("total", 0)
        feedback_items.append(
            f"CRITICAL: Feature count is {total}, but scope mode '{scope_mode}' requires "
            f"{feature_range['min']}-{feature_range['max']}. Add or remove features to fit range. "
            f"Current breakdown — Must: {feature_counts.get('must', 0)}, "
            f"Should: {feature_counts.get('should', 0)}, "
            f"Could: {feature_counts.get('could', 0)}, "
            f"Won't: {feature_counts.get('wont', 0)}"
        )

    if grounding_score < 8:
        feedback_items.append(
            f"IMPORTANT: Timeline grounding is weak ({grounding_note}). "
            f"Every duration estimate must show explicit math: person-days ÷ team size = weeks. "
            f"Reference these constraints: '{resource_constraints}' and timeline: '{timeline}'"
        )

    if not launch_criteria_in_range:
        feedback_items.append(
            f"IMPORTANT: Launch criteria count is {launch_criteria_count}, should be 5-12. "
            f"Each criterion must be binary pass/fail with a measurable threshold."
        )

    for w in weaknesses:
        feedback_items.append(f"WEAKNESS: {w}")

    for s in suggestions:
        feedback_items.append(f"SUGGESTION: {s}")

    feedback_block = "\n".join(f"- {item}" for item in feedback_items)

    system_prompt = EXECUTION_ROLE

    user_prompt = f"""Revise the following MVP scope document based on specific critic feedback.

## Critic Quality Score: {quality_score}/10

## Feedback to Address:
{feedback_block}

## Resource Constraints (for grounding all estimates):
{resource_constraints}

## Timeline (for grounding all estimates):
{timeline}

## Scope Mode: {scope_mode.upper()} ({feature_range['min']}-{feature_range['max']} features)

--- CURRENT MVP SCOPE DOCUMENT ---
{generated_scope}
--- END DOCUMENT ---

REVISION RULES:
1. Address EVERY piece of feedback above — do not skip any item
2. Preserve all content that was NOT criticized — do not remove good content
3. Ensure ALL seven required H2 sections are present with these EXACT headings:
   - ## MoSCoW Feature Prioritization (with ### Must Have, ### Should Have, ### Could Have, ### Won't Have)
   - ## User Journey Map
   - ## Technical Scope Boundaries
   - ## Launch Criteria Checklist (5-12 binary criteria)
   - ## Risk-Adjusted Timeline (with traceable math for every duration)
   - ## Out of Scope
   - ## Resource Allocation
4. Feature count MUST be within {feature_range['min']}-{feature_range['max']}
5. Every timeline estimate MUST show its math tracing to stated constraints
6. Output the COMPLETE revised document — not just the changed parts
7. Maintain consistent markdown formatting: H2 for sections, H3 for subsections, bullets for lists
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    content, error = call_resolved(messages, context, max_tokens=token_budget)
    if error:
        content, error = call_openai(messages, model="gpt-4.1-mini", max_tokens=token_budget)
    if error:
        return None, error

    return {"output": content}, None


# ---------------------------------------------------------------------------
# Step 5: Validate and finalize scope artifact (local)
# ---------------------------------------------------------------------------
def step_5_local(inputs, context):
    """Validate and finalize scope artifact."""
    improved_scope = context.get("step_4_output", "")
    generated_scope = context.get("generated_scope", "")

    final_scope = improved_scope if improved_scope else generated_scope

    if not final_scope:
        return None, "No scope document available to write"

    missing = check_required_sections(final_scope)
    if len(missing) > 2:
        return None, f"Final document missing too many required sections: {', '.join(missing)}"

    content_lines = [
        ln for ln in final_scope.split("\n")
        if ln.strip() and not ln.strip().startswith("#")
    ]
    if len(content_lines) < 20:
        return None, "Final document has insufficient content (fewer than 20 non-heading lines)"

    feature_counts = count_moscow_features(final_scope)
    if feature_counts["total"] == 0:
        return None, "Final document has no detectable features in MoSCoW section"

    return {"output": "artifact_written"}, None


# ---------------------------------------------------------------------------
# Step handlers registry
# ---------------------------------------------------------------------------
STEP_HANDLERS = {
    "step_1": step_1_local,
    "step_2": step_2_llm,
    "step_3": step_3_critic,
    "step_4": step_4_llm,
    "step_5": step_5_local,
}

# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
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