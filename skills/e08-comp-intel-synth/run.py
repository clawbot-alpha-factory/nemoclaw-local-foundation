#!/usr/bin/env python3
"""
NemoClaw Skill: e08-comp-intel-synth
Competitive Intelligence Synthesizer v1.0.0
F08 | E | dual-use | executor
Schema v2 | Runner v4.0+

Fix 1: Factual token extraction in step_1, deterministic preservation in step_3/5.
Fix 2: Competitor coverage requires analytical statement, not just mention.
Fix 3: SWOT must be structured non-empty lists.
Fix 4: Explicit "no external knowledge" in step_2 prompt.
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
    llm = ChatOpenAI(model=model, api_key=key, max_tokens=max_tokens, temperature=0.3)
    lc = [SystemMessage(content=m["content"]) if m["role"] == "system" else HumanMessage(content=m["content"]) for m in messages]
    return llm.invoke(lc).content, None


def call_anthropic(messages, model="claude-sonnet-4-6", max_tokens=6000):
    from langchain_anthropic import ChatAnthropic
    from langchain_core.messages import HumanMessage, SystemMessage
    env = load_env()
    key = env.get("ANTHROPIC_API_KEY", os.environ.get("ANTHROPIC_API_KEY", ""))
    if not key: return None, "ANTHROPIC_API_KEY not found"
    llm = ChatAnthropic(model=model, api_key=key, max_tokens=max_tokens, temperature=0.3)
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


# ── Factual Token Extraction (Fix 1 — same pattern as F35) ───────────────────
FACTUAL_PATTERNS = [
    re.compile(r'[\$€£¥]\s*\.?\d[\d,]*\.?\d*\s*[KMBTkmbt]?', re.IGNORECASE),
    re.compile(r'\.?\d[\d,]*\.?\d*\s*%'),
    re.compile(r'\b\d{4}-\d{2}-\d{2}\b'),
    re.compile(r'\b\d{1,2}/\d{1,2}/\d{2,4}\b'),
    re.compile(r'\b(?:January|February|March|April|May|June|July|August|'
               r'September|October|November|December)\s+\d{1,2},?\s*\d{4}\b', re.IGNORECASE),
    re.compile(r'\bQ[1-4]\s*\d{0,4}\b'),
    re.compile(r'\.?\d[\d,]*\.?\d*\s*[KMBTkmbt]\b'),
    re.compile(r'\b\d{1,3}(?:,\d{3})+(?:\.\d+)?\b'),
    re.compile(r'\b\d+\.\d+\b'),
]


def extract_factual_tokens(text):
    tokens = set()
    for pat in FACTUAL_PATTERNS:
        for match in pat.finditer(text):
            token = match.group().strip()
            if len(token) >= 2:
                tokens.add(token)
    return tokens


def check_factual_preservation(original_text, report_text):
    orig = extract_factual_tokens(original_text)
    report = extract_factual_tokens(report_text)
    missing = orig - report
    invented = report - orig
    missing = {t for t in missing if len(t) >= 2}
    invented = {t for t in invented if len(t) >= 3}
    return len(missing) == 0, missing, invented


# ── Competitor Name Extraction ────────────────────────────────────────────────
def extract_competitor_names(text, focus_company):
    """Extract likely company/competitor names from text.
    Uses heuristic: capitalized multi-word phrases, known patterns."""
    names = set()
    # Look for patterns: "Company Name", "CompanyName", names after keywords
    for pattern in [
        re.compile(r'(?:competitor|company|firm|startup|player|rival)[\s:]+([A-Z][A-Za-z0-9\s&.]+?)(?:[,.\n]|$)', re.IGNORECASE),
        re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b'),  # Multi-word capitalized
        re.compile(r'\b([A-Z][A-Za-z0-9]+(?:\.[A-Za-z]+)?)\b'),  # CamelCase or Corp.
    ]:
        for match in pattern.finditer(text):
            name = match.group(1).strip()
            if len(name) >= 2 and name.lower() != focus_company.lower():
                # Filter common non-names
                skip = {"The", "This", "That", "These", "Those", "What", "When",
                        "Where", "Which", "January", "February", "March", "April",
                        "May", "June", "July", "August", "September", "October",
                        "November", "December", "Monday", "Tuesday", "Wednesday",
                        "Thursday", "Friday", "SWOT", "Strengths", "Weaknesses",
                        "Opportunities", "Threats", "Executive", "Summary",
                        "Market", "Analysis", "Strategic", "Recommendations",
                        "Revenue", "Funding", "Series", "Product", "Team"}
                if name not in skip and len(name) <= 50:
                    names.add(name)
    return names


# ── Report Structure Validation ───────────────────────────────────────────────
REQUIRED_SECTIONS = [
    "executive summary",
    "competitor",       # "Competitor Profiles" or "Competitor Analysis"
    "swot",             # "SWOT Analysis"
    "positioning",      # "Market Positioning"
    "recommendation",   # "Strategic Recommendations"
]

BANNED_FLUFF = [
    "leverage synergies", "optimize positioning", "drive innovation forward",
    "best-in-class solution", "paradigm shift", "move the needle",
    "low-hanging fruit", "circle back", "synergistic approach",
    "thought leadership", "value proposition alignment",
]


def validate_report_structure(report, competitor_names, factual_tokens_orig,
                              report_depth):
    """Full deterministic validation. Returns (issues: list[str])."""
    issues = []
    report_lower = report.lower()

    # ── Required sections ─────────────────────────────────────────────────
    for section in REQUIRED_SECTIONS:
        if section not in report_lower:
            issues.append(f"Missing required section containing '{section}'")

    # ── SWOT structure: must be lists, non-empty (Fix 3) ─────────────────
    swot_section = ""
    swot_match = re.search(r'(?:##\sSWOT.*?)(?=\n##\s[^#]|\Z)', report,
                           re.IGNORECASE | re.DOTALL)
    if swot_match:
        swot_section = swot_match.group()

    swot_subsections = ["strength", "weakness", "opportunit", "threat"]
    for sub in swot_subsections:
        if sub not in report_lower:
            issues.append(f"SWOT missing subsection: '{sub}*'")
        else:
            # Check that subsection has list items (bullet points)
            sub_pattern = re.compile(
                rf'(?:###?\s*{sub}\w*)(.*?)(?=\n##|\Z)',
                re.IGNORECASE | re.DOTALL)
            sub_match = sub_pattern.search(report)
            if sub_match:
                sub_content = sub_match.group(1)
                bullet_count = len(re.findall(r'^\s*[-*•]\s', sub_content, re.MULTILINE))
                if bullet_count == 0:
                    issues.append(
                        f"SWOT '{sub}*' section has no bullet points — "
                        f"must be structured as a list")

    # ── Competitor coverage: analytical statement, not just mention (Fix 2)
    for name in competitor_names:
        name_lower = name.lower()
        if name_lower not in report_lower:
            issues.append(f"Competitor '{name}' not mentioned in report")
        else:
            # Check for analytical statement near the name
            # Find sentences containing the competitor name
            sentences = re.split(r'[.!?]\s+', report)
            mentions = [s for s in sentences if name_lower in s.lower()]
            has_analysis = False
            analysis_markers = [
                "strength", "weakness", "advantage", "disadvantag", "competit",
                "market share", "revenue", "growth", "position", "strateg",
                "pricing", "product", "threat", "opportunit", "risk",
                "differentiat", "focus", "target", "challenge", "lead",
            ]
            for mention in mentions:
                mention_lower = mention.lower()
                if any(marker in mention_lower for marker in analysis_markers):
                    has_analysis = True
                    break
            if not has_analysis and len(mentions) <= 1:
                issues.append(
                    f"Competitor '{name}' mentioned but lacks analytical statement")

    # ── Factual token preservation (Fix 1) ────────────────────────────────
    if factual_tokens_orig:
        passed, missing, invented = check_factual_preservation(
            " ".join(factual_tokens_orig), report)
        if not passed and missing:
            # Only flag if significant tokens are missing
            sig_missing = {t for t in missing if len(t) >= 3}
            if sig_missing:
                issues.append(
                    f"Factual tokens from input missing in report: "
                    f"{sorted(list(sig_missing)[:10])}")

    # ── Banned fluff ──────────────────────────────────────────────────────
    for phrase in BANNED_FLUFF:
        if phrase in report_lower:
            issues.append(f"Report contains banned fluff phrase: '{phrase}'")

    # ── Depth check ───────────────────────────────────────────────────────
    word_count = len(report.split())
    if report_depth == "brief" and word_count > 2000:
        issues.append(f"Brief report too long: {word_count} words (target <1000)")
    elif report_depth == "comprehensive" and word_count < 1500:
        issues.append(f"Comprehensive report too short: {word_count} words (target 2500+)")

    return issues


# ── Step Handlers ─────────────────────────────────────────────────────────────

EXECUTION_ROLE = """You are a senior competitive intelligence analyst with expertise in market
research, strategic analysis frameworks (SWOT, Porter's Five Forces), and
executive-level report writing. You synthesize ONLY the data provided to you
into clear, actionable intelligence.

CRITICAL RULE: You must NEVER use external knowledge, industry assumptions,
or general market data that is not explicitly present in the input. If data
is insufficient for a particular analysis point, you must state "Insufficient
data provided" rather than guessing or inferring. Every claim in your report
must be traceable to the provided input data."""


def step_1_local(inputs, context):
    """Parse competitor data and structure analysis inputs."""
    data = inputs.get("competitor_data", "").strip()
    if not data or len(data) < 50:
        return None, "competitor_data too short (minimum 50 characters)"

    focus = inputs.get("focus_company", "").strip()
    if not focus:
        return None, "focus_company is required"

    industry = inputs.get("industry_context", "").strip()
    if not industry or len(industry) < 10:
        return None, "industry_context too short (minimum 10 characters)"

    priorities = inputs.get("analysis_priorities",
                            "General competitive landscape with balanced coverage").strip()
    depth = inputs.get("report_depth", "standard").strip()
    if depth not in ("brief", "standard", "comprehensive"):
        depth = "standard"

    # Extract competitor names
    competitors = extract_competitor_names(data, focus)

    # Extract factual tokens for preservation check (Fix 1)
    factual_tokens = sorted(extract_factual_tokens(data))

    # Detect data completeness
    data_lower = data.lower()
    data_areas = {
        "pricing": any(w in data_lower for w in ["price", "pricing", "cost", "$", "€"]),
        "funding": any(w in data_lower for w in ["fund", "invest", "series", "raised", "valuation"]),
        "team": any(w in data_lower for w in ["team", "employee", "headcount", "ceo", "founder"]),
        "product": any(w in data_lower for w in ["product", "feature", "service", "platform"]),
        "revenue": any(w in data_lower for w in ["revenue", "arr", "mrr", "sales", "income"]),
        "market_share": any(w in data_lower for w in ["market share", "share", "penetration"]),
    }
    missing_areas = [k for k, v in data_areas.items() if not v]

    # Depth parameters
    depth_config = {
        "brief": {"sections": "condensed", "swot_depth": "top 2-3 per category",
                   "rec_count": "2-3 prioritized"},
        "standard": {"sections": "full", "swot_depth": "3-5 per category",
                      "rec_count": "4-6 prioritized"},
        "comprehensive": {"sections": "detailed with subsections",
                           "swot_depth": "5+ per category with evidence",
                           "rec_count": "6-10 with implementation notes"},
    }

    result = {
        "competitor_data": data,
        "focus_company": focus,
        "industry_context": industry,
        "analysis_priorities": priorities,
        "report_depth": depth,
        "depth_config": depth_config.get(depth, depth_config["standard"]),
        "competitor_names": sorted(competitors),
        "factual_tokens": factual_tokens,
        "data_areas": data_areas,
        "missing_areas": missing_areas,
        "word_count": len(data.split()),
    }

    return {"output": result}, None


def step_2_llm(inputs, context):
    """Generate competitive intelligence report."""
    analysis = context.get("step_1_output", context.get("_resolved_input", {}))
    if not analysis or not isinstance(analysis, dict):
        return None, "No analysis from step 1"

    data = analysis.get("competitor_data", "")
    focus = analysis.get("focus_company", "")
    industry = analysis.get("industry_context", "")
    priorities = analysis.get("analysis_priorities", "")
    depth = analysis.get("report_depth", "standard")
    depth_cfg = analysis.get("depth_config", {})
    competitors = analysis.get("competitor_names", [])
    missing_areas = analysis.get("missing_areas", [])

    missing_note = ""
    if missing_areas:
        missing_note = f"""
DATA GAPS DETECTED — the following areas have little or no data in the input:
{', '.join(missing_areas)}
You MUST acknowledge these gaps in your report rather than fabricating data.
Include a "Data Limitations" subsection in the Executive Summary noting what
data was insufficient for complete analysis."""

    competitor_note = ""
    if competitors:
        competitor_note = f"""
IDENTIFIED COMPETITORS (each must receive dedicated analytical coverage):
{', '.join(competitors)}
Each competitor must have at least one analytical statement in the Competitor
Profiles section — not just a mention."""

    # Fix 4: Explicit no external knowledge rule
    system = f"""{EXECUTION_ROLE}

FOCUS COMPANY: {focus}
INDUSTRY: {industry}
ANALYSIS PRIORITIES: {priorities}
REPORT DEPTH: {depth} — {json.dumps(depth_cfg)}
{competitor_note}
{missing_note}

REPORT STRUCTURE — produce ALL of these sections as markdown headings:

## Executive Summary
Brief overview of competitive landscape. Include Data Limitations if gaps exist.

## Competitor Profiles
Dedicated subsection for each competitor with analytical assessment.
Each competitor MUST have substantive analysis, not just a name mention.

## SWOT Analysis
Structured as:
### Strengths
- [evidence-based point grounded in input data]

### Weaknesses
- [evidence-based point grounded in input data]

### Opportunities
- [evidence-based point grounded in input data]

### Threats
- [evidence-based point grounded in input data]

Each SWOT point MUST be a bullet item. Each point MUST reference specific
information from the provided input data. If evidence is insufficient,
state the assumption explicitly.

## Market Positioning
Relative positioning of focus company vs competitors based on input data.

## Strategic Recommendations
Numbered, prioritized recommendations. Each recommendation MUST be linked
to a specific SWOT finding or positioning insight. Format:
1. **[Recommendation title]** — [rationale linked to SWOT/positioning]

ABSOLUTE RULES:
1. Use ONLY the data provided below. Do NOT use external knowledge.
2. Do NOT fabricate statistics, market sizes, growth rates, or any numbers
   not present in the input.
3. If data is missing for an analysis point, write "Insufficient data provided"
   instead of guessing.
4. Preserve ALL numbers, percentages, currency values, and dates from the
   input exactly as written.
5. Do NOT use banned phrases: "leverage synergies", "optimize positioning",
   "paradigm shift", "move the needle", "low-hanging fruit", "best-in-class".
6. Every strategic recommendation must cite which SWOT element or positioning
   insight supports it.

Output ONLY the markdown report. No preamble, no explanation."""

    user = f"""COMPETITOR DATA:
{data}

Generate the {depth} competitive intelligence report for {focus}."""

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    content, error = call_resolved(messages, context, max_tokens=8000)
    if error:
        content, error = call_openai(messages, model="gpt-5.4-mini", max_tokens=8000)
    if error:
        return None, error

    return {"output": content}, None


def step_3_critic(inputs, context):
    """Two-layer validation: deterministic then LLM."""
    analysis = context.get("step_1_output", {})
    competitor_names = set(analysis.get("competitor_names", []))
    factual_tokens = analysis.get("factual_tokens", [])
    focus = analysis.get("focus_company", "")
    depth = analysis.get("report_depth", "standard")
    original_data = analysis.get("competitor_data", "")

    report = context.get("improved_report", context.get("generated_report",
             context.get("step_2_output", "")))
    if isinstance(report, dict):
        report = str(report)
    if not report:
        return None, "No report to evaluate"

    # ── Layer 1: Deterministic validation ─────────────────────────────────
    det_issues = validate_report_structure(
        report, competitor_names, factual_tokens, depth)

    det_penalty = len(det_issues)
    structural_score = max(0, 10 - (det_penalty * 2))

    if structural_score <= 2:
        return {"output": {
            "quality_score": structural_score,
            "structural_score": structural_score,
            "analytical_depth": 0,
            "grounding_score": 0,
            "deterministic_issues": det_issues,
            "llm_feedback": "Too many structural issues — fix deterministic failures first",
            "feedback": f"STRUCTURAL ({len(det_issues)} issues): " + " | ".join(det_issues[:8]),
        }}, None

    # ── Layer 2: LLM quality evaluation ───────────────────────────────────
    system = """You are a strict competitive intelligence report evaluator.

Score these dimensions (each 0-10):

- analytical_depth: Does the report go beyond surface-level observations?
  Are competitor profiles substantive? Are SWOT points specific and actionable?
  Are recommendations concrete with clear rationale?

- grounding_score: Is every claim traceable to the provided input data?
  Are there fabricated statistics or market data not in the input?
  CRITICAL: Every SWOT element must reference specific information from the
  input. If a SWOT point cannot be traced to the input, score below 5.
  This is the competitive intelligence equivalent of numeric preservation —
  fabricated analysis is a critical failure.

Respond with JSON ONLY — no markdown, no backticks:
{"analytical_depth": N, "grounding_score": N, "llm_feedback": "Specific notes"}"""

    user = f"""ORIGINAL INPUT DATA:
{original_data[:3000]}

GENERATED REPORT:
{report}

FOCUS COMPANY: {focus}

Evaluate analytical depth and grounding in input data. Flag any claims that
appear fabricated or not traceable to the input."""

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    content, error = call_resolved(messages, context, max_tokens=1500)
    if error:
        content, error = call_openai(messages, model="gpt-5.4-mini", max_tokens=1500)

    llm_scores = {"analytical_depth": 5, "grounding_score": 5, "llm_feedback": ""}
    if not error and content:
        try:
            cleaned = content.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
                cleaned = re.sub(r'\s*```$', '', cleaned)
            llm_scores = json.loads(cleaned)
        except (json.JSONDecodeError, TypeError):
            llm_scores["llm_feedback"] = content

    depth_score = llm_scores.get("analytical_depth", 5)
    grounding = llm_scores.get("grounding_score", 5)
    quality_score = min(structural_score, depth_score, grounding)

    feedback_parts = []
    if det_issues:
        feedback_parts.append(
            f"STRUCTURAL ({len(det_issues)}): " + " | ".join(det_issues[:8]))
    llm_fb = llm_scores.get("llm_feedback", "")
    if llm_fb:
        feedback_parts.append(f"QUALITY: {llm_fb}")

    return {"output": {
        "quality_score": quality_score,
        "structural_score": structural_score,
        "analytical_depth": depth_score,
        "grounding_score": grounding,
        "deterministic_issues": det_issues,
        "llm_feedback": llm_fb,
        "feedback": " || ".join(feedback_parts) if feedback_parts else "All checks passed",
    }}, None


def step_4_llm(inputs, context):
    """Strengthen report based on critic feedback."""
    analysis = context.get("step_1_output", {})
    original_data = analysis.get("competitor_data", "")
    focus = analysis.get("focus_company", "")
    competitors = analysis.get("competitor_names", [])

    report = context.get("improved_report", context.get("generated_report",
             context.get("step_2_output", "")))
    if isinstance(report, dict):
        report = str(report)

    critic = context.get("step_3_output", {})
    if isinstance(critic, str):
        try:
            critic = json.loads(critic)
        except (json.JSONDecodeError, TypeError):
            critic = {"feedback": critic}

    feedback = critic.get("feedback", "No specific feedback")
    det_issues = critic.get("deterministic_issues", [])

    det_section = ""
    if det_issues:
        det_section = "\nCRITICAL STRUCTURAL FIXES:\n" + "\n".join(
            f"  - {i}" for i in det_issues[:10])

    system = f"""{EXECUTION_ROLE}

You are improving a competitive intelligence report based on critic feedback.
{det_section}

RULES:
1. Fix ALL structural issues listed above first.
2. Use ONLY the input data — do NOT introduce external knowledge.
3. Preserve ALL numbers, percentages, currency values from the input.
4. Every SWOT point must reference input data. State assumptions if evidence is weak.
5. Every recommendation must link to a SWOT or positioning insight.
6. Maintain the required section structure.
7. Do NOT use banned fluff phrases.
8. Output ONLY the improved markdown report. No preamble."""

    user = f"""ORIGINAL INPUT DATA:
{original_data[:4000]}

CURRENT REPORT:
{report}

CRITIC FEEDBACK: {feedback}

COMPETITORS THAT MUST BE COVERED: {', '.join(competitors)}

Fix all issues. Output ONLY the improved report."""

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    content, error = call_resolved(messages, context, max_tokens=8000)
    if error:
        content, error = call_openai(messages, model="gpt-5.4-mini", max_tokens=8000)
    if error:
        return None, error

    return {"output": content}, None


def _select_best_output(context):
    """Latest surviving candidate."""
    for key in ("improved_report", "generated_report", "step_2_output"):
        v = context.get(key, "")
        if v and isinstance(v, str) and v.strip():
            return v
    return context.get("generated_report", "")


def step_5_write(inputs, context):
    """Full deterministic gate — hard-fail on structural violations."""
    best = _select_best_output(context)
    if isinstance(best, dict):
        best = str(best)
    if not best or not best.strip():
        return None, "No report to write"

    analysis = context.get("step_1_output", {})
    competitor_names = set(analysis.get("competitor_names", []))
    factual_tokens = analysis.get("factual_tokens", [])
    depth = analysis.get("report_depth", "standard")

    issues = validate_report_structure(best, competitor_names, factual_tokens, depth)

    # Only hard-fail on critical structural issues (missing sections, missing SWOT)
    critical = [i for i in issues if any(k in i.lower() for k in
                ["missing required section", "swot missing", "no bullet points",
                 "factual tokens"])]

    if critical:
        summary = "; ".join(critical[:5])
        return None, f"REPORT INTEGRITY FAILURE ({len(critical)} critical): {summary}"

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
