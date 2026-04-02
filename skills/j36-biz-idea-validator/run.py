#!/usr/bin/env python3
"""
Skill: j36-biz-idea-validator
Version: 1.0.0
Family: F36
Domain: J
Tag: dual-use
Type: executor
Schema: 2
Runner: >=4.0.0

Business Idea Validator — structured validation with market viability,
competitive positioning, revenue feasibility, risk assessment, go/no-go
recommendation, and actionable next steps.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone



# ── LLM Helpers (routed through lib/routing.py — L-003 compliant) ────────────
def call_openai(messages, model=None, max_tokens=6000):
    from lib.routing import call_llm
    return call_llm(messages, task_class="complex_reasoning", max_tokens=max_tokens)

def call_anthropic(messages, model=None, max_tokens=6000):
    from lib.routing import call_llm
    return call_llm(messages, task_class="complex_reasoning", max_tokens=max_tokens)

def call_google(messages, model=None, max_tokens=6000):
    from lib.routing import call_llm
    return call_llm(messages, task_class="moderate", max_tokens=max_tokens)

def call_resolved(messages, context, max_tokens=6000):
    from lib.routing import call_llm
    return call_llm(messages, task_class="moderate", max_tokens=max_tokens)


REQUIRED_SECTIONS = [
    "Market Viability Assessment",
    "Competitive Positioning",
    "Revenue Model Feasibility",
    "Risk Assessment",
    "Go/No-Go Recommendation",
    "Actionable Next Steps",
]

SECTION_KEYWORDS = {
    "Market Viability Assessment": ["market viability", "tam", "sam", "som"],
    "Competitive Positioning": ["competitive positioning", "competitive analysis"],
    "Revenue Model Feasibility": ["revenue model", "revenue feasibility"],
    "Risk Assessment": ["risk assessment", "risk analysis"],
    "Go/No-Go Recommendation": ["go/no-go", "recommendation"],
    "Actionable Next Steps": ["next steps", "actionable"],
}


def extract_section(text, heading_keywords):
    for kw in heading_keywords:
        pattern = re.compile(
            rf'(?:^|\n)##\s[^\n]*{re.escape(kw)}[^\n]*\n(.*?)(?=\n##\s[^#]|\Z)',
            re.IGNORECASE | re.DOTALL)
        m = pattern.search(text)
        if m:
            return m.group(1).strip()
    return ""


def count_bullet_items(section_text):
    """Count bullet/numbered list items in a section."""
    count = 0
    for line in section_text.strip().split("\n"):
        stripped = line.strip()
        if re.match(r'^[-*+]\s', stripped) or re.match(r'^\d+[.)]\s', stripped):
            count += 1
    return count


def check_estimate_grounding(text):
    """Check that numeric claims have grounding or [ESTIMATE] tags."""
    numeric_patterns = re.findall(
        r'\$[\d,.]+\s*(?:billion|million|trillion|B|M|T|K)',
        text, re.IGNORECASE
    )
    ungrounded = []
    for match in numeric_patterns:
        idx = text.find(match)
        surrounding = text[max(0, idx - 200):idx + len(match) + 200].lower()
        has_grounding = any(tag in surrounding for tag in [
            "[estimate", "estimate]", "assumption", "based on", "derived from",
            "according to", "source:", "data from", "[data gap", "data gap]",
        ])
        if not has_grounding:
            ungrounded.append(match)
    return ungrounded


def check_risk_categories(section_text):
    """Check for presence of categorized risks."""
    categories = ["market", "technical", "financial", "regulatory", "operational"]
    found = []
    lower = section_text.lower()
    for cat in categories:
        if cat in lower:
            found.append(cat)
    return found


# ---------------------------------------------------------------------------
# Step 1: Parse inputs and build validation plan (local)
# ---------------------------------------------------------------------------

def step_1_local(inputs, context):
    """Parse inputs and build validation plan."""
    business_idea = inputs.get("business_idea", "")
    target_market = inputs.get("target_market", "")
    competitive_landscape = inputs.get("competitive_landscape", "")
    scope = inputs.get("scope", "standard").lower().strip()
    revenue_model_hints = inputs.get("revenue_model_hints", "")
    known_constraints = inputs.get("known_constraints", "")

    if not business_idea or len(business_idea.strip()) < 50:
        return None, "business_idea is required and must be at least 50 characters."
    if not target_market or len(target_market.strip()) < 30:
        return None, "target_market is required and must be at least 30 characters."
    if not competitive_landscape or len(competitive_landscape.strip()) < 30:
        return None, "competitive_landscape is required and must be at least 30 characters."

    if scope not in SCOPE_RANGES:
        scope = "standard"

    min_items, max_items = SCOPE_RANGES[scope]

    all_input_text = (
        f"{business_idea} {target_market} {competitive_landscape} "
        f"{revenue_model_hints} {known_constraints}"
    )
    numeric_tokens = re.findall(
        r'\$[\d,.]+\s*(?:billion|million|trillion|B|M|T|K)?'
        r'|\d+(?:,\d{3})*(?:\.\d+)?%'
        r'|\d+(?:,\d{3})+',
        all_input_text, re.IGNORECASE
    )

    plan = {
        "scope": scope,
        "min_items": min_items,
        "max_items": max_items,
        "token_budget": TOKEN_BUDGET[scope],
        "business_idea": business_idea.strip(),
        "target_market": target_market.strip(),
        "competitive_landscape": competitive_landscape.strip(),
        "revenue_model_hints": revenue_model_hints.strip(),
        "known_constraints": known_constraints.strip(),
        "input_numeric_tokens": numeric_tokens,
        "required_sections": REQUIRED_SECTIONS,
        "risk_categories": ["market", "technical", "financial", "regulatory", "operational"],
    }

    return {"output": plan}, None


# ---------------------------------------------------------------------------
# Step 2: Generate comprehensive business validation report (LLM)
# ---------------------------------------------------------------------------

def step_2_llm(inputs, context):
    """Generate comprehensive business validation report."""
    plan = context.get("step_1_output", {})
    if not plan or not isinstance(plan, dict):
        return None, "Missing step_1_output (validation plan)."

    scope = plan.get("scope", "standard")
    min_items = plan.get("min_items", 5)
    max_items = plan.get("max_items", 10)
    business_idea = plan.get("business_idea", "")
    target_market = plan.get("target_market", "")
    competitive_landscape = plan.get("competitive_landscape", "")
    revenue_model_hints = plan.get("revenue_model_hints", "")
    known_constraints = plan.get("known_constraints", "")
    input_numeric_tokens = plan.get("input_numeric_tokens", [])
    token_budget = plan.get("token_budget", 8000)

    system_prompt = (
        "You are a rigorous business analyst and venture strategist specializing in "
        "early-stage idea validation. You combine market sizing discipline "
        "(TAM/SAM/SOM with three-path sizing: top-down, bottom-up, value-theory), "
        "competitive analysis frameworks, and revenue model feasibility assessment. "
        "You never fabricate market data — all figures must be grounded in provided "
        "inputs or explicitly flagged as estimates with stated assumptions. You produce "
        "structured, actionable validation reports that give founders and stakeholders "
        "clear go/no-go signals backed by specific findings.\n\n"
        "OUTPUT FORMAT: Produce a markdown document with exactly six H2 (##) sections "
        "in the order specified. Each section must contain bullet-point items as specified "
        "by the scope. Every numeric claim must either trace to input data, be tagged "
        "[ESTIMATE: <assumption>], or be tagged [DATA GAP: <what is missing>]. "
        "Do NOT invent competitor names not mentioned in the competitive landscape input. "
        "Do NOT present speculation as fact — state uncertainty explicitly."
    )

    if input_numeric_tokens:
        numeric_grounding_note = (
            f"\n\nNUMERIC DATA FROM INPUTS (use these as grounding anchors): "
            f"{', '.join(input_numeric_tokens)}\n"
            "Any market size figures, revenue projections, or financial estimates NOT "
            "derived from these inputs MUST be tagged with [ESTIMATE: <stated assumption>] "
            "or [DATA GAP: <what data is missing>]."
        )
    else:
        numeric_grounding_note = (
            "\n\nNO NUMERIC DATA PROVIDED IN INPUTS. Therefore ALL market size figures, "
            "revenue projections, and financial estimates MUST be tagged with "
            "[ESTIMATE: <stated assumption>] or [DATA GAP: <what data is missing>]. "
            "Do NOT present any number as fact."
        )

    constraints_section = ""
    if known_constraints:
        constraints_section = f"\n\nKNOWN CONSTRAINTS:\n{known_constraints}"

    revenue_hints_section = ""
    if revenue_model_hints:
        revenue_hints_section = f"\n\nREVENUE MODEL HINTS:\n{revenue_model_hints}"

    user_prompt = f"""Generate a comprehensive business idea validation report in markdown format.

BUSINESS IDEA:
{business_idea}

TARGET MARKET:
{target_market}

COMPETITIVE LANDSCAPE:
{competitive_landscape}{revenue_hints_section}{constraints_section}{numeric_grounding_note}

SCOPE: {scope} (produce {min_items}-{max_items} bullet-point items per section where applicable)

REQUIRED OUTPUT STRUCTURE (use exactly these H2 headings in this order):

## Market Viability Assessment
- Provide TAM (Total Addressable Market), SAM (Serviceable Addressable Market), SOM (Serviceable Obtainable Market)
- Apply three-path sizing methodology explicitly labeled: **Top-Down**, **Bottom-Up**, and **Value-Theory**
- Each path must show its derivation chain or be tagged [ESTIMATE: assumption] with stated assumptions
- Include {min_items}-{max_items} specific market viability factors as bullet points
- Conclude with a market viability score (1-10) and summary paragraph

## Competitive Positioning
- Analyze {min_items}-{max_items} competitive dimensions as bullet points
- Map the idea's positioning relative to competitors mentioned in the input
- Identify differentiation opportunities and competitive moats
- Include a competitive advantage assessment summary
- Do NOT invent competitor names not present in the competitive landscape input

## Revenue Model Feasibility
- Analyze the proposed/suggested revenue model(s) based on the hints provided (or common models if none provided)
- Provide revenue grounding: numeric projections must include derivation chain, or be tagged [ESTIMATE], or acknowledge [DATA GAP]
- Assess unit economics feasibility with specific metrics
- Evaluate pricing strategy viability
- Include {min_items}-{max_items} specific feasibility factors as bullet points

## Risk Assessment
- Categorize risks into exactly these five categories with explicit category labels: **Market**, **Technical**, **Financial**, **Regulatory**, **Operational**
- Provide {min_items}-{max_items} specific risks total across all five categories as bullet points
- Rate each risk: likelihood (high/medium/low) and impact (high/medium/low)
- Suggest mitigation strategies for each high-priority risk (high likelihood OR high impact)
- Every category must have at least one risk identified

## Go/No-Go Recommendation
- State one of exactly these three verdicts in bold at the start: **GO**, **CONDITIONAL GO**, or **NO-GO**
- Link the recommendation to specific findings from the Market Viability, Competitive Positioning, Revenue Model, and Risk Assessment sections by referencing them explicitly
- List the top 3-5 factors driving the recommendation as bullet points
- State specific conditions that would change the recommendation

## Actionable Next Steps
- Provide {min_items}-{max_items} specific, prioritized next steps as numbered items
- Each step must include: the action, owner/responsible party type, timeline estimate, and expected outcome
- Sequence steps logically: validation activities before scaling activities
- First steps should address the highest-priority risks and data gaps identified above

ANTI-FABRICATION RULES:
1. Every numeric claim must trace to input data OR be tagged [ESTIMATE: assumption] OR [DATA GAP: missing info]
2. Do not invent competitor names not mentioned in the competitive landscape input
3. Do not claim specific market research findings without grounding
4. When uncertain, explicitly state uncertainty rather than presenting speculation as fact"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    content, error = call_resolved(messages, context, max_tokens=token_budget)
    if error:
        content, error = call_openai(messages, max_tokens=token_budget)
    if error:
        return None, error

    if not content or len(content.strip()) < 200:
        return None, "LLM returned insufficient content for validation report."

    missing_sections = []
    for section_name, keywords in SECTION_KEYWORDS.items():
        section_text = extract_section(content, keywords)
        if not section_text or len(section_text) < 20:
            missing_sections.append(section_name)

    if len(missing_sections) >= 4:
        return None, f"Generated report missing too many sections: {', '.join(missing_sections)}"

    return {"output": content}, None


# ---------------------------------------------------------------------------
# Step 3: Evaluate validation report quality and grounding (critic)
# ---------------------------------------------------------------------------

def step_3_critic(inputs, context):
    """Evaluate validation report quality and grounding."""
    report = context.get("improved_validation", context.get("generated_validation", ""))
    if not report:
        report = context.get("step_2_output", "")
    if not report:
        return None, "No report found to evaluate."

    plan = context.get("step_1_output", {})
    scope = plan.get("scope", "standard") if isinstance(plan, dict) else "standard"
    min_items = SCOPE_RANGES.get(scope, (5, 10))[0]

    # --- Deterministic layer ---
    sections_found = {}
    sections_missing = []
    section_item_counts = {}

    for section_name, keywords in SECTION_KEYWORDS.items():
        section_text = extract_section(report, keywords)
        if section_text and len(section_text) > 20:
            sections_found[section_name] = True
            section_item_counts[section_name] = count_bullet_items(section_text)
        else:
            sections_found[section_name] = False
            sections_missing.append(section_name)
            section_item_counts[section_name] = 0

    sections_below_min = []
    for section_name, count in section_item_counts.items():
        if sections_found[section_name] and section_name not in ["Go/No-Go Recommendation"]:
            if count < min_items:
                sections_below_min.append(
                    f"{section_name}: {count} items (min {min_items})"
                )

    risk_section = extract_section(report, SECTION_KEYWORDS["Risk Assessment"])
    risk_cats_found = check_risk_categories(risk_section) if risk_section else []
    missing_risk_cats = [
        c for c in ["market", "technical", "financial", "regulatory", "operational"]
        if c not in risk_cats_found
    ]

    ungrounded_numbers = check_estimate_grounding(report)

    gonogo_section = extract_section(report, SECTION_KEYWORDS["Go/No-Go Recommendation"])
    has_recommendation = False
    if gonogo_section:
        lower_gonogo = gonogo_section.lower()
        has_recommendation = any(
            kw in lower_gonogo for kw in ["go", "no-go", "conditional"]
        )

    market_section = extract_section(report, SECTION_KEYWORDS["Market Viability Assessment"])
    sizing_paths_found = []
    if market_section:
        lower_market = market_section.lower()
        for path in ["top-down", "bottom-up", "value-theory", "value theory"]:
            if path in lower_market:
                sizing_paths_found.append(path)

    # Structural score components
    section_presence_score = (
        (len(REQUIRED_SECTIONS) - len(sections_missing)) / len(REQUIRED_SECTIONS) * 10
    )
    risk_cat_score = (len(risk_cats_found) / 5) * 10
    grounding_penalty = min(len(ungrounded_numbers) * 1.5, 5)
    sizing_path_score = min(len(sizing_paths_found) / 3 * 10, 10)
    item_count_penalty = min(len(sections_below_min) * 1.0, 4)
    recommendation_penalty = 0 if has_recommendation else 2

    structural_score = round(max(1, min(10,
        (section_presence_score * 0.3 +
         risk_cat_score * 0.15 +
         sizing_path_score * 0.15 +
         10 * 0.4) - grounding_penalty - item_count_penalty - recommendation_penalty
    )), 1)

    # --- LLM layer ---
    system_prompt = (
        "You are a senior business validation quality assessor with expertise in "
        "market sizing methodology, competitive analysis, and venture due diligence. "
        "You evaluate business idea validation reports for analytical rigor and "
        "actionability. You are strict about grounding — numeric claims without "
        "derivation chains or explicit [ESTIMATE]/[DATA GAP] tags are penalized. "
        "You check that recommendations are linked to specific findings, not generic advice. "
        "Score two dimensions on a 1-10 scale with specific justification."
    )

    truncated_report = report[:6000]

    user_prompt = f"""Evaluate this business idea validation report for quality:

---REPORT START---
{truncated_report}
---REPORT END---

EVALUATION CRITERIA:

1. **analytical_rigor** (1-10): How well-grounded are the market sizing, revenue projections, and risk assessments?
   - Are TAM/SAM/SOM figures derived via three-path sizing (top-down, bottom-up, value-theory)?
   - Are numeric claims supported by derivation chains, input data references, or properly tagged as [ESTIMATE] or [DATA GAP]?
   - Are all five risk categories (market, technical, financial, regulatory, operational) covered?
   - Are risk ratings (likelihood/impact) provided for each risk?
   - Score 8-10: All paths present with derivations, risks fully categorized and rated, numbers grounded
   - Score 5-7: Most elements present but some gaps in derivation or categorization
   - Score 1-4: Major gaps in methodology, ungrounded numbers, missing risk categories

2. **actionability** (1-10): How specific and useful are the recommendations and next steps?
   - Does the go/no-go recommendation explicitly state GO, CONDITIONAL GO, or NO-GO?
   - Is the recommendation linked to specific findings from earlier sections (not generic)?
   - Are next steps concrete with actions, owners, timelines, and expected outcomes?
   - Are next steps sequenced logically (validation before scaling)?
   - Score 8-10: Clear verdict linked to findings, concrete next steps with all four elements
   - Score 5-7: Verdict present but linkage weak, next steps partially specified
   - Score 1-4: No clear verdict, generic advice, vague next steps

Return ONLY valid JSON (no markdown fences):
{{"analytical_rigor": <1-10>, "actionability": <1-10>, "feedback": "<2-4 sentences of specific improvement suggestions referencing exact sections and issues>"}}"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    content, error = call_resolved(messages, context, max_tokens=1500)
    if error:
        content, error = call_openai(messages, max_tokens=1500)
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
            "analytical_rigor": 3,
            "actionability": 3,
            "feedback": "Could not parse LLM critic response — defaulting to low scores.",
        }

    analytical_rigor = max(1, min(10, scores.get("analytical_rigor", 5)))
    actionability = max(1, min(10, scores.get("actionability", 5)))
    llm_feedback = scores.get("feedback", "")

    quality_score = min(structural_score, analytical_rigor, actionability)

    deterministic_issues = []
    if sections_missing:
        deterministic_issues.append(
            f"Missing sections: {', '.join(sections_missing)}"
        )
    if sections_below_min:
        deterministic_issues.append(
            f"Sections below minimum item count: {'; '.join(sections_below_min)}"
        )
    if missing_risk_cats:
        deterministic_issues.append(
            f"Missing risk categories: {', '.join(missing_risk_cats)}"
        )
    if ungrounded_numbers:
        deterministic_issues.append(
            f"Ungrounded numeric claims (need [ESTIMATE] or [DATA GAP] tags): "
            f"{', '.join(ungrounded_numbers[:5])}"
        )
    if len(sizing_paths_found) < 3:
        deterministic_issues.append(
            f"Three-path sizing incomplete. Found: "
            f"{', '.join(sizing_paths_found) if sizing_paths_found else 'none'}. "
            f"Need: top-down, bottom-up, value-theory."
        )
    if not has_recommendation:
        deterministic_issues.append(
            "Go/No-Go section missing clear GO/NO-GO/CONDITIONAL GO recommendation."
        )

    combined_feedback = ""
    if deterministic_issues:
        combined_feedback += "STRUCTURAL ISSUES:\n" + "\n".join(
            f"- {i}" for i in deterministic_issues
        )
    if llm_feedback:
        combined_feedback += f"\n\nLLM FEEDBACK:\n{llm_feedback}"

    result = {
        "output": {
            "quality_score": quality_score,
            "structural_score": structural_score,
            "analytical_rigor": analytical_rigor,
            "actionability": actionability,
            "sections_found": [k for k, v in sections_found.items() if v],
            "sections_missing": sections_missing,
            "sections_below_min": sections_below_min,
            "missing_risk_categories": missing_risk_cats,
            "ungrounded_numbers_count": len(ungrounded_numbers),
            "sizing_paths_found": sizing_paths_found,
            "has_recommendation": has_recommendation,
            "feedback": combined_feedback,
        }
    }

    return result, None


# ---------------------------------------------------------------------------
# Step 4: Improve validation report from critic feedback (LLM)
# ---------------------------------------------------------------------------

def step_4_llm(inputs, context):
    """Improve validation report based on critic feedback."""
    report = context.get("improved_validation", context.get("generated_validation", ""))
    if not report:
        report = context.get("step_2_output", "")
    if not report:
        return None, "No report found to improve."

    critic_output = context.get("step_3_output", {})
    if isinstance(critic_output, str):
        try:
            critic_output = json.loads(critic_output)
        except json.JSONDecodeError:
            critic_output = {}

    feedback = critic_output.get("feedback", "No specific feedback available.")
    quality_score = critic_output.get("quality_score", 5)

    plan = context.get("step_1_output", {})
    scope = plan.get("scope", "standard") if isinstance(plan, dict) else "standard"
    min_items = SCOPE_RANGES.get(scope, (5, 10))[0]
    max_items = SCOPE_RANGES.get(scope, (5, 10))[1]
    token_budget = TOKEN_BUDGET.get(scope, 8000)

    input_numeric_tokens = plan.get("input_numeric_tokens", []) if isinstance(plan, dict) else []

    system_prompt = (
        "You are a rigorous business analyst and venture strategist specializing in "
        "early-stage idea validation. You combine market sizing discipline "
        "(TAM/SAM/SOM with three-path sizing: top-down, bottom-up, value-theory), "
        "competitive analysis frameworks, and revenue model feasibility assessment. "
        "You never fabricate market data — all figures must be grounded in provided "
        "inputs or explicitly flagged as estimates with stated assumptions. You produce "
        "structured, actionable validation reports that give founders and stakeholders "
        "clear go/no-go signals backed by specific findings.\n\n"
        "You are now IMPROVING an existing validation report based on specific critic "
        "feedback. Fix every identified issue while preserving existing good content. "
        "Output the complete improved report in markdown format with all six H2 sections."
    )

    if input_numeric_tokens:
        numeric_note = (
            f"\nGrounding anchors from inputs: {', '.join(input_numeric_tokens)}\n"
            "Numbers derived from these anchors do not need [ESTIMATE] tags. "
            "All other numeric claims MUST be tagged."
        )
    else:
        numeric_note = (
            "\nNo numeric data was provided in inputs — ALL numbers must be tagged "
            "[ESTIMATE: <assumption>] or [DATA GAP: <what is missing>]."
        )

    user_prompt = f"""Improve the following business idea validation report based on the critic feedback below.

CURRENT QUALITY SCORE: {quality_score}/10
SCOPE: {scope} ({min_items}-{max_items} items per section)
{numeric_note}

CRITIC FEEDBACK:
{feedback}

CURRENT REPORT:
---REPORT START---
{report}
---REPORT END---

IMPROVEMENT INSTRUCTIONS (address every issue in the feedback):
1. Maintain all six required H2 sections in this exact order:
   ## Market Viability Assessment
   ## Competitive Positioning
   ## Revenue Model Feasibility
   ## Risk Assessment
   ## Go/No-Go Recommendation
   ## Actionable Next Steps

2. Market Viability Assessment MUST include three explicitly labeled sizing paths:
   **Top-Down**, **Bottom-Up**, and **Value-Theory** — each with derivation chain or [ESTIMATE] tag

3. Risk Assessment MUST cover all five categories with explicit labels:
   **Market**, **Technical**, **Financial**, **Regulatory**, **Operational**
   Each risk must have likelihood (high/medium/low) and impact (high/medium/low) ratings

4. Tag ALL numeric claims with [ESTIMATE: assumption] or [DATA GAP: missing info]
   unless directly derived from input data grounding anchors

5. Go/No-Go section MUST start with one of: **GO**, **CONDITIONAL GO**, or **NO-GO**
   and link the verdict to specific findings from earlier sections by name

6. Actionable Next Steps must be numbered with action, owner type, timeline, and expected outcome

7. Each section must have {min_items}-{max_items} bullet-point items

8. Do NOT remove existing good content — only add, fix, or enhance

Output the complete improved report in markdown format."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    content, error = call_resolved(messages, context, max_tokens=token_budget)
    if error:
        content, error = call_openai(messages, max_tokens=token_budget)
    if error:
        return None, error

    if not content or len(content.strip()) < 200:
        return None, "LLM returned insufficient content for improved report."

    return {"output": content}, None


# ---------------------------------------------------------------------------
# Step 5: Write final validation artifact to disk (local)
# ---------------------------------------------------------------------------

def step_5_local(inputs, context):
    """Write final validation artifact to disk."""
    improved = context.get("improved_validation", "")
    step4_output = context.get("step_4_output", "")
    generated = context.get("generated_validation", "")
    step2_output = context.get("step_2_output", "")

    report = improved or step4_output or generated or step2_output

    if not report or not isinstance(report, str) or len(report.strip()) < 100:
        return None, "No valid report available for artifact writing."

    missing = []
    for section_name, keywords in SECTION_KEYWORDS.items():
        section_text = extract_section(report, keywords)
        if not section_text or len(section_text) < 20:
            missing.append(section_name)

    if len(missing) >= 2:
        return None, f"VALIDATION REPORT INTEGRITY FAILURE ({len(missing)} critical): Missing sections: {', '.join(missing)}"

    return {"output": "artifact_written"}, None


# ---------------------------------------------------------------------------
# Step handlers mapping
# ---------------------------------------------------------------------------

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