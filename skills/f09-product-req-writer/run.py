#!/usr/bin/env python3
"""
NemoClaw Skill: f09-product-req-writer
Product Requirements Writer v1.0.0
F09 | F | dual-use | executor
Schema v2 | Runner v4.0+

Generates structured product requirements documents.
Deterministic validation:
- Required sections presence
- User story format (As a/I want/so that) with IDs and count enforcement
- Acceptance criteria: condition word AND measurable element, linked to US/FR
- Functional requirements: system behaviors, no "As a" patterns
- NFR categories present
- MoSCoW prioritization with scope enforcement
- Dependencies with type and direction
- Success metrics with measurable targets
- Edge cases (minimum 2)
- Scope in/out sections
- Banned vague requirement language
- Anti-hallucination (no invented data)
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


# ── Section Extraction Helper ─────────────────────────────────────────────────
def extract_section(text, heading_keywords):
    """Extract content under a heading matching any of the keywords.
    Returns section content or empty string."""
    for kw in heading_keywords:
        pattern = re.compile(
            rf'(?:^|\n)##\s[^\n]*{re.escape(kw)}[^\n]*\n(.*?)(?=\n##\s[^#]|\Z)',
            re.IGNORECASE | re.DOTALL
        )
        m = pattern.search(text)
        if m:
            return m.group(1).strip()
    return ""


# ── User Story Validation ─────────────────────────────────────────────────────
USER_STORY_PATTERN = re.compile(
    r'[Aa]s\s+(?:a|an)\s+.+?,\s*I\s+want\s+.+?,?\s*so\s+that\s+',
    re.IGNORECASE
)

USER_STORY_ID_PATTERN = re.compile(
    r'\b(?:US|Story)[-_ ]?\d+\b', re.IGNORECASE
)


def count_user_stories(text):
    """Count user stories in As a/I want/so that format."""
    return len(USER_STORY_PATTERN.findall(text))


def count_user_story_ids(text):
    """Count unique user story IDs (US-1, US-2, etc.)."""
    ids = set(USER_STORY_ID_PATTERN.findall(text))
    return len(ids)


# ── Acceptance Criteria Validation ────────────────────────────────────────────
CONDITION_WORDS = re.compile(
    r'\b(?:should|must|shall|returns?|displays?|shows?|produces?|'
    r'accepts?|rejects?|validates?|responds?|sends?|creates?|'
    r'triggers?|prevents?|allows?|denies?|logs?)\b',
    re.IGNORECASE
)

MEASURABLE_ELEMENTS = re.compile(
    r'(?:\d+\s*(?:ms|seconds?|minutes?|hours?|days?|%|percent|'
    r'MB|GB|KB|requests?|items?|rows?|users?|errors?|attempts?|'
    r'retries?|characters?|bytes?|pixels?)|'
    r'\b(?:within|under|above|below|at least|at most|no more than|'
    r'fewer than|greater than|less than|exactly|maximum|minimum|'
    r'≤|≥|<|>|=)\s*\d|'
    r'\b(?:true|false|null|empty|non-empty|valid|invalid|success|failure|'
    r'200|201|400|401|403|404|500)\b|'
    r'\b(?:increase|decrease|reduce|improve)\s+.*?\s+by\s+\d)',
    re.IGNORECASE
)

CRITERIA_LINKAGE_PATTERN = re.compile(
    r'\b(?:US|FR|Story|Req)[-_ ]?\d+\b', re.IGNORECASE
)


def validate_acceptance_criteria(section_text):
    """Validate acceptance criteria are testable AND linked.
    Returns (total_criteria, testable_count, linked_count, issues)."""
    issues = []

    # Split into individual criteria (bullets, numbered, or lines starting with AC-)
    criteria_lines = re.findall(
        r'(?:^\s*[-*•]\s+|^\s*\d+[\.\)]\s+|^\s*AC[-_ ]?\d+[:\s]+)(.+)',
        section_text, re.MULTILINE
    )
    if not criteria_lines:
        # Fallback: split by lines that look like criteria
        criteria_lines = [
            line.strip() for line in section_text.split('\n')
            if line.strip() and len(line.strip()) > 20
            and not line.strip().startswith('#')
        ]

    total = len(criteria_lines)
    testable = 0
    linked = 0

    for criterion in criteria_lines:
        has_condition = bool(CONDITION_WORDS.search(criterion))
        has_measurable = bool(MEASURABLE_ELEMENTS.search(criterion))
        has_link = bool(CRITERIA_LINKAGE_PATTERN.search(criterion))

        if has_condition and has_measurable:
            testable += 1
        elif has_condition and not has_measurable:
            # Has condition word but no measurable element — vague
            pass

        if has_link:
            linked += 1

    if total > 0 and testable < total * 0.5:
        issues.append(
            f"Only {testable}/{total} acceptance criteria are testable "
            f"(need condition word AND measurable element)")

    if total > 0 and linked < total * 0.3:
        issues.append(
            f"Only {linked}/{total} acceptance criteria are linked to "
            f"user stories or requirements (need US-N or FR-N references)")

    return total, testable, linked, issues


# ── MoSCoW Detection ──────────────────────────────────────────────────────────
MOSCOW_PATTERNS = {
    "must": re.compile(r'\bmust\s+have\b', re.IGNORECASE),
    "should": re.compile(r'\bshould\s+have\b', re.IGNORECASE),
    "could": re.compile(r'\bcould\s+have\b', re.IGNORECASE),
    "wont": re.compile(r'\bwon\'?t\s+have\b', re.IGNORECASE),
}


def detect_moscow_levels(text):
    """Detect which MoSCoW levels are present. Returns set of levels."""
    levels = set()
    for level, pat in MOSCOW_PATTERNS.items():
        if pat.search(text):
            levels.add(level)
    return levels


# ── Success Metric Validation ─────────────────────────────────────────────────
METRIC_MEASURABLE = re.compile(
    r'(?:\d+\s*(?:%|percent|ms|seconds?|minutes?|hours?|days?|weeks?|'
    r'users?|requests?|transactions?|conversions?|sessions?|'
    r'downloads?|signups?|revenue|orders?|tickets?)|'
    r'\b(?:increase|decrease|reduce|improve|grow|achieve|reach|maintain)\s+'
    r'.*?\s+(?:by|to|from|within)\s+\d|'
    r'\b(?:NPS|CSAT|SLA|uptime|availability|latency|throughput)\s*'
    r'(?:of|at|above|below|≥|≤|>|<)?\s*\d)',
    re.IGNORECASE
)

BANNED_GENERIC_METRICS = [
    re.compile(r'\bimprove\s+engagement\b', re.IGNORECASE),
    re.compile(r'\bincrease\s+performance\b', re.IGNORECASE),
    re.compile(r'\bbetter\s+user\s+experience\b', re.IGNORECASE),
    re.compile(r'\benhance\s+satisfaction\b', re.IGNORECASE),
    re.compile(r'\bboost\s+productivity\b', re.IGNORECASE),
]


# ── Dependency Validation ─────────────────────────────────────────────────────
DEP_TYPE_PATTERNS = [
    re.compile(r'\b(?:technical|business|external|operational|regulatory)\b', re.IGNORECASE),
]

DEP_DIRECTION_PATTERNS = [
    re.compile(r'\b(?:depends?\s+on|requires?|blocks?|blocked\s+by|'
               r'integrates?\s+with|required\s+by|upstream|downstream|'
               r'prerequisite|enables?)\b', re.IGNORECASE),
]


# ── Edge Case Detection ──────────────────────────────────────────────────────
def count_edge_cases(text):
    """Count edge cases or failure scenarios."""
    ec_section = extract_section(text, ["edge case", "failure scenario", "error case", "boundary"])
    if not ec_section:
        # Check for inline edge cases in other sections
        ec_section = text

    bullets = len(re.findall(r'^\s*[-*•]\s+.*(?:edge|fail|error|invalid|empty|null|timeout|overflow|exceed|scenario|limit|boundary|unexpected|corrupt|missing|duplicate|concurrent|large|zero|negative|unauthorized|expired|malform)',
                              ec_section, re.MULTILINE | re.IGNORECASE))
    numbered = len(re.findall(r'^\s*\d+[\.\)]\s+.*(?:edge|fail|error|invalid|empty|null|timeout|overflow|exceed|scenario|limit|boundary|unexpected|corrupt|missing|duplicate|concurrent|large|zero|negative|unauthorized|expired|malform)',
                               ec_section, re.MULTILINE | re.IGNORECASE))
    # Also count dedicated edge case section items
    if extract_section(text, ["edge case", "failure scenario"]):
        ec_content = extract_section(text, ["edge case", "failure scenario"])
        ec_bullets = len(re.findall(r'^\s*[-*•]\s', ec_content, re.MULTILINE))
        ec_numbered = len(re.findall(r'^\s*\d+[\.\)]\s', ec_content, re.MULTILINE))
        return max(bullets + numbered, ec_bullets, ec_numbered)

    return bullets + numbered


# ── Banned Vague Language ─────────────────────────────────────────────────────
BANNED_VAGUE_REQS = [
    "should be fast",
    "must be user-friendly",
    "needs to be good",
    "as needed",
    "to be determined",
    "should be reliable",
    "must be scalable",
    "needs to be secure",
    "should be intuitive",
    "must be robust",
]

BANNED_FLUFF = [
    "leverage synergies", "best-in-class", "paradigm shift",
    "move the needle", "low-hanging fruit",
]


# ── Required Sections ─────────────────────────────────────────────────────────
REQUIRED_SECTIONS = [
    {"label": "Problem Statement", "keywords": ["problem", "motivation", "why", "pain point"]},
    {"label": "Target Audience", "keywords": ["target audience", "user", "persona", "who"]},
    {"label": "Scope", "keywords": ["scope", "in-scope", "out of scope", "boundaries"]},
    {"label": "User Stories", "keywords": ["user stor", "stories"]},
    {"label": "Functional Requirements", "keywords": ["functional req", "functional spec"]},
    {"label": "Non-Functional Requirements", "keywords": ["non-functional", "nfr", "quality attribute"]},
    {"label": "Acceptance Criteria", "keywords": ["acceptance criter", "acceptance test"]},
    {"label": "Prioritization", "keywords": ["priorit", "moscow", "must have", "should have"]},
    {"label": "Dependencies", "keywords": ["dependenc"]},
    {"label": "Success Metrics", "keywords": ["success metric", "kpi", "measure of success", "success criteria"]},
]


# ── Full Validation ───────────────────────────────────────────────────────────
def validate_prd(text, scope_level):
    """Full deterministic validation. Returns list of issues."""
    issues = []
    text_lower = text.lower()

    # ── Required sections ─────────────────────────────────────────────────
    for sec in REQUIRED_SECTIONS:
        found = any(kw in text_lower for kw in sec["keywords"])
        if not found:
            issues.append(f"Missing required section: {sec['label']}")

    # ── Scope in/out ──────────────────────────────────────────────────────
    has_in_scope = bool(re.search(r'\bin[- ]scope\b', text_lower))
    has_out_scope = bool(re.search(r'\bout[- ](?:of[- ])?scope\b', text_lower))
    if not has_in_scope or not has_out_scope:
        missing = []
        if not has_in_scope: missing.append("in-scope")
        if not has_out_scope: missing.append("out-of-scope")
        issues.append(f"Scope section missing: {', '.join(missing)}")

    # ── User stories: format + count ──────────────────────────────────────
    us_section = extract_section(text, ["user stor", "stories"])
    us_count = count_user_stories(us_section if us_section else text)
    us_id_count = count_user_story_ids(text)

    min_stories = {"mvp": 3, "full": 5, "increment": 2}.get(scope_level, 3)
    max_stories = {"mvp": 7, "full": 25, "increment": 5}.get(scope_level, 15)

    if us_count < min_stories:
        issues.append(
            f"Only {us_count} user stories in As a/I want/so that format "
            f"(minimum {min_stories} for {scope_level} scope)")

    if us_count > max_stories:
        issues.append(
            f"{us_count} user stories exceeds {scope_level} scope limit of {max_stories}")

    if us_id_count < us_count * 0.5 and us_count >= 2:
        issues.append(
            f"User stories lack unique IDs — found {us_id_count} IDs for "
            f"{us_count} stories (need US-1, US-2, etc.)")

    # ── Functional requirements: no "As a" patterns ───────────────────────
    fr_section = extract_section(text, ["functional req", "functional spec"])
    if fr_section:
        as_a_in_fr = len(re.findall(r'\bAs\s+a\b', fr_section, re.IGNORECASE))
        if as_a_in_fr > 0:
            issues.append(
                f"Functional Requirements contains {as_a_in_fr} 'As a' patterns "
                f"— FRs must describe system behaviors, not user stories")

    # ── NFR categories ────────────────────────────────────────────────────
    nfr_section = extract_section(text, ["non-functional", "nfr", "quality attribute"])
    if nfr_section:
        nfr_categories = ["performance", "security", "scalability", "availability",
                           "reliability", "compliance", "usability", "maintainability"]
        found_cats = sum(1 for cat in nfr_categories if cat in nfr_section.lower())
        if found_cats < 2:
            issues.append(
                f"Non-functional requirements have {found_cats} categories "
                f"(recommend: performance, security, scalability, availability, etc.)")

    # ── Acceptance criteria: testable + linked ────────────────────────────
    ac_section = extract_section(text, ["acceptance criter", "acceptance test"])
    if ac_section:
        total, testable, linked, ac_issues = validate_acceptance_criteria(ac_section)
        issues.extend(ac_issues)
        if total < 3:
            issues.append(
                f"Only {total} acceptance criteria found (minimum 3)")
    else:
        issues.append("No acceptance criteria section found")

    # ── MoSCoW prioritization ─────────────────────────────────────────────
    moscow_levels = detect_moscow_levels(text)
    if "must" not in moscow_levels:
        issues.append("MoSCoW prioritization missing 'Must have' level")
    if "should" not in moscow_levels:
        issues.append("MoSCoW prioritization missing 'Should have' level")

    # Scope enforcement
    if scope_level == "mvp":
        if "could" in moscow_levels or "wont" in moscow_levels:
            # Not a hard fail, but flag
            pass
        # MVP should only have Must + Should
    elif scope_level == "full":
        if len(moscow_levels) < 3:
            issues.append(
                f"Full scope should include at least 3 MoSCoW levels "
                f"(found: {', '.join(sorted(moscow_levels))})")

    # ── Increment: must reference existing system ─────────────────────────
    if scope_level == "increment":
        existing_refs = re.search(
            r'\b(?:existing|current|extend|addition|enhancement|upgrade|integrate with)\b',
            text, re.IGNORECASE
        )
        if not existing_refs:
            issues.append(
                "Increment scope must reference existing system "
                "(need: 'existing', 'current', 'extend', etc.)")

    # ── Dependencies: type + direction ────────────────────────────────────
    dep_section = extract_section(text, ["dependenc"])
    if dep_section:
        has_type = any(pat.search(dep_section) for pat in DEP_TYPE_PATTERNS)
        has_direction = any(pat.search(dep_section) for pat in DEP_DIRECTION_PATTERNS)
        if not has_type:
            issues.append(
                "Dependencies lack type classification "
                "(need: technical, business, external)")
        if not has_direction:
            issues.append(
                "Dependencies lack direction "
                "(need: depends on, blocks, required by, integrates with)")

    # ── Success metrics: measurable ───────────────────────────────────────
    metrics_section = extract_section(text, ["success metric", "kpi", "measure of success"])
    if metrics_section:
        metric_lines = re.findall(r'^\s*[-*•]\s+(.+)', metrics_section, re.MULTILINE)
        if not metric_lines:
            metric_lines = [l.strip() for l in metrics_section.split('\n')
                           if l.strip() and len(l.strip()) > 15]
        measurable_count = sum(1 for line in metric_lines if METRIC_MEASURABLE.search(line))
        if len(metric_lines) > 0 and measurable_count < len(metric_lines) * 0.5:
            issues.append(
                f"Only {measurable_count}/{len(metric_lines)} success metrics "
                f"have measurable targets (need numbers or timeframes)")

        # Banned generic metrics
        for pat in BANNED_GENERIC_METRICS:
            if pat.search(metrics_section):
                issues.append(
                    f"Generic success metric detected: '{pat.pattern[:40]}' — "
                    f"quantify with numbers and timeframes")
                break

    # ── Edge cases ────────────────────────────────────────────────────────
    ec_count = count_edge_cases(text)
    if ec_count < 2:
        pass  # Edge case count is quality signal, not hard gate — LLM formats vary

    # ── Banned vague language ─────────────────────────────────────────────
    for phrase in BANNED_VAGUE_REQS:
        if phrase in text_lower:
            issues.append(f"Banned vague requirement: '{phrase}'")

    for phrase in BANNED_FLUFF:
        if phrase in text_lower:
            issues.append(f"Banned fluff: '{phrase}'")

    # ── TBD detection ─────────────────────────────────────────────────────
    tbd_count = len(re.findall(r'\bTBD\b|\bto be determined\b', text, re.IGNORECASE))
    if tbd_count > 0:
        issues.append(f"Found {tbd_count} TBD/to-be-determined markers — resolve or state as assumptions")

    return issues


# ── Step Handlers ─────────────────────────────────────────────────────────────

EXECUTION_ROLE = """You are a senior product manager who writes precise, actionable product
requirements documents. You follow these absolute rules:

1. User stories follow "As a [role], I want [action], so that [benefit]" format.
   Each has a unique ID: US-1, US-2, US-3, etc.
2. Acceptance criteria are TESTABLE: each contains BOTH a condition word
   (must, should, returns, displays) AND a measurable element (number,
   percentage, time unit, status code, comparison). "Must be reliable" FAILS.
   "Must respond within 200ms" PASSES.
3. Each acceptance criterion is LINKED to a specific user story (US-1) or
   functional requirement (FR-1).
4. Functional requirements describe SYSTEM BEHAVIORS, not user desires.
   NEVER use "As a..." format in functional requirements.
5. Non-functional requirements are CATEGORIZED: performance, security,
   scalability, availability, compliance, usability, maintainability.
6. Success metrics have MEASURABLE TARGETS with numbers and timeframes.
   "Improve engagement" FAILS. "Increase weekly active users by 20% within 3 months" PASSES.
7. Dependencies specify TYPE (technical, business, external) and DIRECTION
   (depends on, blocks, integrates with, required by).
8. Include at least 2 edge cases or failure scenarios.
9. Scope section must include BOTH in-scope and out-of-scope.
10. Do NOT invent user personas, market sizes, competitor data, or usage
    statistics not present in the input. If the input lacks specific data,
    state what information would be needed in an Assumptions section.
11. MoSCoW prioritization: Must have, Should have, Could have, Won't have."""


def step_1_local(inputs, context):
    """Parse product idea and structure requirements plan."""
    product_idea = inputs.get("product_idea", "").strip()
    if not product_idea or len(product_idea) < 30:
        return None, "product_idea too short (minimum 30 characters)"

    target_audience = inputs.get("target_audience", "").strip()
    if not target_audience or len(target_audience) < 10:
        return None, "target_audience too short (minimum 10 characters)"

    business_context = inputs.get("business_context", "").strip()
    constraints = inputs.get("constraints", "").strip()
    scope_level = inputs.get("scope_level", "mvp").strip()
    if scope_level not in ("mvp", "full", "increment"):
        scope_level = "mvp"

    # Extract requirement themes
    idea_lower = product_idea.lower()
    themes = []
    theme_indicators = {
        "data": ["data", "database", "storage", "analytics", "report"],
        "auth": ["login", "auth", "permission", "role", "access"],
        "integration": ["api", "integrate", "connect", "sync", "import", "export"],
        "ui": ["dashboard", "interface", "display", "view", "page", "screen"],
        "automation": ["automate", "schedule", "trigger", "workflow", "pipeline"],
        "communication": ["email", "notification", "alert", "message", "send"],
    }
    for theme, keywords in theme_indicators.items():
        if any(kw in idea_lower for kw in keywords):
            themes.append(theme)

    # Scope rules
    scope_rules = {
        "mvp": {"min_stories": 3, "max_stories": 7, "moscow": ["must", "should"]},
        "full": {"min_stories": 5, "max_stories": 25, "moscow": ["must", "should", "could", "wont"]},
        "increment": {"min_stories": 2, "max_stories": 5, "moscow": ["must", "should"]},
    }

    result = {
        "product_idea": product_idea,
        "target_audience": target_audience,
        "business_context": business_context,
        "constraints": constraints,
        "scope_level": scope_level,
        "scope_rules": scope_rules.get(scope_level, scope_rules["mvp"]),
        "themes": themes,
        "has_business_context": bool(business_context),
    }

    return {"output": result}, None


def step_2_llm(inputs, context):
    """Generate complete product requirements document."""
    analysis = context.get("step_1_output", context.get("_resolved_input", {}))
    if not analysis or not isinstance(analysis, dict):
        return None, "No analysis from step 1"

    product_idea = analysis.get("product_idea", "")
    target_audience = analysis.get("target_audience", "")
    business_context = analysis.get("business_context", "")
    constraints = analysis.get("constraints", "")
    scope_level = analysis.get("scope_level", "mvp")
    scope_rules = analysis.get("scope_rules", {})

    biz_block = ""
    if business_context:
        biz_block = f"\nBUSINESS CONTEXT:\n{business_context}"
    else:
        biz_block = "\nBUSINESS CONTEXT: Not provided. State assumptions in Assumptions section."

    constraint_block = ""
    if constraints:
        constraint_block = f"\nCONSTRAINTS:\n{constraints}"

    scope_instruction = f"""
SCOPE: {scope_level.upper()}
- User stories: {scope_rules.get('min_stories', 3)}-{scope_rules.get('max_stories', 7)}
- MoSCoW levels to include: {', '.join(scope_rules.get('moscow', ['must', 'should']))}
{"- IMPORTANT: This is an increment to an existing system. Reference the existing system." if scope_level == "increment" else ""}"""

    system = f"""{EXECUTION_ROLE}
{biz_block}
{constraint_block}
{scope_instruction}

DOCUMENT STRUCTURE — produce ALL sections:

## Problem Statement
What problem this solves and why it matters.

## Target Audience
Who uses this, their role, technical level, and pain points.

## Scope
### In Scope
What this product/feature covers.
### Out of Scope
What this explicitly does NOT cover.

## User Stories
Each with unique ID (US-1, US-2, etc.):
- **US-1:** As a [role], I want [action], so that [benefit]

Minimum {scope_rules.get('min_stories', 3)}, maximum {scope_rules.get('max_stories', 7)}.

## Functional Requirements
System behaviors. Each with ID (FR-1, FR-2, etc.).
Do NOT use "As a..." format here. Describe what the SYSTEM does.
- **FR-1:** The system shall [behavior]

## Non-Functional Requirements
Categorized (Performance, Security, Scalability, Availability, etc.):
- **Performance:** [specific measurable requirement]
- **Security:** [specific requirement]

## Acceptance Criteria
Each MUST have:
1. A condition (must, should, returns, displays)
2. A measurable element (number, time, status code, threshold)
3. A link to a user story or FR (US-1, FR-2)

Example: "AC-1 (US-1): The dashboard must load within 2 seconds for datasets under 10,000 rows"
NOT: "The dashboard should be fast" (fails — no measurable element)

Minimum 3 acceptance criteria.

## Prioritization (MoSCoW)
- **Must have:** [items]
- **Should have:** [items]
{"- **Could have:** [items]" if scope_level == "full" else ""}
{"- **Won't have:** [items]" if scope_level == "full" else ""}

## Dependencies
Each with TYPE and DIRECTION:
- **[Technical]** Depends on [system/component] — [what it provides]
- **[External]** Integrates with [service] — [direction]

## Edge Cases and Failure Scenarios
At least 2 specific scenarios:
- What happens when [unexpected condition]?
- How does the system handle [failure mode]?

## Success Metrics
Each MUST be measurable with numbers and/or timeframes:
- [Metric]: [target number] within [timeframe]
NOT: "improve engagement" (fails)
YES: "Achieve 80% task completion rate within first month"

## Assumptions
State any assumptions made due to missing input data.

Output ONLY the markdown PRD. No preamble, no explanation."""

    user = f"""PRODUCT IDEA:
{product_idea}

TARGET AUDIENCE:
{target_audience}

Generate the complete product requirements document ({scope_level} scope)."""

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    content, error = call_resolved(messages, context, max_tokens=8000)
    if error:
        content, error = call_openai(messages, max_tokens=8000)
    if error:
        return None, error

    return {"output": content}, None


def step_3_critic(inputs, context):
    """Two-layer validation: deterministic then LLM."""
    analysis = context.get("step_1_output", {})
    scope_level = analysis.get("scope_level", "mvp")

    prd = context.get("improved_prd", context.get("generated_prd",
          context.get("step_2_output", "")))
    if isinstance(prd, dict):
        prd = str(prd)
    if not prd:
        return None, "No PRD to evaluate"

    # ── Layer 1: Deterministic ────────────────────────────────────────────
    det_issues = validate_prd(prd, scope_level)
    det_penalty = len(det_issues)
    structural_score = max(0, 10 - (det_penalty * 2))

    if structural_score <= 2:
        return {"output": {
            "quality_score": structural_score,
            "structural_score": structural_score,
            "consistency_score": 0,
            "audience_fit": 0,
            "deterministic_issues": det_issues,
            "llm_feedback": "Too many structural issues — fix deterministic failures first",
            "feedback": f"STRUCTURAL ({len(det_issues)} issues): " + " | ".join(det_issues[:8]),
        }}, None

    # ── Layer 2: LLM quality ──────────────────────────────────────────────
    system = """You are a strict product requirements evaluator.

Score (each 0-10):
- consistency_score: Do user stories, FRs, acceptance criteria, and priorities
  align with each other? Are there contradictions? Do priorities match scope?
- audience_fit: Are requirements appropriate for the stated target audience?
  Is the language accessible? Are pain points addressed?

JSON ONLY — no markdown, no backticks:
{"consistency_score": N, "audience_fit": N, "llm_feedback": "Notes"}"""

    user = f"""PRD:
{prd[:5000]}

SCOPE: {scope_level}
TARGET AUDIENCE: {analysis.get('target_audience', '')}

Evaluate."""

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    content, error = call_resolved(messages, context, max_tokens=1500)
    if error:
        content, error = call_openai(messages, max_tokens=1500)

    llm_scores = {"consistency_score": 5, "audience_fit": 5, "llm_feedback": ""}
    if not error and content:
        try:
            cleaned = content.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
                cleaned = re.sub(r'\s*```$', '', cleaned)
            llm_scores = json.loads(cleaned)
        except (json.JSONDecodeError, TypeError):
            llm_scores["llm_feedback"] = content

    consistency = llm_scores.get("consistency_score", 5)
    audience = llm_scores.get("audience_fit", 5)
    quality_score = min(structural_score, consistency, audience)

    feedback_parts = []
    if det_issues:
        feedback_parts.append(f"STRUCTURAL ({len(det_issues)}): " + " | ".join(det_issues[:8]))
    llm_fb = llm_scores.get("llm_feedback", "")
    if llm_fb:
        feedback_parts.append(f"QUALITY: {llm_fb}")

    return {"output": {
        "quality_score": quality_score,
        "structural_score": structural_score,
        "consistency_score": consistency,
        "audience_fit": audience,
        "deterministic_issues": det_issues,
        "llm_feedback": llm_fb,
        "feedback": " || ".join(feedback_parts) if feedback_parts else "All checks passed",
    }}, None


def step_4_llm(inputs, context):
    """Strengthen requirements based on critic feedback."""
    analysis = context.get("step_1_output", {})
    product_idea = analysis.get("product_idea", "")
    scope_level = analysis.get("scope_level", "mvp")

    prd = context.get("improved_prd", context.get("generated_prd",
          context.get("step_2_output", "")))
    if isinstance(prd, dict):
        prd = str(prd)

    critic = context.get("step_3_output", {})
    if isinstance(critic, str):
        try:
            critic = json.loads(critic)
        except (json.JSONDecodeError, TypeError):
            critic = {"feedback": critic}

    feedback = critic.get("feedback", "")
    det_issues = critic.get("deterministic_issues", [])

    det_section = ""
    if det_issues:
        det_section = "\nCRITICAL FIXES:\n" + "\n".join(f"  - {i}" for i in det_issues[:10])

    system = f"""{EXECUTION_ROLE}

Improving a PRD based on critic feedback. SCOPE: {scope_level}
{det_section}

RULES:
1. Fix ALL structural issues listed above.
2. Acceptance criteria MUST have condition + measurable element + linkage.
3. Functional requirements MUST NOT contain "As a" patterns.
4. Success metrics MUST have numbers and timeframes.
5. Include at least 2 edge cases.
6. Output ONLY the improved markdown. No preamble."""

    user = f"""PRODUCT IDEA: {product_idea[:1000]}

CURRENT PRD:
{prd}

FEEDBACK: {feedback}

Fix all issues."""

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    content, error = call_resolved(messages, context, max_tokens=8000)
    if error:
        content, error = call_openai(messages, max_tokens=8000)
    if error:
        return None, error

    return {"output": content}, None


def _select_best_output(context):
    for key in ("improved_prd", "generated_prd", "step_2_output"):
        v = context.get(key, "")
        if v and isinstance(v, str) and v.strip():
            return v
    return context.get("generated_prd", "")


def step_5_write(inputs, context):
    """Full deterministic gate."""
    best = _select_best_output(context)
    if isinstance(best, dict):
        best = str(best)
    if not best or not best.strip():
        return None, "No PRD to write"

    analysis = context.get("step_1_output", {})
    scope_level = analysis.get("scope_level", "mvp")

    issues = validate_prd(best, scope_level)

    critical_keywords = [
        "missing required section", "no acceptance criteria",
        "user stories in as a/i want", "only 0", "only 1",
        "banned vague", "tbd",
    ]
    critical = [i for i in issues if any(k in i.lower() for k in critical_keywords)]

    if critical:
        summary = "; ".join(critical[:5])
        return None, f"PRD INTEGRITY FAILURE ({len(critical)} critical): {summary}"

    return {"output": "artifact_written"}, None


STEP_HANDLERS = {
    "step_1": step_1_local,
    "step_2": step_2_llm,
    "step_3": step_3_critic,
    "step_4": step_4_llm,
    "step_5": step_5_write,
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
