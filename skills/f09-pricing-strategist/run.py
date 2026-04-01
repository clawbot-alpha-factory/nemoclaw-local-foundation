#!/usr/bin/env python3
"""
NemoClaw Skill: f09-pricing-strategist
Pricing Strategy Analyst v1.0.0
F09 | F | dual-use | executor
Schema v2 | Runner v4.0+

Generates complete pricing strategy documents.
Deterministic validation:
- Required sections presence (8 sections)
- Pricing model explicitly named from known list
- Tier/plan structure: 2+ tiers, each with name + price + features
- Tier differentiation: adjacent tiers must have different feature sets
- Revenue grounding: 2+ numeric tokens from input OR derivation language OR
  insufficient-data acknowledgment
- Competitive reference: competitors from input appear in output
- Pricing goals addressed when provided
- Anti-hallucination: no ungrounded research claims
- Assumptions: 2+ items related to pricing logic
- Scope-specific: initial_launch (max 3 tiers, concrete price), mature (3-5 tiers),
  pivot (references prior state)
- Value-based fallback when cost_structure missing
- Banned vague phrases (penalty, not hard-fail)
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
    """Extract content under a heading matching any of the keywords."""
    for kw in heading_keywords:
        pattern = re.compile(
            rf'(?:^|\n)##\s[^\n]*{re.escape(kw)}[^\n]*\n(.*?)(?=\n##\s[^#]|\Z)',
            re.IGNORECASE | re.DOTALL
        )
        m = pattern.search(text)
        if m:
            return m.group(1).strip()
    return ""


# ── Numeric Extraction (reused from i35 pattern) ─────────────────────────────
NUMERIC_PATTERNS = [
    r'\$[\d,]+(?:\.\d+)?(?:\s*[KkMmBb](?:illion)?)?',
    r'[\d,]+(?:\.\d+)?%',
    r'[\d,]+(?:\.\d+)?\s*(?:users?|seats?|customers?|subscribers?|companies|people)',
    r'[\d,]+(?:\.\d+)?\s*(?:per\s+(?:month|year|user|seat|unit))',
    r'[\d,]+(?:\.\d+)?\s*(?:\/(?:mo|yr|month|year|user|seat))',
    r'(?:^|\s)[\d,]+(?:\.\d+)?(?:\s|$)',
]


def extract_numeric_tokens(text):
    if not text:
        return set()
    tokens = set()
    for pattern in NUMERIC_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            normalized = re.sub(r'[,\s]', '', match.group().strip())
            tokens.add(normalized.lower())
    for match in re.finditer(r'[\d]+(?:\.[\d]+)?', text):
        tokens.add(match.group())
    return tokens


# ── Pricing Models ────────────────────────────────────────────────────────────
PRICING_MODELS = [
    "freemium", "tiered", "per-seat", "per-user", "usage-based",
    "flat-rate", "one-time", "subscription", "pay-as-you-go",
    "hybrid", "enterprise", "custom pricing", "value-based",
    "cost-plus", "penetration", "skimming", "dynamic",
]

RESEARCH_CLAIM_PATTERNS = [
    r"according to (?:market |industry )?research",
    r"studies show",
    r"industry data indicates",
    r"based on (?:market |industry )?analysis",
    r"research (?:shows|suggests|indicates|confirms)",
    r"market data (?:shows|suggests|indicates)",
    r"survey(?:s)? (?:show|indicate|suggest)",
]

BANNED_VAGUE_PHRASES = [
    "optimal pricing", "maximize value", "competitive advantage",
    "best-in-class", "world-class", "cutting-edge pricing",
    "leverage synergies", "paradigm shift", "game-changing pricing",
    "revolutionary pricing", "disruptive pricing model",
]

PIVOT_PRIOR_STATE_MARKERS = [
    "currently", "existing", "changing from", "migrating",
    "previous", "prior", "was previously", "legacy pricing",
    "old pricing", "replacing", "transitioning from",
    "customers currently", "subscribers currently",
]

REQUIRED_SECTION_KEYWORDS = [
    {"label": "Pricing Model", "keywords": ["pricing model"]},
    {"label": "Tier/Plan Structure", "keywords": ["tier", "plan structure", "plan"]},
    {"label": "Feature Mapping", "keywords": ["feature", "feature-to-tier", "feature mapping"]},
    {"label": "Revenue Projections", "keywords": ["revenue", "projection", "forecast"]},
    {"label": "Competitive Positioning", "keywords": ["competitive", "positioning", "competitor"]},
    {"label": "Risks", "keywords": ["risk", "limitation"]},
    {"label": "Implementation", "keywords": ["implementation", "rollout", "launch plan"]},
    {"label": "Assumptions", "keywords": ["assumption"]},
]

TIER_KEYWORDS = [
    "tier", "plan", "free", "starter", "basic", "pro",
    "premium", "enterprise", "business", "growth",
    "professional", "team", "individual", "standard",
    "plus", "advanced", "scale", "custom"
]


# ── Tier Extraction ───────────────────────────────────────────────────────────
def extract_tiers(text):
    tiers = []
    current_tier = None
    current_content = []

    for line in text.split("\n"):
        tier_match = re.match(
            r'^#{2,4}\s+(?:Tier\s+\d+[:\s]*|Plan[:\s]*)?(.+)',
            line, re.IGNORECASE
        )
        if tier_match and any(kw in line.lower() for kw in TIER_KEYWORDS):
            if current_tier:
                tiers.append({"name": current_tier, "content": "\n".join(current_content)})
            current_tier = tier_match.group(1).strip()
            current_content = []
        elif current_tier:
            current_content.append(line)

    if current_tier:
        tiers.append({"name": current_tier, "content": "\n".join(current_content)})
    return tiers


def check_tier_has_price(tier_content, tier_name):
    lower = tier_content.lower() + " " + tier_name.lower()
    if re.search(r'\$\s*[\d,]+', tier_content):
        return True, "numeric"
    if "free" in tier_name.lower():
        return True, "free"
    if "free" in lower and any(w in lower for w in ["tier", "plan", "$0", "no cost"]):
        return True, "free"
    if any(w in lower for w in ["custom", "contact", "quote", "negotiat"]):
        return True, "custom"
    if re.search(r'(?:price|cost|fee)[:\s]*[\d,]+', lower):
        return True, "numeric"
    return False, None


def check_tier_differentiation(tiers):
    if len(tiers) < 2:
        return False, "fewer than 2 tiers detected"
    feature_sets = []
    for tier in tiers:
        features = set()
        for line in tier["content"].split("\n"):
            line = line.strip()
            if line.startswith(("-", "*", "•")) or re.match(r'^\d+\.', line):
                features.add(line.strip("- *•0123456789.").strip().lower())
        feature_sets.append(features)
    for i in range(len(feature_sets) - 1):
        if feature_sets[i] and feature_sets[i + 1]:
            if feature_sets[i] == feature_sets[i + 1]:
                return False, f"tiers '{tiers[i]['name']}' and '{tiers[i+1]['name']}' have identical features"
    return True, "tiers differentiated"


# ── Revenue Grounding ─────────────────────────────────────────────────────────
def check_revenue_grounding(text, input_numeric_tokens):
    revenue_section = extract_section(text, ["revenue", "projection", "forecast"])
    if not revenue_section:
        return False, "no revenue projections section found", 0

    grounding_count = 0
    for token in input_numeric_tokens:
        raw_nums = re.findall(r'[\d]+(?:\.[\d]+)?', token)
        for num in raw_nums:
            if num in revenue_section:
                grounding_count += 1

    derivation_markers = [
        "based on", "derived from", "calculated from", "assuming",
        "given the", "from the input", "at .* per", "multiplied by",
        "times", "divided by",
    ]
    has_derivation = any(
        re.search(marker, revenue_section, re.IGNORECASE)
        for marker in derivation_markers
    )

    insufficient_markers = [
        "insufficient data", "limited data", "not enough data",
        "without detailed cost", "without specific cost",
        "estimates should be validated", "rough estimate",
        "these projections are illustrative",
    ]
    has_insufficient_ack = any(
        marker in revenue_section.lower()
        for marker in insufficient_markers
    )

    ok = grounding_count >= 2 or has_derivation or has_insufficient_ack
    return ok, f"grounding={grounding_count}, derivation={has_derivation}, ack={has_insufficient_ack}", grounding_count


# ── Research Claims ───────────────────────────────────────────────────────────
def check_research_claims(text, competitive_context):
    violations = []
    for pattern in RESEARCH_CLAIM_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            if competitive_context:
                window = text[max(0, match.start()-200):match.end()+200].lower()
                comp_words = set(competitive_context.lower().split())
                overlap = sum(1 for w in comp_words if w in window and len(w) > 3)
                if overlap >= 2:
                    continue
            violations.append(match.group())
    return violations


# ── Assumptions Quality ───────────────────────────────────────────────────────
def check_assumptions(text):
    section = extract_section(text, ["assumption"])
    if not section:
        return False, 0
    items = [
        line.strip() for line in section.split("\n")
        if line.strip().startswith(("-", "*", "•")) or re.match(r'^\d+\.', line.strip())
    ]
    return len(items) >= 2, len(items)


# ── Scope Rules ───────────────────────────────────────────────────────────────
def check_scope_rules(text, scope, tiers):
    issues = []
    if scope == "initial_launch":
        if len(tiers) > 3:
            issues.append(f"initial_launch max 3 tiers, found {len(tiers)}")
        has_numeric = any(
            check_tier_has_price(t["content"], t["name"])[1] == "numeric"
            for t in tiers
        )
        if not has_numeric and tiers:
            issues.append("initial_launch requires at least one tier with a concrete numeric price")
    elif scope == "mature":
        if len(tiers) < 3:
            issues.append(f"mature scope needs 3-5 tiers, found {len(tiers)}")
    elif scope == "pivot":
        lower = text.lower()
        if not any(m in lower for m in PIVOT_PRIOR_STATE_MARKERS):
            issues.append("pivot must reference prior state (currently, existing, changing from, etc.)")
    return issues


# ── Full Deterministic Validation ─────────────────────────────────────────────
def validate_pricing(text, analysis):
    """Full deterministic validation. Returns list of issues."""
    issues = []
    text_lower = text.lower()

    # 1. Required sections
    for sec in REQUIRED_SECTION_KEYWORDS:
        found = any(kw in text_lower for kw in sec["keywords"])
        if not found:
            issues.append(f"Missing required section: {sec['label']}")

    # 2. Pricing model named
    model_found = any(m in text_lower for m in PRICING_MODELS)
    if not model_found:
        issues.append("No pricing model explicitly named")

    # 3. Tier structure
    tiers = extract_tiers(text)
    if len(tiers) < 2:
        issues.append(f"Need at least 2 tiers/plans, found {len(tiers)}")
    else:
        for tier in tiers:
            has_price, _ = check_tier_has_price(tier["content"], tier["name"])
            if not has_price:
                issues.append(f"Tier '{tier['name']}' missing price indicator")
        diff_ok, diff_msg = check_tier_differentiation(tiers)
        if not diff_ok:
            issues.append(f"Tier differentiation: {diff_msg}")

    # 4. Revenue grounding
    input_text = (analysis.get("cost_structure", "") or "") + " " + (analysis.get("target_market", "") or "")
    input_tokens = extract_numeric_tokens(input_text)
    grounding_ok, grounding_msg, _ = check_revenue_grounding(text, input_tokens)
    if not grounding_ok:
        issues.append(f"Revenue not grounded: {grounding_msg}")

    # 5. Research claims
    violations = check_research_claims(text, analysis.get("competitive_context", ""))
    if violations:
        issues.append(f"Ungrounded research claims: {violations}")

    # 6. Competitive reference
    comp_ctx = analysis.get("competitive_context", "")
    if comp_ctx:
        comp_words = set(w.lower() for w in comp_ctx.split() if len(w) > 3)
        if not any(w in text_lower for w in comp_words):
            issues.append("Competitive context provided but no competitors referenced")

    # 7. Pricing goals addressed
    goals = analysis.get("pricing_goals", "")
    if goals:
        goal_words = set(w.lower() for w in goals.split() if len(w) > 3)
        if not any(w in text_lower for w in goal_words):
            issues.append("Pricing goals not addressed")

    # 8. Assumptions
    assumptions_ok, assumption_count = check_assumptions(text)
    if not assumptions_ok:
        issues.append(f"Assumptions: need 2+, found {assumption_count}")

    # 9. Scope rules
    scope = analysis.get("scope", "initial_launch") or "initial_launch"
    scope_issues = check_scope_rules(text, scope, tiers)
    issues.extend(scope_issues)

    # 10. Value-based fallback
    if not analysis.get("cost_structure"):
        if "value-based" not in text_lower and "value based" not in text_lower:
            issues.append("No cost_structure but output doesn't mention value-based pricing")

    # 11. Banned vague phrases (tracked but not hard-fail)
    vague_found = [p for p in BANNED_VAGUE_PHRASES if p in text_lower]

    return issues, vague_found, len(tiers)


# ── Execution Role ────────────────────────────────────────────────────────────
EXECUTION_ROLE = """You are a senior pricing strategist who produces precise, grounded
pricing strategy documents. Every pricing recommendation is tied to provided input
data. Every tier has a clear target audience, price point, and differentiated
feature set. Revenue projections reference actual input numbers or clearly derived
computations — never purely invented figures. When cost_structure is missing, you
explicitly switch to value-based pricing. When making assumptions, you state them
clearly and tie each assumption to the pricing logic it influences. You never
reference external research unless it was explicitly provided in the input."""


# ── Step Handlers ─────────────────────────────────────────────────────────────

def step_1_local(inputs, context):
    """Parse product context and identify pricing dimensions."""
    product = inputs.get("product_description", "").strip()
    if not product or len(product) < 30:
        return None, "product_description must be at least 30 characters"

    market = inputs.get("target_market", "").strip()
    if not market or len(market) < 20:
        return None, "target_market must be at least 20 characters"

    cost = inputs.get("cost_structure", "").strip()
    competitive = inputs.get("competitive_context", "").strip()
    goals = inputs.get("pricing_goals", "").strip()
    scope = inputs.get("scope", "initial_launch").strip()
    if scope not in ("initial_launch", "mature", "pivot"):
        scope = "initial_launch"

    lower = (product + " " + market).lower()
    signals = {
        "b2b": any(w in lower for w in ["b2b", "business", "enterprise", "company", "companies", "organization"]),
        "b2c": any(w in lower for w in ["b2c", "consumer", "individual", "personal", "people"]),
        "saas": any(w in lower for w in ["saas", "software", "platform", "subscription", "cloud", "app"]),
        "one_time": any(w in lower for w in ["one-time", "single purchase", "lifetime", "perpetual"]),
        "per_seat": any(w in lower for w in ["per-seat", "per-user", "per seat", "per user", "per member"]),
        "usage_based": any(w in lower for w in ["usage", "metered", "per-call", "per-request", "pay-as-you-go"]),
    }

    has_cost = bool(cost)
    has_competitive = bool(competitive)
    has_goals = bool(goals)

    scope_rules = {
        "initial_launch": {"max_tiers": 3, "require_numeric_price": True},
        "mature": {"max_tiers": 5, "min_tiers": 3},
        "pivot": {"require_prior_state_ref": True},
    }

    result = {
        "product_description": product,
        "target_market": market,
        "cost_structure": cost,
        "competitive_context": competitive,
        "pricing_goals": goals,
        "scope": scope,
        "signals": signals,
        "has_cost_structure": has_cost,
        "has_competitive_context": has_competitive,
        "has_pricing_goals": has_goals,
        "pricing_mode": "cost-plus capable" if has_cost else "value-based (no cost data)",
        "input_numeric_tokens": list(extract_numeric_tokens(cost + " " + market)),
        "scope_rules": scope_rules.get(scope, scope_rules["initial_launch"]),
    }

    return {"output": result}, None


def step_2_llm(inputs, context):
    """Generate complete pricing strategy."""
    analysis = context.get("step_1_output", context.get("_resolved_input", {}))
    if not analysis or not isinstance(analysis, dict):
        return None, "No analysis from step 1"

    product = analysis.get("product_description", "")
    market = analysis.get("target_market", "")
    cost = analysis.get("cost_structure", "")
    competitive = analysis.get("competitive_context", "")
    goals = analysis.get("pricing_goals", "")
    scope = analysis.get("scope", "initial_launch")
    signals = analysis.get("signals", {})
    pricing_mode = analysis.get("pricing_mode", "value-based")
    has_cost = analysis.get("has_cost_structure", False)

    scope_rules = {
        "initial_launch": "Max 3 tiers. Conservative revenue projections. Emphasize simplicity and market entry. At least one tier must have a concrete numeric price.",
        "mature": "Full tier structure (3-5 tiers including enterprise). Include expansion revenue (upsell/cross-sell). Address retention pricing.",
        "pivot": "Must reference what is changing and why. Include migration path for existing customers. Risk section must address churn. Use 'currently', 'existing', 'changing from' language.",
    }

    cost_instruction = ""
    if not has_cost:
        cost_instruction = (
            "\nCRITICAL: No cost_structure was provided. You MUST:\n"
            "1. Explicitly state that pricing is value-based due to missing cost data\n"
            "2. Use value-based pricing methodology\n"
            "3. State this limitation in the Assumptions section\n"
        )

    system = f"""{EXECUTION_ROLE}
{cost_instruction}

SCOPE: {scope.upper()}
SCOPE RULES: {scope_rules.get(scope, '')}

DETECTED SIGNALS: {json.dumps(signals)}
PRICING MODE: {pricing_mode}

REQUIRED SECTIONS (all must be present as markdown headings):
1. ## Pricing Model Recommendation — Name and justify the model
2. ## Tier/Plan Structure — Each tier: name, target audience, why it exists, specific price, included features. Differentiated.
3. ## Feature-to-Tier Mapping — Table or list showing features per tier
4. ## Revenue Projections — Ground ALL numbers in input data or clearly computed derivations. If data insufficient, state "insufficient data for precise projections". Reference at least 2 numbers from input.
5. ## Competitive Positioning — Address competitors from input (if provided).
6. ## Risks and Limitations — Specific risks, not generic.
7. ## Implementation Recommendations — How to roll out pricing.
8. ## Assumptions — Each: (a) relates to pricing logic, (b) states which section it influences.

RULES:
- Do NOT reference external research unless provided in input
- Higher tiers: price anchoring logic (value justification or competitor comparison)
- For initial_launch: at least one concrete numeric price (not just "contact us")
- For pivot: reference prior/existing state
- Adjacent tiers must have differentiated features
- Revenue must reference input cost/market data or state limitations"""

    user = f"""PRODUCT: {product}

TARGET MARKET: {market}

COST STRUCTURE: {cost or 'NOT PROVIDED — use value-based pricing'}

COMPETITIVE CONTEXT: {competitive or 'NOT PROVIDED'}

PRICING GOALS: {goals or 'NOT PROVIDED'}

Generate the complete pricing strategy document ({scope} scope)."""

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

    pricing = context.get("improved_pricing", context.get("generated_pricing",
              context.get("step_2_output", "")))
    if isinstance(pricing, dict):
        pricing = str(pricing)
    if not pricing:
        return None, "No pricing strategy to evaluate"

    # ── Layer 1: Deterministic ────────────────────────────────────────────
    det_issues, vague_found, tier_count = validate_pricing(pricing, analysis)
    det_penalty = len(det_issues) + len(vague_found) * 0.5
    structural_score = max(0, 10 - (det_penalty * 1.5))

    if structural_score <= 2:
        return {"output": {
            "quality_score": structural_score,
            "structural_score": structural_score,
            "strategic_coherence": 0,
            "grounding_quality": 0,
            "deterministic_issues": det_issues,
            "vague_phrases": vague_found,
            "llm_feedback": "Too many structural issues — fix deterministic failures first",
            "feedback": f"STRUCTURAL ({len(det_issues)} issues): " + " | ".join(det_issues[:8]),
        }}, None

    # ── Layer 2: LLM quality ──────────────────────────────────────────────
    system = """You are a pricing strategy reviewer. Score (each 0-10):
- strategic_coherence: Does the pricing model match the product? Are tiers logical?
  Does each tier have a clear target audience and justification? Is price anchoring used?
- grounding_quality: Are revenue projections grounded in provided data? Are assumptions
  tied to pricing logic? Is value justification present?

JSON ONLY — no markdown, no backticks:
{"strategic_coherence": N, "grounding_quality": N, "llm_feedback": "Notes"}"""

    user = f"""PRICING STRATEGY:
{pricing[:5000]}

SCOPE: {analysis.get('scope', 'initial_launch')}
COST DATA PROVIDED: {analysis.get('has_cost_structure', False)}

Evaluate."""

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    content, error = call_resolved(messages, context, max_tokens=1500)
    if error:
        content, error = call_openai(messages, max_tokens=1500)

    llm_scores = {"strategic_coherence": 5, "grounding_quality": 5, "llm_feedback": ""}
    if not error and content:
        try:
            cleaned = content.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
                cleaned = re.sub(r'\s*```$', '', cleaned)
            llm_scores = json.loads(cleaned)
        except (json.JSONDecodeError, TypeError):
            llm_scores["llm_feedback"] = content

    coherence = llm_scores.get("strategic_coherence", 5)
    grounding = llm_scores.get("grounding_quality", 5)
    quality_score = min(structural_score, coherence, grounding)

    feedback_parts = []
    if det_issues:
        feedback_parts.append(f"STRUCTURAL ({len(det_issues)}): " + " | ".join(det_issues[:8]))
    if vague_found:
        feedback_parts.append(f"VAGUE ({len(vague_found)}): " + ", ".join(vague_found))
    llm_fb = llm_scores.get("llm_feedback", "")
    if llm_fb:
        feedback_parts.append(f"QUALITY: {llm_fb}")

    return {"output": {
        "quality_score": quality_score,
        "structural_score": structural_score,
        "strategic_coherence": coherence,
        "grounding_quality": grounding,
        "deterministic_issues": det_issues,
        "vague_phrases": vague_found,
        "llm_feedback": llm_fb,
        "feedback": " || ".join(feedback_parts) if feedback_parts else "All checks passed",
        "tier_count": tier_count,
    }}, None


def step_4_llm(inputs, context):
    """Strengthen pricing strategy based on critic feedback."""
    analysis = context.get("step_1_output", {})
    product = analysis.get("product_description", "")
    scope = analysis.get("scope", "initial_launch")

    pricing = context.get("improved_pricing", context.get("generated_pricing",
              context.get("step_2_output", "")))
    if isinstance(pricing, dict):
        pricing = str(pricing)

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

Improving a pricing strategy based on critic feedback. SCOPE: {scope}
{det_section}

RULES:
1. Fix ALL structural issues listed above.
2. Every tier must have target audience + justification + differentiated features.
3. Revenue projections must reference input data.
4. Assumptions must tie to pricing logic they influence.
5. Higher tiers need price anchoring.
6. If no cost data: explicitly use value-based pricing language.
7. Do NOT add external research references.
8. Output ONLY the improved markdown. No preamble."""

    user = f"""PRODUCT: {product[:1000]}

CURRENT PRICING STRATEGY:
{pricing}

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
    for key in ("improved_pricing", "generated_pricing", "step_2_output"):
        v = context.get(key, "")
        if v and isinstance(v, str) and v.strip():
            return v
    return context.get("generated_pricing", "")


def step_5_write(inputs, context):
    """Full deterministic gate."""
    best = _select_best_output(context)
    if isinstance(best, dict):
        best = str(best)
    if not best or not best.strip():
        return None, "No pricing strategy to write"

    analysis = context.get("step_1_output", {})

    issues, vague_found, tier_count = validate_pricing(best, analysis)

    critical_keywords = [
        "missing required section", "no pricing model",
        "need at least 2 tier", "fewer than 2",
        "revenue not grounded", "pivot must reference",
    ]
    critical = [i for i in issues if any(k in i.lower() for k in critical_keywords)]

    if critical:
        summary = "; ".join(critical[:5])
        return None, f"PRICING INTEGRITY FAILURE ({len(critical)} critical): {summary}"

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
