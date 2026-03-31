#!/usr/bin/env python3
"""
NemoClaw Skill: i35-tone-calibrator
Tone Calibrator v1.2.0
F35 | I | customer-facing | transformer
Schema v2 | Runner v4.0+

v1.2: Hard-fail on final numeric violation, stronger malformed-number
extraction, consistent output structure, final selection aligned with runner.
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


def call_openai(messages, model=None, max_tokens=4000):
    if model is None:
        from lib.routing import resolve_alias
        _, model, _ = resolve_alias("general_short")
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, SystemMessage
    env = load_env()
    key = env.get("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
    if not key: return None, "OPENAI_API_KEY not found"
    llm = ChatOpenAI(model=model, api_key=key, max_tokens=max_tokens, temperature=0.3)
    lc = [SystemMessage(content=m["content"]) if m["role"] == "system" else HumanMessage(content=m["content"]) for m in messages]
    return llm.invoke(lc).content, None


def call_anthropic(messages, model=None, max_tokens=4000):
    if model is None:
        from lib.routing import resolve_alias
        _, model, _ = resolve_alias("complex_reasoning")
    from langchain_anthropic import ChatAnthropic
    from langchain_core.messages import HumanMessage, SystemMessage
    env = load_env()
    key = env.get("ANTHROPIC_API_KEY", os.environ.get("ANTHROPIC_API_KEY", ""))
    if not key: return None, "ANTHROPIC_API_KEY not found"
    llm = ChatAnthropic(model=model, api_key=key, max_tokens=max_tokens, temperature=0.3)
    lc = [SystemMessage(content=m["content"]) if m["role"] == "system" else HumanMessage(content=m["content"]) for m in messages]
    return llm.invoke(lc).content, None


def call_google(messages, model=None, max_tokens=4000):
    if model is None:
        from lib.routing import resolve_alias
        _, model, _ = resolve_alias("moderate")
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.messages import HumanMessage, SystemMessage
    env = load_env()
    key = env.get("GOOGLE_API_KEY", os.environ.get("GOOGLE_API_KEY", ""))
    if not key: return None, "GOOGLE_API_KEY not found"
    llm = ChatGoogleGenerativeAI(model=model, google_api_key=key, max_tokens=max_tokens)
    lc = [SystemMessage(content=m["content"]) if m["role"] == "system" else HumanMessage(content=m["content"]) for m in messages]
    return llm.invoke(lc).content, None


def call_resolved(messages, context, max_tokens=4000):
    m = context.get("resolved_model", "")
    p = context.get("resolved_provider", __import__("lib.routing", fromlist=["resolve_alias"]).resolve_alias("moderate")[0])
    if p == "google": return call_google(messages, model=m or "gemini-2.5-flash", max_tokens=max_tokens)
    if p == "openai": return call_openai(messages, model=m or "gpt-5.4-mini", max_tokens=max_tokens)
    return call_anthropic(messages, model=m or "claude-sonnet-4-6", max_tokens=max_tokens)


# ── Deterministic Numeric Extraction (Fix 2: strengthened) ────────────────────

NUMERIC_PATTERNS = [
    # Currency with multiplier: $4.2M, €50K, $.2M, $100 (including malformed like $.2M)
    re.compile(r'[\$€£¥]\s*\.?\d[\d,]*\.?\d*\s*[KMBTkmbt]?', re.IGNORECASE),
    # Malformed leading-decimal currency: $.2M, $.75
    re.compile(r'[\$€£¥]\.\d+\s*[KMBTkmbt]?', re.IGNORECASE),
    # Percentages: 99.9%, 23.4%, .5%
    re.compile(r'\.?\d[\d,]*\.?\d*\s*%'),
    # Negative values: -5%, -$100, -3.2
    re.compile(r'-\d[\d,]*\.?\d*\s*[%KMBTkmbt]?'),
    # Ranges: 10-12%, 5-10x
    re.compile(r'\d+\.?\d*\s*[-–]\s*\d+\.?\d*\s*[%xX]?'),
    # Quarters: Q1, Q3 2024
    re.compile(r'\bQ[1-4]\s*\d{0,4}\b'),
    # Dates: MM/DD/YYYY, YYYY-MM-DD
    re.compile(r'\b\d{1,2}/\d{1,2}/\d{2,4}\b'),
    re.compile(r'\b\d{4}-\d{2}-\d{2}\b'),
    # Dates: Month DD, YYYY
    re.compile(r'\b(?:January|February|March|April|May|June|July|August|'
               r'September|October|November|December)\s+\d{1,2},?\s*\d{4}\b', re.IGNORECASE),
    # Numbers with multiplier: 4.2M, 100K, .2M
    re.compile(r'\.?\d[\d,]*\.?\d*\s*[KMBTkmbt]\b'),
    # Comma-separated numbers: 1,000,000
    re.compile(r'\b\d{1,3}(?:,\d{3})+(?:\.\d+)?\b'),
    # Malformed leading-decimal standalone: .2M, .75, .5%
    re.compile(r'\.\d+\s*[KMBTkmbt%]?'),
]


def extract_numeric_tokens(text):
    """Extract all numeric tokens preserving exact original form."""
    tokens = set()
    for pat in NUMERIC_PATTERNS:
        for match in pat.finditer(text):
            token = match.group().strip()
            if len(token) >= 2:  # Skip single chars
                tokens.add(token)

    # Fallback: extract standalone decimal/integer sequences (2+ chars)
    for match in re.finditer(r'\d+\.\d+|\d{2,}', text):
        tokens.add(match.group())

    return tokens


def check_numeric_preservation(original_text, rewritten_text):
    """Compare numeric tokens. Returns (passed, missing, invented)."""
    orig = extract_numeric_tokens(original_text)
    rewrite = extract_numeric_tokens(rewritten_text)

    missing = orig - rewrite
    invented = rewrite - orig

    # Filter out noise: very short generic numbers that are likely structural
    missing = {t for t in missing if len(t) >= 2}
    invented = {t for t in invented if len(t) >= 2}

    return len(missing) == 0 and len(invented) == 0, missing, invented


# ── Tone Detection Heuristics ─────────────────────────────────────────────────
FORMAL_MARKERS = [
    "furthermore", "consequently", "nevertheless", "notwithstanding",
    "aforementioned", "herein", "pursuant", "whereby", "thereof",
    "accordingly", "henceforth", "whereas"
]

CASUAL_MARKERS = [
    "gonna", "wanna", "kinda", "sorta", "yeah", "nope", "hey",
    "cool", "awesome", "btw", "tbh", "imo", "lol", "omg"
]

CONTRACTION_PATTERN = re.compile(
    r"\b(can't|won't|don't|isn't|aren't|wasn't|weren't|hasn't|haven't|"
    r"hadn't|doesn't|didn't|couldn't|wouldn't|shouldn't|mustn't|"
    r"let's|it's|he's|she's|that's|there's|here's|who's|what's|"
    r"i'm|you're|we're|they're|i've|you've|we've|they've|"
    r"i'll|you'll|we'll|they'll|i'd|you'd|we'd|they'd)\b",
    re.IGNORECASE
)

TECHNICAL_MARKERS = [
    "api", "sdk", "http", "json", "sql", "css", "html", "tcp",
    "algorithm", "latency", "throughput", "infrastructure",
    "deployment", "containerized", "microservices", "kubernetes",
    "scalability", "middleware", "endpoint"
]


def detect_tone(text):
    words = text.split()
    word_count = len(words)
    if word_count == 0:
        return {}

    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    sent_count = max(len(sentences), 1)
    avg_sent_len = word_count / sent_count

    text_lower = text.lower()
    formal_count = sum(1 for m in FORMAL_MARKERS if m in text_lower)
    casual_count = sum(1 for m in CASUAL_MARKERS if m in text_lower)
    contraction_count = len(CONTRACTION_PATTERN.findall(text))
    technical_count = sum(1 for m in TECHNICAL_MARKERS if m in text_lower)

    if formal_count >= 3 or (contraction_count == 0 and avg_sent_len > 20):
        formality = "high"
    elif casual_count >= 2 or contraction_count >= 3:
        formality = "low"
    else:
        formality = "medium"

    if avg_sent_len > 25: sentence_style = "long_complex"
    elif avg_sent_len < 10: sentence_style = "short_punchy"
    else: sentence_style = "medium_balanced"

    if contraction_count == 0: contraction_usage = "none"
    elif contraction_count / sent_count > 0.5: contraction_usage = "heavy"
    else: contraction_usage = "moderate"

    warm_words = ["love", "great", "wonderful", "amazing", "thank", "appreciate",
                  "happy", "excited", "welcome", "glad", "enjoy", "celebrate"]
    warm_count = sum(1 for w in warm_words if w in text_lower)
    if warm_count >= 3: emotional_warmth = "high"
    elif warm_count == 0 and formality == "high": emotional_warmth = "low"
    else: emotional_warmth = "medium"

    if technical_count >= 5: technical_density = "high"
    elif technical_count >= 2: technical_density = "medium"
    else: technical_density = "low"

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    has_bullets = bool(re.search(r'^\s*[-*•]\s', text, re.MULTILINE))
    has_headings = bool(re.search(r'^#{1,6}\s|^[A-Z][A-Za-z\s]{3,}:?\s*$', text, re.MULTILINE))
    has_cta = bool(re.search(
        r'(?i)(click|sign up|subscribe|register|schedule|book|download|'
        r'get started|learn more|contact us|try|join|buy|order)', text))

    if has_bullets and has_headings: structure_sig = "structured_with_bullets_and_headings"
    elif has_bullets: structure_sig = "bulleted_list"
    elif has_headings: structure_sig = "paragraphs_with_headings"
    else: structure_sig = "plain_paragraphs"

    return {
        "detected_formality": formality, "sentence_style": sentence_style,
        "contraction_usage": contraction_usage, "emotional_warmth": emotional_warmth,
        "technical_density": technical_density, "structure_signature": structure_sig,
        "word_count": word_count, "paragraph_count": len(paragraphs),
        "has_bullets": has_bullets, "has_headings": has_headings, "has_cta": has_cta,
    }


# ── Step Handlers ─────────────────────────────────────────────────────────────

EXECUTION_ROLE = """You are a professional tone calibration specialist with expertise in
linguistic register, voice adaptation, and content preservation. Your
job is to rewrite text to match a specified tone while:

1. Preserving ALL factual content — no facts added or removed
2. Maintaining the logical structure and argument flow
3. Matching the target tone naturally — not mechanically

You understand that tone is more than word choice. It includes:
- Sentence length and rhythm
- Level of formality
- Use of contractions and colloquialisms
- Emotional distance or warmth
- Technical vocabulary density
- Active vs passive voice balance"""

TONE_PROFILES = """Tone profiles:
- professional: Clear, confident, formal but not stiff. No slang. Active voice preferred.
- casual: Relaxed, conversational, contractions welcome. Like talking to a smart friend.
- authoritative: Expert voice. Definitive statements. Data-backed confidence. Minimal hedging.
- friendly: Warm, approachable, encouraging. Uses "you" directly. Positive framing.
- technical: Precise, domain-specific vocabulary. Assumes expert audience. Minimal simplification.
- empathetic: Acknowledging, validating, supportive. Emotional awareness. Careful word choice."""


def step_1_local(inputs, context):
    """Parse input and detect current tone characteristics."""
    text = inputs.get("input_text", "").strip()
    if not text or len(text) < 10:
        return None, "Input text too short (minimum 10 characters)"

    target_tone = inputs.get("target_tone", "").strip()
    valid_tones = ["professional", "casual", "authoritative", "friendly", "technical", "empathetic"]
    if target_tone not in valid_tones:
        return None, f"Invalid target_tone: '{target_tone}'. Must be one of: {valid_tones}"

    intensity = inputs.get("intensity", "moderate")
    if intensity not in ("subtle", "moderate", "aggressive"):
        intensity = "moderate"

    preserve = inputs.get("preserve_structure", "true")
    if isinstance(preserve, str):
        preserve = preserve.lower() in ("true", "1", "yes")

    analysis = detect_tone(text)
    analysis["target_tone"] = target_tone
    analysis["intensity"] = intensity
    analysis["preserve_structure"] = preserve
    analysis["original_text"] = text
    analysis["original_numeric_tokens"] = sorted(extract_numeric_tokens(text))

    return {"output": analysis}, None


def step_2_llm(inputs, context):
    """Rewrite text to match target tone profile."""
    analysis = context.get("step_1_output", context.get("_resolved_input", {}))
    if not analysis or not isinstance(analysis, dict):
        return None, "No tone analysis from step 1"

    text = analysis.get("original_text", inputs.get("input_text", ""))
    target_tone = analysis.get("target_tone", "professional")
    intensity = analysis.get("intensity", "moderate")
    preserve = analysis.get("preserve_structure", True)

    length_rule = {
        "subtle": "Stay within ±15% of original length",
        "moderate": "Stay within ±20% of original length",
        "aggressive": f"Stay within ±{'20' if preserve else '30'}% of original length",
    }.get(intensity, "Stay within ±20% of original length")

    preserve_rules = ""
    if preserve:
        preserve_rules = """When preserve_structure = true, you MUST preserve:
- Paragraph count and boundaries
- Bullet/list structure and ordering
- Headings if present
- CTA position if present
- Ordering of ideas within sections"""
    else:
        preserve_rules = """When preserve_structure = false, you MAY:
- Rewrite and merge sentences freely
- Reshape paragraphs
- Reorder phrasing within sections"""

    system = f"""{EXECUTION_ROLE}

TARGET TONE: {target_tone}
INTENSITY: {intensity}
PRESERVE STRUCTURE: {preserve}

CURRENT TONE ANALYSIS:
Formality: {analysis.get('detected_formality', 'unknown')}
Sentence style: {analysis.get('sentence_style', 'unknown')}
Contraction usage: {analysis.get('contraction_usage', 'unknown')}
Emotional warmth: {analysis.get('emotional_warmth', 'unknown')}
Technical density: {analysis.get('technical_density', 'unknown')}
Structure: {analysis.get('structure_signature', 'unknown')}

{TONE_PROFILES}

Length guideline: {length_rule}

{preserve_rules}

CRITICAL NUMERIC PRESERVATION RULES:
You must reproduce EVERY number, percentage, currency value, and date
from the source text EXACTLY as written — character for character.
Do not round, convert, infer, correct, or modify any numeric value.
If the source says "$4.2M", write "$4.2M". If the source says ".2M",
write ".2M". Do NOT guess or reconstruct missing values.

Regardless of preserve_structure, you must NEVER:
- Omit any material fact, number, name, date, or claim
- Insert new facts, claims, or commitments not in the original
- Change numbers, percentages, or quantities IN ANY WAY
- Alter named entities, titles, or product names
- Remove or change calls to action
- "Fix" or "correct" numbers that appear malformed — preserve them as-is

Rewrite the following text to match the {target_tone} tone at {intensity} intensity.
Output ONLY the rewritten text with no preamble, no explanation."""

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": text},
    ]

    content, error = call_resolved(messages, context, max_tokens=6000)
    if error:
        content, error = call_openai(messages, model="gpt-5.4-mini", max_tokens=6000)
    if error:
        return None, error

    # Deterministic numeric check — store violation in context via output key
    # Fix 3: violation info is stored as a separate context key by the runner
    # because the runner stores context[output_key] = output["output"]
    passed, missing, invented = check_numeric_preservation(text, content)
    if not passed:
        parts = []
        if missing: parts.append(f"DROPPED: {sorted(missing)}")
        if invented: parts.append(f"INVENTED: {sorted(invented)}")
        # Numeric violation detected — step_3 will independently verify
        # and force low score. Just return the content.
        return {"output": content}, None

    return {"output": content}, None


def step_3_critic(inputs, context):
    """Evaluate tone match and preservation quality — strict on numeric fidelity."""
    analysis = context.get("step_1_output", {})
    original = analysis.get("original_text", inputs.get("input_text", ""))
    target_tone = analysis.get("target_tone", "professional")
    preserve = analysis.get("preserve_structure", True)

    rewritten = context.get("improved_text", context.get("rewritten_text",
                context.get("step_2_output", "")))
    if isinstance(rewritten, dict):
        rewritten = str(rewritten)
    if not rewritten:
        return None, "No rewritten text to evaluate"

    # Deterministic numeric check BEFORE LLM critic
    num_passed, num_missing, num_invented = check_numeric_preservation(original, rewritten)
    numeric_warning = ""
    forced_low_score = False

    if not num_passed:
        parts = []
        if num_missing: parts.append(f"Numbers DROPPED: {sorted(num_missing)}")
        if num_invented: parts.append(f"Numbers INVENTED: {sorted(num_invented)}")
        numeric_warning = " | ".join(parts)
        forced_low_score = True

    preserve_note = ""
    if preserve:
        preserve_note = """- structure_preservation: Are paragraph count, bullet structure,
  heading structure, idea ordering, and CTA position preserved?

Scoring rule: quality_score = min(tone_accuracy, meaning_preservation, structure_preservation)"""
    else:
        preserve_note = """- structure_preservation: Set to null (not applicable)

Scoring rule: quality_score = min(tone_accuracy, meaning_preservation)"""

    system = f"""You are a strict tone quality evaluator focused on FACTUAL FIDELITY.

You will receive the ORIGINAL text and the REWRITTEN text.
Target tone: {target_tone}
Structure preservation required: {preserve}

Score the rewrite on these dimensions (each 0-10):

- tone_accuracy: How well does the rewrite match the target tone?

- meaning_preservation: How completely is the original meaning preserved?
  THIS IS THE MOST IMPORTANT DIMENSION. Verify EXACT preservation of:
  * Every number, percentage, and numeric value (e.g., 99.9%, 23.4%, $4.2M)
  * Every currency amount — dollar signs, values, multipliers
  * Every named entity — person names, company names, product names, titles
  * Every date, quarter reference, or time reference
  * Every product claim or commitment (e.g., "SOC2 certified", "99.9% uptime")
  * Every call to action (e.g., "click the link", "schedule a demo")

  CRITICAL: If ANY number, percentage, or currency value is missing, changed,
  rounded, converted, or replaced — meaning_preservation MUST be 3 or below.
  Numeric mutation is a CRITICAL failure. If a malformed value like ".2M" was
  changed to "$8.2M" or any other value, score meaning_preservation as 0.

{preserve_note}

Respond with JSON ONLY — no markdown, no backticks, no explanation:
{{"quality_score": N, "tone_accuracy": N, "meaning_preservation": N, "structure_preservation": N, "feedback": "Specific actionable notes"}}"""

    user = f"""ORIGINAL TEXT:
{original}

REWRITTEN TEXT:
{rewritten}

Compare every number, name, date, claim, and CTA between the two texts."""

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    content, error = call_resolved(messages, context, max_tokens=1500)
    if error:
        content, error = call_openai(messages, model="gpt-5.4-mini", max_tokens=1500)
    if error:
        return None, error

    try:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
            cleaned = re.sub(r'\s*```$', '', cleaned)
        parsed = json.loads(cleaned)

        if "quality_score" not in parsed:
            ta = parsed.get("tone_accuracy", 5)
            mp = parsed.get("meaning_preservation", 5)
            sp = parsed.get("structure_preservation")
            if sp is not None and preserve:
                parsed["quality_score"] = min(ta, mp, sp)
            else:
                parsed["quality_score"] = min(ta, mp)

        # Deterministic override: cap scores if numeric check failed
        if forced_low_score:
            parsed["meaning_preservation"] = min(parsed.get("meaning_preservation", 0), 3)
            sp_val = parsed.get("structure_preservation", 10) if preserve else 10
            parsed["quality_score"] = min(
                parsed.get("tone_accuracy", 5),
                parsed["meaning_preservation"],
                sp_val
            )
            parsed["feedback"] = (
                f"NUMERIC VIOLATION: {numeric_warning}. "
                f"Original feedback: {parsed.get('feedback', '')}"
            )
            parsed["numeric_violation"] = numeric_warning

        return {"output": parsed}, None

    except (json.JSONDecodeError, TypeError):
        score = 3 if forced_low_score else 5
        return {"output": {
            "quality_score": score, "tone_accuracy": 5,
            "meaning_preservation": score, "structure_preservation": None,
            "feedback": content,
            "numeric_violation": numeric_warning if forced_low_score else None
        }}, None


def step_4_llm(inputs, context):
    """Improve rewrite based on critic feedback."""
    analysis = context.get("step_1_output", {})
    original = analysis.get("original_text", inputs.get("input_text", ""))
    preserve = analysis.get("preserve_structure", True)

    rewritten = context.get("improved_text", context.get("rewritten_text",
                context.get("step_2_output", "")))
    if isinstance(rewritten, dict):
        rewritten = str(rewritten)

    critic = context.get("step_3_output", {})
    if isinstance(critic, str):
        try:
            critic = json.loads(critic)
        except (json.JSONDecodeError, TypeError):
            critic = {"feedback": critic}

    feedback = critic.get("feedback", "No specific feedback")
    ta = critic.get("tone_accuracy", "?")
    mp = critic.get("meaning_preservation", "?")
    sp = critic.get("structure_preservation", "N/A")
    nv = critic.get("numeric_violation", "")

    preserve_rules = ""
    if preserve:
        preserve_rules = """When preserve_structure = true, you MUST preserve:
- Paragraph count and boundaries
- Bullet/list structure and ordering
- Headings if present
- CTA position if present"""

    nv_instruction = ""
    if nv:
        nv_instruction = f"""
CRITICAL NUMERIC FIX REQUIRED:
The previous rewrite had violations: {nv}
Copy every number, percentage, currency value, and date from the ORIGINAL
exactly as written. If original has ".2M", write ".2M" — not "$8.2M"."""

    system = f"""{EXECUTION_ROLE}

You are improving a tone-calibrated rewrite based on critic feedback.
PRESERVE STRUCTURE: {preserve}
{preserve_rules}

CRITICAL: Reproduce EVERY number, percentage, currency value, and date
from the ORIGINAL TEXT exactly as written. Do not modify any numeric value.
{nv_instruction}

You must NEVER omit or modify facts, numbers, names, dates, or claims.

Address the critic's feedback. Focus on the lowest-scoring dimension.
Output ONLY the improved text with no preamble."""

    user = f"""ORIGINAL TEXT:
{original}

CURRENT REWRITE:
{rewritten}

CRITIC FEEDBACK: {feedback}
TONE ACCURACY: {ta}/10 | MEANING PRESERVATION: {mp}/10 | STRUCTURE: {sp}/10"""

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    content, error = call_resolved(messages, context, max_tokens=6000)
    if error:
        content, error = call_openai(messages, model="gpt-5.4-mini", max_tokens=6000)
    if error:
        return None, error

    return {"output": content}, None


def _select_best_output(context):
    """Mirror the runner's final_output selection logic exactly.
    Fix 4: uses the same candidate/score/fallback logic as skill-runner.py."""
    candidates = [
        {"key": "rewritten_text", "score_from": "step_3_output.quality_score"},
        {"key": "improved_text",  "score_from": "step_3_output.quality_score"},
    ]
    fallback_key = "rewritten_text"

    # highest_quality policy
    best_val, best_score = None, -1
    for cand in candidates:
        val = context.get(cand["key"], "")
        if not val:
            continue
        # Resolve score path
        score = None
        parts = cand["score_from"].split(".")
        cur = context
        for p in parts:
            if isinstance(cur, dict) and p in cur:
                cur = cur[p]
            else:
                cur = None
                break
        if cur is not None:
            try:
                score = float(cur)
            except (ValueError, TypeError):
                pass
        if score is not None and score > best_score:
            best_score = score
            best_val = val
        elif score is None and best_val is None:
            # No scores yet — track as potential fallback
            best_val = val

    if best_val:
        return best_val

    # Fallback: latest non-empty
    for key in ("improved_text", "rewritten_text", "step_2_output"):
        v = context.get(key, "")
        if v and isinstance(v, str):
            return v

    return context.get(fallback_key, "")


def step_5_write(inputs, context):
    """Fix 1: Hard-fail if final numeric preservation check fails."""
    analysis = context.get("step_1_output", {})
    original = analysis.get("original_text", "")

    # Fix 4: Use exact same selection logic as runner
    best = _select_best_output(context)
    if isinstance(best, dict):
        best = str(best)

    if original and best and best != "artifact_written":
        passed, missing, invented = check_numeric_preservation(original, best)
        if not passed:
            parts = []
            if missing: parts.append(f"DROPPED: {sorted(missing)}")
            if invented: parts.append(f"INVENTED: {sorted(invented)}")
            violation = "; ".join(parts)
            # Fix 1: HARD FAIL — do not write artifact with numeric violations
            return None, f"NUMERIC INTEGRITY FAILURE in final output: {violation}"

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
