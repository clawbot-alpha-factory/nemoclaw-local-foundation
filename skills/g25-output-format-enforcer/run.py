#!/usr/bin/env python3
"""
NemoClaw Skill: g25-output-format-enforcer
Output Format Enforcer v1.0.0
F25 | G | internal | transformer
Schema v2 | Runner v4.0+

Transforms LLM output into exact target format. Deterministic fixes first;
LLM reformat only when structural change is needed.

Fix 1: step_2 is local — calls LLM internally only when needed.
Fix 2: Deterministic content-preservation check (factual tokens).
Fix 3: Structured format_spec schema with validation in step_1.
"""

import argparse
import csv
import io
import json
import os
import re
import sys
from datetime import datetime, timezone

import yaml


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


def call_openai(messages, model=None, max_tokens=6000):
    if model is None:
        from lib.routing import resolve_alias
        _, model, _ = resolve_alias("general_short")
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, SystemMessage
    env = load_env()
    key = env.get("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
    if not key: return None, "OPENAI_API_KEY not found"
    llm = ChatOpenAI(model=model, api_key=key, max_tokens=max_tokens, temperature=0.1)
    lc = [SystemMessage(content=m["content"]) if m["role"] == "system" else HumanMessage(content=m["content"]) for m in messages]
    return llm.invoke(lc).content, None


def call_anthropic(messages, model=None, max_tokens=6000):
    if model is None:
        from lib.routing import resolve_alias
        _, model, _ = resolve_alias("complex_reasoning")
    from langchain_anthropic import ChatAnthropic
    from langchain_core.messages import HumanMessage, SystemMessage
    env = load_env()
    key = env.get("ANTHROPIC_API_KEY", os.environ.get("ANTHROPIC_API_KEY", ""))
    if not key: return None, "ANTHROPIC_API_KEY not found"
    llm = ChatAnthropic(model=model, api_key=key, max_tokens=max_tokens, temperature=0.1)
    lc = [SystemMessage(content=m["content"]) if m["role"] == "system" else HumanMessage(content=m["content"]) for m in messages]
    return llm.invoke(lc).content, None


def call_google(messages, model=None, max_tokens=6000):
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


def call_resolved(messages, context, max_tokens=6000):
    m = context.get("resolved_model", "")
    p = context.get("resolved_provider", __import__("lib.routing", fromlist=["resolve_alias"]).resolve_alias("moderate")[0])
    if p == "google": return call_google(messages, model=m, max_tokens=max_tokens)
    if p == "openai": return call_openai(messages, model=m, max_tokens=max_tokens)
    return call_anthropic(messages, model=m, max_tokens=max_tokens)


# ── Preamble / Postamble Detection ───────────────────────────────────────────
PREAMBLE_PATTERNS = [
    re.compile(r"^(?:Here(?:\s+is|'s)|Sure(?:,|\s)|Certainly(?:,|\s)|Of course(?:,|\s)|"
               r"I've|Below is|The following|Let me|Okay,|Alright,|Great,|"
               r"Absolutely(?:,|\s)|Happy to|Sure thing)"
               r"[^\n]{0,200}[:\n]", re.IGNORECASE),
]

POSTAMBLE_PATTERNS = [
    re.compile(r"\n(?:Let me know|Hope this|Feel free|Is there anything|"
               r"Would you like|I hope|This should|Note:|Please note|"
               r"If you need|Don't hesitate|Happy to help|"
               r"---\n).*$", re.IGNORECASE | re.DOTALL),
]


def detect_preamble(text):
    """Returns (has_preamble, end_index)."""
    for pat in PREAMBLE_PATTERNS:
        m = pat.match(text)
        if m:
            return True, m.end()
    return False, 0


def detect_postamble(text):
    """Returns (has_postamble, start_index)."""
    for pat in POSTAMBLE_PATTERNS:
        m = pat.search(text)
        if m:
            return True, m.start()
    return False, len(text)


def detect_fences(text):
    return text.strip().startswith("```")


def strip_code_fences(text):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r'^```(?:\w+)?\s*\n?', '', text)
        text = re.sub(r'\n?\s*```\s*$', '', text)
    return text.strip()


def apply_preamble_strip(text):
    for pat in PREAMBLE_PATTERNS:
        m = pat.match(text)
        if m:
            remaining = text[m.end():].strip()
            if remaining:
                return remaining
    return text


def apply_postamble_strip(text):
    for pat in POSTAMBLE_PATTERNS:
        m = pat.search(text)
        if m:
            trimmed = text[:m.start()].strip()
            if trimmed:
                return trimmed
    return text


# ── Factual Token Extraction (Fix 2) ─────────────────────────────────────────
FACTUAL_TOKEN_PATTERNS = [
    # Currency: $4.2M, €50K, $100
    re.compile(r'[\$€£¥]\s*\.?\d[\d,]*\.?\d*\s*[KMBTkmbt]?', re.IGNORECASE),
    # Percentages: 99.9%, 23.4%
    re.compile(r'\.?\d[\d,]*\.?\d*\s*%'),
    # URLs
    re.compile(r'https?://[^\s<>"\']+'),
    # Email addresses
    re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'),
    # Dates: YYYY-MM-DD, MM/DD/YYYY
    re.compile(r'\b\d{4}-\d{2}-\d{2}\b'),
    re.compile(r'\b\d{1,2}/\d{1,2}/\d{2,4}\b'),
    # Numbers with units: 4.2M, 100K
    re.compile(r'\b\d[\d,]*\.?\d*\s*[KMBTkmbt]\b'),
    # Version numbers: v1.0.0, 3.12.13
    re.compile(r'\bv?\d+\.\d+(?:\.\d+)+\b'),
    # Large standalone numbers: 1,000,000 or 10000+
    re.compile(r'\b\d{1,3}(?:,\d{3})+(?:\.\d+)?\b'),
    # Decimal numbers with 1+ decimal places: 99.9, 4.2
    re.compile(r'\b\d+\.\d+\b'),
]


def extract_factual_tokens(text):
    """Extract all factual tokens (numbers, URLs, emails, identifiers)."""
    tokens = set()
    for pat in FACTUAL_TOKEN_PATTERNS:
        for match in pat.finditer(text):
            token = match.group().strip()
            if len(token) >= 2:
                tokens.add(token)
    return tokens


def check_content_preservation(original, transformed):
    """Verify factual tokens are preserved. Returns (passed, missing, invented)."""
    orig_tokens = extract_factual_tokens(original)
    trans_tokens = extract_factual_tokens(transformed)

    missing = orig_tokens - trans_tokens
    invented = trans_tokens - orig_tokens

    # Filter noise: very short generic tokens
    missing = {t for t in missing if len(t) >= 2}
    invented = {t for t in invented if len(t) >= 2}

    return len(missing) == 0, missing, invented


# ── Format Detection ──────────────────────────────────────────────────────────
def detect_current_format(text):
    cleaned = strip_code_fences(text).strip()

    try:
        json.loads(cleaned)
        return "json"
    except (json.JSONDecodeError, TypeError):
        pass

    try:
        parsed = yaml.safe_load(cleaned)
        if isinstance(parsed, dict) and len(parsed) > 1:
            return "yaml"
    except yaml.YAMLError:
        pass

    lines = cleaned.split("\n")
    if len(lines) >= 2:
        try:
            reader = csv.reader(io.StringIO(cleaned))
            rows = list(reader)
            if len(rows) >= 2:
                col_counts = [len(r) for r in rows if r]
                if col_counts and len(set(col_counts)) == 1 and col_counts[0] >= 2:
                    return "csv"
        except csv.Error:
            pass

    if re.search(r'^#{1,6}\s', cleaned, re.MULTILINE):
        return "markdown"

    return "prose"


def detect_double_format(text, target_format):
    """Detect double formatting: JSON inside markdown fences, YAML inside prose, etc."""
    issues = []
    cleaned = text.strip()

    if target_format == "prose":
        if re.search(r'^\s*\{.*\}\s*$', cleaned, re.DOTALL):
            issues.append("Prose output appears to be JSON")
        if re.search(r'^\w+:\s', cleaned) and "\n" in cleaned:
            try:
                yaml.safe_load(cleaned)
                if isinstance(yaml.safe_load(cleaned), dict):
                    issues.append("Prose output appears to be YAML")
            except yaml.YAMLError:
                pass

    if target_format in ("json", "yaml") and cleaned.startswith("```"):
        issues.append(f"{target_format.upper()} output is wrapped in code fences")

    return issues


# ── Format Spec Validation (Fix 3) ───────────────────────────────────────────
VALID_SPEC_KEYS = {"required_keys", "required_sections", "max_length",
                   "min_length", "column_headers"}


def parse_format_spec(spec_str):
    """Parse and validate format_spec JSON. Returns (parsed: dict, error: str|None)."""
    if not spec_str or not spec_str.strip():
        return {}, None

    try:
        parsed = json.loads(spec_str)
    except (json.JSONDecodeError, TypeError) as e:
        return None, f"format_spec is not valid JSON: {str(e)[:200]}"

    if not isinstance(parsed, dict):
        return None, f"format_spec must be a JSON object, got {type(parsed).__name__}"

    unknown_keys = set(parsed.keys()) - VALID_SPEC_KEYS
    if unknown_keys:
        return None, f"format_spec has unknown keys: {sorted(unknown_keys)}. Valid: {sorted(VALID_SPEC_KEYS)}"

    for list_key in ("required_keys", "required_sections", "column_headers"):
        if list_key in parsed:
            if not isinstance(parsed[list_key], list):
                return None, f"format_spec.{list_key} must be a list"
            if not all(isinstance(v, str) for v in parsed[list_key]):
                return None, f"format_spec.{list_key} must contain only strings"

    for int_key in ("max_length", "min_length"):
        if int_key in parsed:
            if not isinstance(parsed[int_key], int) or parsed[int_key] < 0:
                return None, f"format_spec.{int_key} must be a non-negative integer"

    return parsed, None


# ── Format Validation ─────────────────────────────────────────────────────────
def validate_format(text, target_format, format_spec_parsed):
    """Validate text matches target format. Returns (valid: bool, issues: list[str])."""
    issues = []

    if not text or not text.strip():
        return False, ["Output is empty"]

    cleaned = text.strip()

    # Length checks from spec
    if "max_length" in format_spec_parsed:
        if len(cleaned) > format_spec_parsed["max_length"]:
            issues.append(f"Output exceeds max_length: {len(cleaned)} > {format_spec_parsed['max_length']}")
    if "min_length" in format_spec_parsed:
        if len(cleaned) < format_spec_parsed["min_length"]:
            issues.append(f"Output below min_length: {len(cleaned)} < {format_spec_parsed['min_length']}")

    if target_format == "json":
        try:
            parsed = json.loads(cleaned)
        except (json.JSONDecodeError, TypeError) as e:
            return False, [f"Invalid JSON: {str(e)[:200]}"]

        for key in format_spec_parsed.get("required_keys", []):
            if isinstance(parsed, dict) and key not in parsed:
                issues.append(f"Missing required JSON key: '{key}'")

    elif target_format == "yaml":
        try:
            parsed = yaml.safe_load(cleaned)
            if not isinstance(parsed, dict):
                issues.append(f"YAML did not produce a dict — got {type(parsed).__name__}")
        except yaml.YAMLError as e:
            return False, [f"Invalid YAML: {str(e)[:200]}"]

    elif target_format == "markdown":
        for section in format_spec_parsed.get("required_sections", []):
            if section.lower() not in cleaned.lower():
                issues.append(f"Missing required section: '{section}'")

    elif target_format == "prose":
        # No JSON or YAML structures
        try:
            json.loads(cleaned)
            issues.append("Prose output is actually valid JSON — format mismatch")
        except (json.JSONDecodeError, TypeError):
            pass
        # No remaining fences
        if cleaned.startswith("```"):
            issues.append("Prose output still contains code fences")

    elif target_format == "csv":
        try:
            reader = csv.reader(io.StringIO(cleaned))
            rows = list(reader)
            if len(rows) < 1:
                issues.append("CSV has no rows")
            else:
                col_counts = [len(r) for r in rows if r]
                if col_counts and len(set(col_counts)) > 1:
                    issues.append(f"Inconsistent CSV column counts: {set(col_counts)}")
                expected_headers = format_spec_parsed.get("column_headers", [])
                if expected_headers and rows:
                    for h in expected_headers:
                        if h not in rows[0]:
                            issues.append(f"Missing CSV header: '{h}'")
        except csv.Error as e:
            issues.append(f"CSV parse error: {str(e)[:200]}")

    # Double formatting check
    double_issues = detect_double_format(cleaned, target_format)
    issues.extend(double_issues)

    return len(issues) == 0, issues


# ── Step Handlers ─────────────────────────────────────────────────────────────

def step_1_local(inputs, context):
    """Detect format violations and classify repair needs."""
    text = inputs.get("input_text", "").strip()
    if not text:
        return None, "input_text is empty"

    target = inputs.get("target_format", "").strip()
    if target not in ("json", "yaml", "markdown", "prose", "csv"):
        return None, f"Invalid target_format: '{target}'"

    # Fix 3: Parse and validate format_spec
    spec_str = inputs.get("format_spec", "").strip()
    format_spec, spec_error = parse_format_spec(spec_str)
    if spec_error:
        return None, f"format_spec validation failed: {spec_error}"

    do_strip_preamble = inputs.get("strip_preamble", "true")
    do_strip_postamble = inputs.get("strip_postamble", "true")
    do_strip_fences = inputs.get("strip_fences", "true")
    do_preserve = inputs.get("preserve_content", "true")

    # Normalize booleans from string
    for name in ("do_strip_preamble", "do_strip_postamble", "do_strip_fences", "do_preserve"):
        val = locals()[name]
        if isinstance(val, str):
            locals()[name] = val.lower() in ("true", "1", "yes")

    do_strip_preamble = do_strip_preamble if isinstance(do_strip_preamble, bool) else str(do_strip_preamble).lower() in ("true", "1", "yes")
    do_strip_postamble = do_strip_postamble if isinstance(do_strip_postamble, bool) else str(do_strip_postamble).lower() in ("true", "1", "yes")
    do_strip_fences = do_strip_fences if isinstance(do_strip_fences, bool) else str(do_strip_fences).lower() in ("true", "1", "yes")
    do_preserve = do_preserve if isinstance(do_preserve, bool) else str(do_preserve).lower() in ("true", "1", "yes")

    # Detect violations
    has_fences = detect_fences(text)
    has_preamble, preamble_end = detect_preamble(text)
    has_postamble, postamble_start = detect_postamble(text)
    current_format = detect_current_format(text)
    format_mismatch = (current_format != target)
    double_issues = detect_double_format(text, target)

    # Classify repair type
    needs_llm = False
    if format_mismatch and current_format != "prose":
        # Structural reformat needed (e.g., prose → json)
        needs_llm = True
    elif format_mismatch and target not in ("prose", "markdown"):
        # Need to create structured format from prose
        needs_llm = True

    # Extract factual tokens for preservation check
    factual_tokens = sorted(extract_factual_tokens(text))

    result = {
        "original_text": text,
        "target_format": target,
        "format_spec": format_spec,
        "strip_preamble": do_strip_preamble,
        "strip_postamble": do_strip_postamble,
        "strip_fences": do_strip_fences,
        "preserve_content": do_preserve,
        "factual_tokens": factual_tokens,
        "violations": {
            "has_fences": has_fences,
            "has_preamble": has_preamble,
            "has_postamble": has_postamble,
            "format_mismatch": format_mismatch,
            "current_format": current_format,
            "double_format_issues": double_issues,
        },
        "needs_llm_reformat": needs_llm,
    }

    return {"output": result}, None


def step_2_local(inputs, context):
    """Apply deterministic fixes. Call LLM only if structural reformat needed."""
    analysis = context.get("step_1_output", context.get("_resolved_input", {}))
    if not analysis or not isinstance(analysis, dict):
        return None, "No analysis from step 1"

    text = analysis.get("original_text", "")
    target = analysis.get("target_format", "prose")
    spec = analysis.get("format_spec", {})
    violations = analysis.get("violations", {})
    needs_llm = analysis.get("needs_llm_reformat", False)

    # ── Phase 1: Deterministic fixes ──────────────────────────────────────
    result = text

    if analysis.get("strip_fences") and violations.get("has_fences"):
        result = strip_code_fences(result)

    if analysis.get("strip_preamble") and violations.get("has_preamble"):
        result = apply_preamble_strip(result)

    if analysis.get("strip_postamble") and violations.get("has_postamble"):
        result = apply_postamble_strip(result)

    # Re-strip fences after preamble/postamble removal — fences may have
    # been hidden behind preamble (e.g., "Here is the JSON:\n```json\n...")
    if analysis.get("strip_fences") and detect_fences(result):
        result = strip_code_fences(result)

    # ── Phase 2: Check if deterministic fix was enough ────────────────────
    # Always validate, even if step_1 said needs_llm — deterministic fixes
    # may have been sufficient (e.g., preamble + fence strip reveals valid JSON)
    after_det = result.strip()
    valid, issues = validate_format(after_det, target, spec)
    if valid:
        return {"output": after_det}, None

    # Quick format-specific parse check before falling through to LLM
    if target == "json":
        try:
            json.loads(after_det)
            return {"output": after_det}, None
        except (json.JSONDecodeError, TypeError):
            pass
    elif target == "yaml":
        try:
            parsed = yaml.safe_load(after_det)
            if isinstance(parsed, dict):
                return {"output": after_det}, None
        except yaml.YAMLError:
            pass
    elif target in ("prose", "markdown", "csv") and not needs_llm:
        # Deterministic fix was our best shot for these formats
        return {"output": after_det}, None

    # ── Phase 3: LLM reformat (only when needed) ─────────────────────────
    spec_instruction = ""
    if spec:
        spec_instruction = f"\nFORMAT REQUIREMENTS:\n{json.dumps(spec, indent=2)}"

    system = f"""You are a precise format converter. Your ONLY job is to restructure the
given text into {target} format.

RULES — absolute, no exceptions:
1. Preserve ALL factual content: every number, name, URL, email, date, claim.
2. Do NOT add commentary, explanation, preamble, or postamble.
3. Do NOT add new facts, opinions, or content not in the source.
4. Do NOT wrap output in markdown code fences.
5. Output ONLY the reformatted content in {target} format.
{spec_instruction}

{"Required JSON keys: " + ", ".join(spec.get("required_keys", [])) if spec.get("required_keys") else ""}
{"Required sections: " + ", ".join(spec.get("required_sections", [])) if spec.get("required_sections") else ""}"""

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Convert this to {target} format:\n\n{after_det}"},
    ]

    content, error = call_resolved(messages, context, max_tokens=6000)
    if error:
        content, error = call_openai(messages, max_tokens=6000)
    if error:
        return None, error

    # Strip any fences the LLM added
    content = strip_code_fences(content)
    content = apply_preamble_strip(content)

    return {"output": content}, None


def step_3_local(inputs, context):
    """Validate format compliance and content preservation."""
    analysis = context.get("step_1_output", {})
    target = analysis.get("target_format", "prose")
    spec = analysis.get("format_spec", {})
    original = analysis.get("original_text", "")
    do_preserve = analysis.get("preserve_content", True)
    original_tokens = set(analysis.get("factual_tokens", []))

    enforced = context.get("enforced_text", context.get("step_2_output", ""))
    if isinstance(enforced, dict):
        enforced = str(enforced)
    if not enforced:
        return None, "No enforced text to validate"

    issues = []

    # ── Format validation ─────────────────────────────────────────────────
    valid, format_issues = validate_format(enforced, target, spec)
    issues.extend(format_issues)

    # ── Content preservation check (Fix 2) ────────────────────────────────
    content_passed = True
    missing_tokens = set()
    if do_preserve and original:
        content_passed, missing_tokens, _ = check_content_preservation(
            original, enforced)
        if not content_passed and missing_tokens:
            issues.append(
                f"Content preservation failed — missing factual tokens: "
                f"{sorted(missing_tokens)}")

    # ── Remaining fence/preamble check ────────────────────────────────────
    if analysis.get("strip_fences") and detect_fences(enforced):
        issues.append("Code fences still present after enforcement")
    if analysis.get("strip_preamble"):
        has_pre, _ = detect_preamble(enforced)
        if has_pre:
            issues.append("Preamble still present after enforcement")
    if analysis.get("strip_postamble"):
        has_post, _ = detect_postamble(enforced)
        if has_post:
            issues.append("Postamble still present after enforcement")

    result = {
        "format_valid": valid and len(issues) == 0,
        "format_issues": format_issues,
        "content_preserved": content_passed,
        "missing_tokens": sorted(missing_tokens) if missing_tokens else [],
        "all_issues": issues,
        "issue_count": len(issues),
    }

    if issues:
        return None, f"Validation failed ({len(issues)} issues): " + "; ".join(issues[:5])

    return {"output": result}, None


def step_4_write(inputs, context):
    """Write validated output artifact."""
    enforced = context.get("enforced_text", context.get("step_2_output", ""))
    if isinstance(enforced, dict):
        enforced = str(enforced)

    # Verify step_3 passed
    step3 = context.get("step_3_output", {})
    if isinstance(step3, dict) and not step3.get("format_valid", False):
        return None, "Cannot write artifact — format validation did not pass"

    if not enforced or not enforced.strip():
        return None, "No content to write"

    return {"output": "artifact_written"}, None


STEP_HANDLERS = {
    "step_1": step_1_local,
    "step_2": step_2_local,
    "step_3": step_3_local,
    "step_4": step_4_write,
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
