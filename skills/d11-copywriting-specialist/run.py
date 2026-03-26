#!/usr/bin/env python3
"""
NemoClaw Skill: d11-copywriting-specialist
Copywriting Specialist v1.0.0
F11 | D | customer-facing | executor
Schema v2 | Runner v4.0+

Generates polished, conversion-oriented marketing copy.
Deterministic validation:
- Format-specific required sections (landing_page, email, ad_copy, etc.)
- Single CTA enforcement (flag >2 distinct CTAs)
- Headline quality: benefit/hook markers required
- Persuasion mechanics: social proof, urgency, benefit stacking, objection handling
- Feature-benefit separation: flag feature-only bullets
- Banned filler phrases
- Anti-hallucination: fabricated testimonials, statistics
- Tone consistency check
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone


# ── Env + LLM Helpers ─────────────────────────────────────────────────────────
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


def call_openai(messages, model="gpt-5.4-mini", max_tokens=6000):
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, SystemMessage
    env = load_env()
    key = env.get("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
    if not key: return None, "OPENAI_API_KEY not found"
    llm = ChatOpenAI(model=model, api_key=key, max_tokens=max_tokens, temperature=0.4)
    lc = [SystemMessage(content=m["content"]) if m["role"] == "system" else HumanMessage(content=m["content"]) for m in messages]
    return llm.invoke(lc).content, None


def call_anthropic(messages, model="claude-sonnet-4-6", max_tokens=6000):
    from langchain_anthropic import ChatAnthropic
    from langchain_core.messages import HumanMessage, SystemMessage
    env = load_env()
    key = env.get("ANTHROPIC_API_KEY", os.environ.get("ANTHROPIC_API_KEY", ""))
    if not key: return None, "ANTHROPIC_API_KEY not found"
    llm = ChatAnthropic(model=model, api_key=key, max_tokens=max_tokens, temperature=0.4)
    lc = [SystemMessage(content=m["content"]) if m["role"] == "system" else HumanMessage(content=m["content"]) for m in messages]
    return llm.invoke(lc).content, None


def call_google(messages, model="gemini-2.5-flash", max_tokens=6000):
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.messages import HumanMessage, SystemMessage
    env = load_env()
    key = env.get("GOOGLE_API_KEY", os.environ.get("GOOGLE_API_KEY", ""))
    if not key: return None, "GOOGLE_API_KEY not found"
    llm = ChatGoogleGenerativeAI(model=model, google_api_key=key, max_tokens=max_tokens)
    lc = [SystemMessage(content=m["content"]) if m["role"] == "system" else HumanMessage(content=m["content"]) for m in messages]
    return llm.invoke(lc).content, None


def call_resolved(messages, context, max_tokens=6000):
    m = context.get("resolved_model", "")
    p = context.get("resolved_provider", "anthropic")
    if p == "google": return call_google(messages, model=m or "gemini-2.5-flash", max_tokens=max_tokens)
    if p == "openai": return call_openai(messages, model=m or "gpt-5.4-mini", max_tokens=max_tokens)
    return call_anthropic(messages, model=m or "claude-sonnet-4-6", max_tokens=max_tokens)


# ── H2-Scoped Section Extraction (lesson from e12-tech-trend-scanner) ─────────
def extract_section(text, heading_keywords):
    """Extract content under an H2 heading matching any keyword.
    Uses ##\\s (H2 only) — not H1 titles, preserves H3 subsections inside."""
    for kw in heading_keywords:
        pattern = re.compile(
            rf'(?:^|\n)##\s[^\n]*{re.escape(kw)}[^\n]*\n(.*?)(?=\n##\s[^#]|\Z)',
            re.IGNORECASE | re.DOTALL
        )
        m = pattern.search(text)
        if m:
            return m.group(1).strip()
    return ""


# ── Length-Driven Token Budget (lesson from e12-tech-trend-scanner) ────────────
TOKEN_BUDGET_BY_LENGTH = {
    "short": 4000,
    "standard": 8000,
    "long": 12000,
}


def _get_token_budget(copy_length):
    return TOKEN_BUDGET_BY_LENGTH.get(copy_length, 8000)


# ── Constants ─────────────────────────────────────────────────────────────────

FORMAT_REQUIRED_SECTIONS = {
    "landing_page": [
        {"label": "Hero Section", "keywords": ["hero", "headline"]},
        {"label": "Problem", "keywords": ["problem", "pain", "challenge", "frustrat"]},
        {"label": "Solution", "keywords": ["solution", "how it works", "introducing"]},
        {"label": "Benefits", "keywords": ["benefit", "why", "advantage", "what you get"]},
        {"label": "Social Proof", "keywords": ["proof", "testimonial", "trusted", "customer", "result"]},
        {"label": "Call to Action", "keywords": ["call to action", "cta", "get started", "start", "try"]},
    ],
    "email": [
        {"label": "Subject Line", "keywords": ["subject"]},
        {"label": "Opening Hook", "keywords": ["hook", "opening", "hi ", "hey "]},
        {"label": "CTA", "keywords": ["call to action", "cta", "click", "reply", "get started"]},
    ],
    "ad_copy": [
        {"label": "Headline", "keywords": ["headline", "head"]},
        {"label": "Body", "keywords": ["body", "description", "copy"]},
    ],
    "product_description": [
        {"label": "Opening", "keywords": ["opening", "overview", "what", "introducing"]},
        {"label": "Features/Benefits", "keywords": ["feature", "benefit", "what you get"]},
    ],
    "sales_page": [
        {"label": "Headline", "keywords": ["hero", "headline"]},
        {"label": "Pain Point", "keywords": ["problem", "pain", "frustrat", "struggle"]},
        {"label": "Solution", "keywords": ["solution", "how", "introducing"]},
        {"label": "Benefits", "keywords": ["benefit", "why", "advantage"]},
        {"label": "CTA", "keywords": ["call to action", "cta", "get started", "buy", "start"]},
    ],
    "general": [
        {"label": "Headline", "keywords": ["headline", "title"]},
    ],
}

CTA_PHRASES = [
    "sign up", "get started", "buy now", "schedule", "download",
    "try free", "try it", "start free", "start your", "claim",
    "book a", "book your", "request", "subscribe", "join",
    "register", "learn more", "contact us", "talk to", "see demo",
    "grab your", "unlock", "activate", "begin your", "apply now",
    "order now", "shop now", "add to cart", "enroll",
]

HEADLINE_BENEFIT_MARKERS = [
    r'\d+', r'%', r'\bsave\b', r'\bincrease\b', r'\breduce\b',
    r'\bget\b', r'\bachieve\b', r'\btransform\b', r'\bstop\b',
    r'\bstart\b', r'\bdiscover\b', r'\bunlock\b', r'\bboost\b',
    r'\bcut\b', r'\bgrow\b', r'\bfaster\b', r'\beasier\b',
    r'\bfree\b', r'\bwithout\b', r'\bhow to\b', r'\bwhy\b',
    r'\bsecret\b', r'\bproven\b', r'\bguarantee\b',
]

HEADLINE_CURIOSITY_MARKERS = [
    r'\?', r'\bhow\b', r'\bwhy\b', r'\bwhat if\b',
    r'\bthe \d+\b', r'\byou\'re\b', r'\bstop\b',
]

SOCIAL_PROOF_MARKERS = [
    "customers", "companies", "trusted by", "used by", "reviews",
    "rated", "testimonial", "users", "teams", "businesses",
    "client", "case study", "success story",
]

URGENCY_MARKERS = [
    "limited", "now", "today", "before", "deadline", "spots",
    "only", "hurry", "don't miss", "last chance", "expires",
    "act now", "while", "ending soon",
]

OBJECTION_MARKERS = [
    "but what about", "you might wonder", "concerned about",
    "worry", "risk-free", "guarantee", "no obligation",
    "what if", "afraid", "hesitat", "common question",
    "faq", "but what if", "no risk", "cancel anytime",
    "money back", "refund",
]

SPECIFICITY_MARKERS = re.compile(
    r'(?:\d+\s*(?:%|x|hours?|minutes?|days?|weeks?|months?|times?)\b|'
    r'\$[\d,]+|'
    r'\b\d{2,}\+?\s*(?:customers?|users?|companies|teams?|businesses)\b)',
    re.IGNORECASE
)

BANNED_FILLER = [
    "cutting-edge", "best-in-class", "world-class", "leverage synergies",
    "paradigm shift", "revolutionary", "game-changing", "next-generation",
    "seamless integration", "robust solution", "innovative approach",
    "holistic solution", "state-of-the-art", "turnkey solution",
    "synergistic", "disruptive innovation", "thought leader",
    "move the needle", "low-hanging fruit", "circle back",
]

FORMAL_MARKERS = [
    "herein", "aforementioned", "pursuant to", "henceforth",
    "notwithstanding", "in accordance with", "thereby",
    "whereas", "shall", "deemed",
]

CASUAL_MARKERS = [
    "hey", "awesome", "super", "totally", "gonna", "wanna",
    "stuff", "cool", "amazing", "insane", "crazy good",
    "no brainer", "hands down",
]

FEATURE_ONLY_INDICATORS = re.compile(
    r'(?:\d+\s*(?:GB|MB|TB|GHz|cores?|threads?|pixels?|dpi|fps)\b|'
    r'\b(?:supports?|includes?|features?|comes with|built[- ]in|compatible)\b)',
    re.IGNORECASE
)

OUTCOME_LANGUAGE = re.compile(
    r'\b(?:so that|which means|enabling|allowing|helps? you|'
    r'resulting in|leading to|saving|reducing|increasing|improving|'
    r'giving you|making it|you can|you\'ll|your team)\b',
    re.IGNORECASE
)

FABRICATED_TESTIMONIAL_PATTERN = re.compile(
    r'["\u201c]([^"\u201d]{20,})["\u201d]\s*[-\u2014]\s*([A-Z][a-z]+ [A-Z])',
    re.MULTILINE
)


# ── Validation Functions ──────────────────────────────────────────────────────

def check_format_sections(text, copy_format):
    """Check required sections for the given format."""
    sections = FORMAT_REQUIRED_SECTIONS.get(copy_format, FORMAT_REQUIRED_SECTIONS["general"])
    text_lower = text.lower()
    missing = []
    for sec in sections:
        found = any(kw in text_lower for kw in sec["keywords"])
        if not found:
            # Also check H2/H3 headings
            for kw in sec["keywords"]:
                if re.search(rf'#{2,3}\s[^\n]*{re.escape(kw)}', text, re.IGNORECASE):
                    found = True
                    break
        if not found:
            missing.append(sec["label"])
    return missing


def check_cta_count(text):
    """Count distinct CTA phrases. Flag >2."""
    text_lower = text.lower()
    found_ctas = set()
    for phrase in CTA_PHRASES:
        if phrase in text_lower:
            # Normalize similar CTAs
            normalized = phrase.split()[0]  # Group by first word
            found_ctas.add(phrase)
    return len(found_ctas), list(found_ctas)


def check_any_cta(text):
    """Check if at least one CTA exists."""
    text_lower = text.lower()
    return any(phrase in text_lower for phrase in CTA_PHRASES)


def check_headline_quality(text):
    """Check first heading has benefit/hook markers."""
    # Find first H1 or H2
    m = re.search(r'^#{1,2}\s+(.+)', text, re.MULTILINE)
    if not m:
        return False, "", "no headline found"

    headline = m.group(1).strip()
    headline_lower = headline.lower()

    # Check benefit markers
    has_benefit = any(re.search(pat, headline_lower) for pat in HEADLINE_BENEFIT_MARKERS)
    has_curiosity = any(re.search(pat, headline_lower) for pat in HEADLINE_CURIOSITY_MARKERS)

    if has_benefit or has_curiosity:
        return True, headline, "benefit/curiosity detected"
    return False, headline, "no benefit or hook — reads as a label"


def count_persuasion_techniques(text):
    """Count distinct persuasion techniques used."""
    text_lower = text.lower()
    techniques = {}

    # Social proof
    sp_count = sum(1 for m in SOCIAL_PROOF_MARKERS if m in text_lower)
    if sp_count >= 2:
        techniques["social_proof"] = sp_count

    # Urgency
    urg_count = sum(1 for m in URGENCY_MARKERS if m in text_lower)
    if urg_count >= 1:
        techniques["urgency"] = urg_count

    # Benefit stacking (3+ bullet points with outcome language)
    bullets = re.findall(r'^\s*[-*\u2022]\s+(.+)', text, re.MULTILINE)
    outcome_bullets = sum(1 for b in bullets if OUTCOME_LANGUAGE.search(b))
    if outcome_bullets >= 3:
        techniques["benefit_stacking"] = outcome_bullets

    # Objection handling
    obj_count = sum(1 for m in OBJECTION_MARKERS if m in text_lower)
    if obj_count >= 1:
        techniques["objection_handling"] = obj_count

    # Specificity (numbers, percentages, timeframes)
    spec_count = len(SPECIFICITY_MARKERS.findall(text))
    if spec_count >= 2:
        techniques["specificity"] = spec_count

    return techniques


def check_feature_benefit_separation(text):
    """Check if bullet points are feature-only or include benefits."""
    bullets = re.findall(r'^\s*[-*\u2022]\s+(.+)', text, re.MULTILINE)
    if not bullets:
        return True, 0, 0

    feature_only = 0
    for bullet in bullets:
        has_feature_indicator = bool(FEATURE_ONLY_INDICATORS.search(bullet))
        has_outcome = bool(OUTCOME_LANGUAGE.search(bullet))
        if has_feature_indicator and not has_outcome:
            feature_only += 1

    total = len(bullets)
    pct = feature_only / total if total > 0 else 0
    return pct <= 0.5, feature_only, total


def check_filler_phrases(text):
    """Detect banned filler phrases."""
    text_lower = text.lower()
    found = [f for f in BANNED_FILLER if f in text_lower]
    return found


def check_fabrication(text, reference_material):
    """Flag fabricated testimonials and stats when no reference data."""
    flags = []

    # Fabricated quoted testimonials
    for match in FABRICATED_TESTIMONIAL_PATTERN.finditer(text):
        quote = match.group(1)
        name = match.group(2)
        if reference_material:
            # Check if the name or quote content appears in reference
            if name.lower() not in reference_material.lower() and quote[:20].lower() not in reference_material.lower():
                flags.append(f"Testimonial attributed to '{name}' not found in reference material")
        else:
            flags.append(f"Fabricated testimonial: '{quote[:40]}...' — no reference material provided")

    # Fabricated statistics when no reference
    if not reference_material or not reference_material.strip():
        for match in re.finditer(r'[\d]+(?:\.\d+)?%\s*(?:increase|decrease|improvement|reduction|growth)',
                                  text, re.IGNORECASE):
            flags.append(f"Potentially fabricated stat: {match.group()}")
        for match in re.finditer(r'[\d,]+\+?\s*(?:customers?|users?|companies|businesses|teams)',
                                  text, re.IGNORECASE):
            flags.append(f"Potentially fabricated count: {match.group()}")

    return flags


def check_tone_consistency(text, brand_voice):
    """Simple tone consistency: check formality markers in opening vs closing."""
    if not brand_voice:
        return True, ""

    voice_lower = brand_voice.lower()
    is_casual_brand = any(w in voice_lower for w in ["casual", "playful", "friendly", "informal", "fun"])
    is_formal_brand = any(w in voice_lower for w in ["formal", "professional", "corporate", "executive"])

    text_lines = text.strip().split('\n')
    if len(text_lines) < 4:
        return True, ""

    opening = ' '.join(text_lines[:5]).lower()
    closing = ' '.join(text_lines[-5:]).lower()

    if is_casual_brand:
        formal_in_text = any(m in opening + closing for m in FORMAL_MARKERS)
        if formal_in_text:
            return False, "Brand voice is casual but formal language detected"

    if is_formal_brand:
        casual_in_text = any(m in opening + closing for m in CASUAL_MARKERS)
        if casual_in_text:
            return False, "Brand voice is formal but casual language detected"

    return True, ""


# ── Full Deterministic Validation ─────────────────────────────────────────────
def validate_copy(text, analysis):
    """Full deterministic validation.
    Returns (issues, filler_found, fabrication_flags, penalty_items)."""
    issues = []
    copy_format = analysis.get("copy_format", "general")
    copy_length = analysis.get("copy_length", "standard")
    reference = analysis.get("reference_material", "")
    brand_voice = analysis.get("brand_voice", "")

    # 1. Format-specific sections
    missing = check_format_sections(text, copy_format)
    for m in missing:
        issues.append(f"Missing required section for {copy_format}: {m}")

    # 2. CTA presence (hard-fail if none)
    has_cta = check_any_cta(text)
    if not has_cta:
        issues.append("No CTA detected — every piece needs at least one call to action")

    # 3. CTA count (penalty if >2)
    cta_count, cta_list = check_cta_count(text)

    # 4. Headline quality
    headline_ok, headline, headline_msg = check_headline_quality(text)

    # 5. Persuasion techniques
    techniques = count_persuasion_techniques(text)
    min_techniques = 1 if copy_length == "short" or copy_format == "ad_copy" else 2

    # 6. Feature-benefit separation
    fb_ok, feature_only, fb_total = check_feature_benefit_separation(text)

    # 7. Fabricated testimonials (hard-fail for quoted fabrication)
    fabrication_flags = check_fabrication(text, reference)
    hard_fabrications = [f for f in fabrication_flags if "Fabricated testimonial:" in f]
    if hard_fabrications:
        issues.append(f"Fabricated testimonial detected: {hard_fabrications[0]}")

    # 8. Tone consistency
    tone_ok, tone_msg = check_tone_consistency(text, brand_voice)

    # ── Filler ────────────────────────────────────────────────────────────
    filler_found = check_filler_phrases(text)

    # ── Penalty items (not hard-fail) ─────────────────────────────────────
    penalty_items = []
    if cta_count > 2:
        penalty_items.append(f"Multiple competing CTAs ({cta_count}): consolidate to one primary")
    if not headline_ok and headline:
        penalty_items.append(f"Headline lacks benefit/hook: '{headline[:50]}'")
    if len(techniques) < min_techniques:
        penalty_items.append(
            f"Low persuasion techniques: {len(techniques)} found "
            f"(need {min_techniques}): {list(techniques.keys())}")
    if not fb_ok:
        penalty_items.append(f"Feature-only bullets: {feature_only}/{fb_total} lack outcome framing")
    if not tone_ok:
        penalty_items.append(f"Tone: {tone_msg}")

    # Filter hard fabrications out of flags (already in issues)
    soft_fabrications = [f for f in fabrication_flags if "Fabricated testimonial:" not in f]

    return issues, filler_found, soft_fabrications, penalty_items


# ── Execution Role ────────────────────────────────────────────────────────────
EXECUTION_ROLE = """You are a senior conversion copywriter who produces polished, audience-targeted
marketing copy. You follow these absolute rules:

1. Every piece has exactly ONE primary CTA. Do not scatter multiple different asks.
2. Headlines contain a benefit, hook, or curiosity element — never just a product name.
3. Use identifiable persuasion techniques: social proof, urgency, benefit stacking,
   objection handling, specificity with numbers.
4. Frame benefits as OUTCOMES, not feature lists. "256GB storage" is a feature.
   "Never worry about running out of space" is a benefit.
5. Do NOT fabricate testimonials, customer quotes, case studies, or statistics.
   If reference_material provides them, use them. If not, use placeholder markers:
   [INSERT TESTIMONIAL], [INSERT METRIC], [INSERT CASE STUDY].
6. Maintain consistent tone throughout — match the brand voice exactly.
7. Avoid filler: no "cutting-edge", "best-in-class", "game-changing", "robust solution".
8. Be specific: numbers, timeframes, named outcomes > vague claims."""


# ── Step Handlers ─────────────────────────────────────────────────────────────

def step_1_local(inputs, context):
    """Parse copy brief and build generation plan."""
    brief = inputs.get("copy_brief", "").strip()
    if not brief or len(brief) < 30:
        return None, "copy_brief must be at least 30 characters"

    audience = inputs.get("target_audience", "").strip()
    if not audience or len(audience) < 15:
        return None, "target_audience must be at least 15 characters"

    copy_format = inputs.get("copy_format", "general").strip()
    if copy_format not in ("landing_page", "email", "ad_copy", "product_description", "sales_page", "general"):
        return None, f"Invalid copy_format: {copy_format}"

    brand_voice = inputs.get("brand_voice", "").strip()
    reference = inputs.get("reference_material", "").strip()
    copy_length = inputs.get("copy_length", "standard").strip()
    if copy_length not in ("short", "standard", "long"):
        copy_length = "standard"

    # Audience signals
    audience_lower = (audience + " " + brief).lower()
    signals = {
        "b2b": any(w in audience_lower for w in ["b2b", "business", "enterprise", "company", "vp", "director", "head of", "cto", "cfo"]),
        "b2c": any(w in audience_lower for w in ["b2c", "consumer", "individual", "personal", "people", "user"]),
        "technical": any(w in audience_lower for w in ["developer", "engineer", "technical", "devops", "api", "code"]),
        "executive": any(w in audience_lower for w in ["cto", "cfo", "ceo", "vp", "director", "executive", "c-suite"]),
    }

    # Reference inventory
    has_testimonials = bool(re.search(r'(?:testimonial|quote|said|told us|feedback)', reference, re.IGNORECASE)) if reference else False
    has_statistics = bool(re.search(r'\d+%|\$[\d,]+|\d+\+?\s*(?:customers?|users?|companies)', reference, re.IGNORECASE)) if reference else False
    has_features = bool(re.search(r'(?:feature|integrat|support|includ|built[- ]in)', reference, re.IGNORECASE)) if reference else False

    # Voice keywords
    voice_keywords = []
    if brand_voice:
        for word in ["formal", "casual", "playful", "authoritative", "warm",
                     "direct", "empathetic", "technical", "friendly", "professional"]:
            if word in brand_voice.lower():
                voice_keywords.append(word)
    if not voice_keywords:
        voice_keywords = ["professional", "clear"]

    result = {
        "copy_brief": brief,
        "target_audience": audience,
        "copy_format": copy_format,
        "brand_voice": brand_voice or "Professional, clear, benefit-focused",
        "reference_material": reference,
        "copy_length": copy_length,
        "audience_signals": signals,
        "has_testimonials": has_testimonials,
        "has_statistics": has_statistics,
        "has_features": has_features,
        "has_reference": bool(reference),
        "voice_keywords": voice_keywords,
        "format_rules": FORMAT_REQUIRED_SECTIONS.get(copy_format, FORMAT_REQUIRED_SECTIONS["general"]),
    }

    return {"output": result}, None


def step_2_llm(inputs, context):
    """Generate polished marketing copy."""
    analysis = context.get("step_1_output", context.get("_resolved_input", {}))
    if not analysis or not isinstance(analysis, dict):
        return None, "No analysis from step 1"

    brief = analysis.get("copy_brief", "")
    audience = analysis.get("target_audience", "")
    copy_format = analysis.get("copy_format", "general")
    brand_voice = analysis.get("brand_voice", "Professional, clear")
    reference = analysis.get("reference_material", "")
    copy_length = analysis.get("copy_length", "standard")
    has_ref = analysis.get("has_reference", False)

    format_instructions = {
        "landing_page": """REQUIRED SECTIONS (use ## headings):
## Hero Section — Headline with benefit/hook + subheadline
## The Problem — Audience pain point, agitation
## The Solution — Product/service as the answer
## Benefits — 3+ specific benefits as outcomes, NOT feature list
## Social Proof — {'Use provided testimonials/data' if has_ref else 'Use [INSERT TESTIMONIAL] and [INSERT METRIC] placeholders'}
## Call to Action — Single, clear, specific CTA
## Objection Handling — Address 1-2 likely objections""",

        "email": """REQUIRED SECTIONS:
**Subject Line:** — benefit-driven or curiosity-driven (do NOT repeat in preview)
**Preview Text:** — complements subject, does not repeat it
Then the email body with:
- Opening hook (first 2 sentences earn the read)
- Value delivery (not pitch-first)
- Single CTA (specific action, not "click here")
- Optional P.S. reinforcement""",

        "ad_copy": """REQUIRED FORMAT:
**Headline:** — benefit or hook (max 40 chars for social, 30 for search)
**Body:** — concise value proposition (max 125 chars social, 90 search)
**CTA:** — action-oriented phrase

Generate 3 variations with different angles.""",

        "product_description": """REQUIRED SECTIONS:
## Overview — What it is and who it's for (one paragraph)
## Features & Benefits — 3+ feature-benefit pairs (feature → outcome)
## Use Case — One concrete scenario showing the product in action
## Get Started — CTA with next step""",

        "sales_page": """REQUIRED SECTIONS (use ## headings):
## Hero — Benefit-driven headline
## The Problem — Specific pain point identification
## The Solution — How product solves it (bridge)
## Why It Works — 3+ benefits with specificity
## Proof — {'Use provided data' if has_ref else 'Use [INSERT TESTIMONIAL] placeholders'}
## Call to Action — Single, clear CTA
## Risk Reversal — Guarantee, trial, or refund mention""",

        "general": """REQUIRED: Headline with benefit/hook + structured body + CTA.""",
    }

    length_rules = {
        "short": "Keep under 300 words. Tight, punchy, no filler.",
        "standard": "300-800 words. Room for persuasion mechanics but stay focused.",
        "long": "800+ words. Full persuasion arc: problem → agitation → solution → proof → CTA.",
    }

    ref_block = ""
    if reference:
        ref_block = f"\nREFERENCE MATERIAL (use this data — do NOT invent beyond it):\n{reference}"
    else:
        ref_block = "\nNO REFERENCE MATERIAL PROVIDED. Use [INSERT TESTIMONIAL], [INSERT METRIC], [INSERT CASE STUDY] placeholders where social proof would go. Do NOT fabricate statistics or quotes."

    system = f"""{EXECUTION_ROLE}

FORMAT: {copy_format.upper()}
{format_instructions.get(copy_format, format_instructions['general'])}

BRAND VOICE: {brand_voice}
LENGTH: {copy_length.upper()} — {length_rules.get(copy_length, '')}
{ref_block}

RULES:
- ONE primary CTA only — do not scatter multiple different asks
- Headline MUST contain a benefit, number, or curiosity hook
- Use 2+ persuasion techniques (social proof, urgency, benefit stacking, objection handling, specificity)
- Frame benefits as OUTCOMES: what the audience GETS, not what the product HAS
- Match the brand voice exactly — tone must be consistent throughout
- No filler: no "cutting-edge", "best-in-class", "game-changing", "robust solution"
- Output ONLY the copy as markdown. No preamble, no explanation."""

    user = f"""COPY BRIEF:
{brief}

TARGET AUDIENCE:
{audience}

Write the {copy_format.replace('_', ' ')} copy ({copy_length} length)."""

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    tokens = _get_token_budget(copy_length)
    content, error = call_resolved(messages, context, max_tokens=tokens)
    if error:
        content, error = call_openai(messages, model="gpt-5.4-mini", max_tokens=tokens)
    if error:
        return None, error

    return {"output": content}, None


def step_3_critic(inputs, context):
    """Two-layer validation: deterministic then LLM."""
    analysis = context.get("step_1_output", {})

    copy = context.get("improved_copy", context.get("generated_copy",
           context.get("step_2_output", "")))
    if isinstance(copy, dict):
        copy = str(copy)
    if not copy:
        return None, "No copy to evaluate"

    # ── Layer 1: Deterministic ────────────────────────────────────────────
    det_issues, filler_found, fabrication_flags, penalty_items = validate_copy(
        copy, analysis)

    det_penalty = (len(det_issues)
                   + len(filler_found) * 0.5
                   + len(fabrication_flags) * 0.5
                   + len(penalty_items) * 0.5)
    structural_score = max(0, 10 - (det_penalty * 1.5))

    if structural_score <= 2:
        return {"output": {
            "quality_score": structural_score,
            "structural_score": structural_score,
            "persuasion_quality": 0,
            "voice_alignment": 0,
            "deterministic_issues": det_issues,
            "filler_found": filler_found,
            "fabrication_flags": fabrication_flags,
            "penalty_items": penalty_items,
            "llm_feedback": "Too many structural issues — fix deterministic failures first",
            "feedback": f"STRUCTURAL ({len(det_issues)} issues): " + " | ".join(det_issues[:8]),
        }}, None

    # ── Layer 2: LLM quality ──────────────────────────────────────────────
    system = """You are a conversion copy reviewer. Score (each 0-10):
- persuasion_quality: Does the copy make you want to take the CTA? Is the value
  proposition clear? Are objections addressed? Would the target audience respond?
- voice_alignment: Does the tone match the brand voice? Is it consistent throughout?
  Is the language appropriate for the audience?

JSON ONLY — no markdown, no backticks:
{"persuasion_quality": N, "voice_alignment": N, "llm_feedback": "Notes"}"""

    user = f"""MARKETING COPY:
{copy[:5000]}

FORMAT: {analysis.get('copy_format', 'general')}
BRAND VOICE: {analysis.get('brand_voice', '')}
TARGET AUDIENCE: {analysis.get('target_audience', '')[:200]}

Evaluate."""

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    content, error = call_resolved(messages, context, max_tokens=1500)
    if error:
        content, error = call_openai(messages, model="gpt-5.4-mini", max_tokens=1500)

    llm_scores = {"persuasion_quality": 5, "voice_alignment": 5, "llm_feedback": ""}
    if not error and content:
        try:
            cleaned = content.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
                cleaned = re.sub(r'\s*```$', '', cleaned)
            llm_scores = json.loads(cleaned)
        except (json.JSONDecodeError, TypeError):
            llm_scores["llm_feedback"] = content

    persuasion = llm_scores.get("persuasion_quality", 5)
    voice = llm_scores.get("voice_alignment", 5)
    quality_score = min(structural_score, persuasion, voice)

    feedback_parts = []
    if det_issues:
        feedback_parts.append(f"STRUCTURAL ({len(det_issues)}): " + " | ".join(det_issues[:8]))
    if filler_found:
        feedback_parts.append(f"FILLER ({len(filler_found)}): " + ", ".join(filler_found[:5]))
    if fabrication_flags:
        feedback_parts.append(f"FABRICATION ({len(fabrication_flags)}): " + " | ".join(fabrication_flags[:3]))
    if penalty_items:
        feedback_parts.append(f"PENALTIES ({len(penalty_items)}): " + " | ".join(penalty_items[:3]))
    llm_fb = llm_scores.get("llm_feedback", "")
    if llm_fb:
        feedback_parts.append(f"QUALITY: {llm_fb}")

    return {"output": {
        "quality_score": quality_score,
        "structural_score": structural_score,
        "persuasion_quality": persuasion,
        "voice_alignment": voice,
        "deterministic_issues": det_issues,
        "filler_found": filler_found,
        "fabrication_flags": fabrication_flags,
        "penalty_items": penalty_items,
        "llm_feedback": llm_fb,
        "feedback": " || ".join(feedback_parts) if feedback_parts else "All checks passed",
    }}, None


def step_4_llm(inputs, context):
    """Strengthen copy based on critic feedback."""
    analysis = context.get("step_1_output", {})
    brief = analysis.get("copy_brief", "")
    copy_format = analysis.get("copy_format", "general")
    copy_length = analysis.get("copy_length", "standard")

    copy = context.get("improved_copy", context.get("generated_copy",
           context.get("step_2_output", "")))
    if isinstance(copy, dict):
        copy = str(copy)

    critic = context.get("step_3_output", {})
    if isinstance(critic, str):
        try:
            critic = json.loads(critic)
        except (json.JSONDecodeError, TypeError):
            critic = {"feedback": critic}

    feedback = critic.get("feedback", "")
    det_issues = critic.get("deterministic_issues", [])
    filler_found = critic.get("filler_found", [])

    det_section = ""
    if det_issues:
        det_section = "\nCRITICAL FIXES:\n" + "\n".join(f"  - {i}" for i in det_issues[:10])
    if filler_found:
        det_section += "\nFILLER TO REMOVE:\n" + "\n".join(f"  - {f}" for f in filler_found[:10])

    system = f"""{EXECUTION_ROLE}

Improving {copy_format.replace('_', ' ')} copy based on critic feedback.
{det_section}

RULES:
1. Fix ALL structural issues listed above.
2. Consolidate to ONE primary CTA if multiple were flagged.
3. Strengthen headline with benefit/number/hook.
4. Add missing persuasion techniques.
5. Convert feature-only bullets to benefit framing.
6. Remove ALL filler phrases listed above.
7. Do NOT add fabricated testimonials or statistics.
8. Maintain brand voice consistency.
9. Output ONLY the improved copy. No preamble."""

    user = f"""BRIEF: {brief[:500]}

CURRENT COPY:
{copy}

FEEDBACK: {feedback}

Fix all issues."""

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    tokens = _get_token_budget(copy_length)
    content, error = call_resolved(messages, context, max_tokens=tokens)
    if error:
        content, error = call_openai(messages, model="gpt-5.4-mini", max_tokens=tokens)
    if error:
        return None, error

    return {"output": content}, None


def _select_best_output(context):
    for key in ("improved_copy", "generated_copy", "step_2_output"):
        v = context.get(key, "")
        if v and isinstance(v, str) and v.strip():
            return v
    return context.get("generated_copy", "")


def step_5_write(inputs, context):
    """Full deterministic gate."""
    best = _select_best_output(context)
    if isinstance(best, dict):
        best = str(best)
    if not best or not best.strip():
        return None, "No copy to write"

    analysis = context.get("step_1_output", {})

    issues, filler_found, fabrication_flags, penalty_items = validate_copy(
        best, analysis)

    critical_keywords = [
        "missing required section", "no cta detected",
        "fabricated testimonial detected",
    ]
    critical = [i for i in issues if any(k in i.lower() for k in critical_keywords)]

    if critical:
        summary = "; ".join(critical[:5])
        return None, f"COPY INTEGRITY FAILURE ({len(critical)} critical): {summary}"

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
