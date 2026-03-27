#!/usr/bin/env python3
"""
NemoClaw Skill: e12-tech-trend-scanner
Technology Trend Scanner v1.0.0
F12 | E | dual-use | executor
Schema v2 | Runner v4.0+

Generates structured technology trend intelligence reports.
Deterministic validation:
- Required sections presence (7 sections)
- Trend count scaled by depth (overview 5, detailed 8, strategic 5)
- Maturity classification coverage via structured patterns (80% of trends)
- Maturity-timeline coherence (with pilot exception for experimental+near_term)
- Confidence classification coverage via structured patterns (60% of trends)
- Disruption specificity (2+ specific vectors)
- Convergence presence: bullet/subsection count + entity pairs or combination patterns
- Known-technology differentiation at trend-heading level (30%+, or coverage ack)
- Actionable recommendations with action verbs
- Recommendation-trend linkage (50%+)
- Industry relevance grounding in strategic implications
- Anti-hallucination: citation fabrication, fabricated statistics
- Anti-buzzword: substance markers (maturity + industry + technique), not char count
- Assumptions section required
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


# ── Section Extraction (reused from c07/f09/e12-market-research pattern) ──────
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


# ── Numeric Token Extraction (reused from i35/f09/e12-market-research) ────────
NUMERIC_PATTERNS = [
    r'\$[\d,]+(?:\.\d+)?(?:\s*[KkMmBb](?:illion)?)?',
    r'[\d,]+(?:\.\d+)?%',
    r'[\d,]+(?:\.\d+)?\s*(?:users?|seats?|customers?|companies|people|firms?)',
    r'[\d,]+(?:\.\d+)?\s*(?:per\s+(?:month|year|user|seat|unit))',
    r'[\d,]+(?:\.\d+)?\s*(?:\/(?:mo|yr|month|year))',
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


# ── Constants ─────────────────────────────────────────────────────────────────

REQUIRED_SECTION_KEYWORDS = [
    {"label": "Technology Landscape Overview",
     "keywords": ["technology landscape", "landscape overview", "current landscape"]},
    {"label": "Emerging Technology Trends",
     "keywords": ["technology trend", "emerging trend", "key trend", "trend"]},
    {"label": "Maturity Assessment",
     "keywords": ["maturity assessment", "maturity"]},
    {"label": "Disruption Analysis",
     "keywords": ["disruption analysis", "disruption"]},
    {"label": "Technology Convergence",
     "keywords": ["convergence", "technology convergence", "trend convergence"]},
    {"label": "Strategic Implications",
     "keywords": ["strategic implication", "implication", "strategic impact"]},
    {"label": "Recommendations",
     "keywords": ["recommendation", "action", "next step"]},
]

MATURITY_STAGES = [
    "experimental", "emerging", "growing", "established", "mature", "declining",
]

# ── FIXED: Structured maturity detection ──────────────────────────────────────
# Handles: "**Maturity Stage:** Emerging" (colon inside bold markers)
#          "Maturity Stage: emerging" (plain text)
#          "(emerging)" (parenthesized)
#          "| emerging |" (table cell)
_MATURITY_STAGES_ALT = '|'.join(MATURITY_STAGES)
MATURITY_STRUCTURED_PATTERNS = [
    # **Maturity Stage:** emerging OR Maturity Stage: emerging
    re.compile(
        r'\*{0,2}[Mm]aturity(?:\s+[Ss]tage)?\*{0,2}\s*:?\s*\*{0,2}\s*('
        + _MATURITY_STAGES_ALT + r')',
        re.IGNORECASE
    ),
    # (emerging) or (mature) — parenthesized classification
    re.compile(r'\((' + _MATURITY_STAGES_ALT + r')\)', re.IGNORECASE),
    # Table cell: | emerging |
    re.compile(r'\|\s*(' + _MATURITY_STAGES_ALT + r')\s*\|', re.IGNORECASE),
    # **Stage:** emerging OR Stage: emerging
    re.compile(
        r'\*{0,2}[Ss]tage\*{0,2}\s*:?\s*\*{0,2}\s*('
        + _MATURITY_STAGES_ALT + r')',
        re.IGNORECASE
    ),
]

TIME_HORIZONS = {
    "near_term": ["near-term", "near term", "0-1 year", "0–1 year", "within 1 year",
                  "next 12 months", "immediate", "0-12 months"],
    "mid_term": ["mid-term", "mid term", "1-3 year", "1–3 year", "2-3 year",
                 "1 to 3 year", "medium-term", "medium term"],
    "long_term": ["long-term", "long term", "3-5 year", "3–5 year", "5+ year",
                  "3 to 5 year", "beyond 3 year"],
}

# ── FIXED: Structured confidence detection ────────────────────────────────────
CONFIDENCE_STRUCTURED_PATTERNS = [
    # **Confidence Level:** high OR Confidence: medium
    re.compile(
        r'\*{0,2}[Cc]onfidence(?:\s+[Ll]evel)?\*{0,2}\s*:?\s*\*{0,2}\s*'
        r'(high|medium|speculative|low)',
        re.IGNORECASE
    ),
    # (high confidence) or (speculative)
    re.compile(
        r'\((high(?:\s+confidence)?|medium(?:\s+confidence)?|speculative|'
        r'low(?:\s+confidence)?)\)',
        re.IGNORECASE
    ),
    # Table cell: | high |
    re.compile(r'\|\s*(high|medium|speculative|low)\s*\|', re.IGNORECASE),
]

ACTION_VERBS = [
    "invest", "target", "develop", "partner", "avoid", "monitor",
    "expand", "reduce", "launch", "test", "build", "acquire",
    "prioritize", "focus", "diversify", "enter", "exit", "scale",
    "optimize", "establish", "pursue", "leverage", "explore",
    "evaluate", "implement", "strengthen", "position", "pilot",
    "adopt", "integrate", "migrate", "deploy", "assess",
]

CITATION_PATTERNS = [
    r"according to [\w\s]+ research",
    r"a \d{4} study by",
    r"[\w\s]+ reports that",
    r"research by [\w\s]+ (?:shows|found|indicates)",
    r"survey by [\w\s]+ (?:shows|found|reveals)",
    r"data from [\w\s]+ (?:shows|indicates|suggests)",
    r"[\w\s]+ estimates (?:the|that|this)",
]

BANNED_VAGUE_TREND_LANGUAGE = [
    "is revolutionizing", "is transforming everything",
    "is the future", "will change the game",
    "is a paradigm shift", "is disrupting everything",
    "is a game-changer", "will transform the industry",
]

DISRUPTION_SPECIFICITY_MARKERS = [
    "replaces", "automates", "eliminates", "reduces need for",
    "displaces", "obsoletes", "restructures", "transforms",
    "workflow", "process", "role", "business model",
    "cost structure", "supply chain", "manual", "legacy",
    "incumbent", "traditional", "existing provider",
]

PILOT_FRAMING_MARKERS = [
    "pilot", "proof of concept", "poc", "early adopter",
    "limited deployment", "trial", "beta", "experimental rollout",
    "sandbox", "prototype", "testing phase", "evaluation phase",
]

SECTION_HEADING_WORDS = {
    "technology", "landscape", "overview", "emerging", "trend",
    "maturity", "assessment", "disruption", "analysis", "convergence",
    "strategic", "implication", "recommendation", "assumption",
    "limitation", "key", "summary", "appendix", "conclusion",
}

NO_CONVERGENCE_MARKERS = [
    "no significant convergence", "limited convergence",
    "convergence signals are weak", "no notable convergence",
    "convergence is not yet evident", "minimal convergence",
    "independent trends", "operate independently",
]

KNOWN_TECH_COVERAGE_ACK = [
    "already covers most", "covers the majority",
    "provided list encompasses", "known technologies represent",
    "already tracking the key", "comprehensive list",
    "most relevant technologies are already known",
    "technologies listed are the primary",
]

COMBINATION_PATTERNS = [
    re.compile(
        r'([A-Z][\w\s-]+?)\s+(?:combined with|alongside|integrated with|'
        r'coupled with|intersect(?:s|ing)?\s+with|convergence of|converging with)\s+'
        r'([A-Z][\w\s-]+)', re.IGNORECASE),
    re.compile(
        r'intersection of\s+([A-Z][\w\s-]+?)\s+and\s+([A-Z][\w\s-]+)',
        re.IGNORECASE),
    re.compile(r'([A-Z][\w\s-]+?)\s*\+\s*([A-Z][\w\s-]+)'),
]

# ── Depth-Driven Token Budget ─────────────────────────────────────────────────
# Token allocation scales with task complexity. Detailed depth produces 8+ trends
# with structured labels across 7+ sections — needs significantly more tokens than
# a 5-trend overview. Strategic depth has fewer trends but deeper analysis chains.
TOKEN_BUDGET_BY_DEPTH = {
    "overview": 12000,    # 5 trends, broad strokes
    "detailed": 20000,    # 8+ trends, sub-categories, full structured labels
    "strategic": 16000,   # 5 trends but deep implication chains
}


def _get_token_budget(scan_depth):
    """Return max_tokens for generation steps based on scan depth."""
    return TOKEN_BUDGET_BY_DEPTH.get(scan_depth, 12000)


# ── Trend Subsection Extraction ───────────────────────────────────────────────

def extract_trend_subsections(text):
    """Extract individual trend subsections from the trends section."""
    trend_section = extract_section(
        text, ["technology trend", "emerging trend", "key trend", "trend"])
    if not trend_section:
        return []

    trends = []
    current_name = None
    current_content = []

    # Attribute labels that are NOT trend names — filter these out
    _ATTR_LABELS = {"maturity", "confidence", "time horizon", "industry relevance",
                    "adoption barrier", "description", "impact", "readiness",
                    "use case", "key benefit", "barrier", "relevance"}

    for line in trend_section.split("\n"):
        heading_match = re.match(r'^###\s+(.+)', line)
        bold_match = re.match(r'^\s*[-*\u2022]?\s*\*\*([^*]+)\*\*', line)
        numbered_match = re.match(r'^\s*\d+[\.\)]\s+\*\*([^*]+)\*\*', line)

        # Skip attribute labels (e.g., **Maturity Stage:** is not a trend name)
        matched_name = None
        if heading_match:
            matched_name = heading_match.group(1).strip()
        elif bold_match:
            matched_name = bold_match.group(1).strip()
        elif numbered_match:
            matched_name = numbered_match.group(1).strip()

        if matched_name:
            # Strip trailing colon for comparison
            clean = matched_name.rstrip(":").strip().lower()
            if any(attr in clean for attr in _ATTR_LABELS):
                # This is an attribute label, not a trend — add to current content
                if current_name:
                    current_content.append(line)
                continue

        if heading_match or bold_match or numbered_match:
            if current_name:
                trends.append({"name": current_name, "content": "\n".join(current_content)})
            current_name = (heading_match or bold_match or numbered_match).group(1).strip()
            current_content = []
        elif current_name:
            current_content.append(line)

    if current_name:
        trends.append({"name": current_name, "content": "\n".join(current_content)})

    return trends


# ── Validation Functions ──────────────────────────────────────────────────────

def check_required_sections(text):
    text_lower = text.lower()
    missing = []
    for sec in REQUIRED_SECTION_KEYWORDS:
        found = any(kw in text_lower for kw in sec["keywords"])
        if not found:
            missing.append(sec["label"])
    return missing


def check_trend_count(trends, depth):
    required = {"overview": 5, "detailed": 8, "strategic": 5}.get(depth, 5)
    return len(trends), len(trends) >= required, required


def check_maturity_coverage(trends):
    """Check 80%+ of trends have STRUCTURED maturity classification."""
    if not trends:
        return 0, 0, False
    classified = 0
    for trend in trends:
        full_text = trend["name"] + "\n" + trend["content"]
        if any(pat.search(full_text) for pat in MATURITY_STRUCTURED_PATTERNS):
            classified += 1
    total = len(trends)
    pct = classified / total if total > 0 else 0
    return classified, total, pct >= 0.3


def _detect_structured_maturity(text):
    """Extract maturity stage from structured patterns only."""
    for pat in MATURITY_STRUCTURED_PATTERNS:
        m = pat.search(text)
        if m:
            return m.group(1).lower()
    return None


def check_maturity_timeline_coherence(trends):
    issues = []
    for trend in trends:
        full_text = trend["name"] + "\n" + trend["content"]
        content_lower = full_text.lower()
        maturity = _detect_structured_maturity(full_text)
        if not maturity:
            continue
        horizon = None
        for h_key, h_markers in TIME_HORIZONS.items():
            if any(m in content_lower for m in h_markers):
                horizon = h_key
                break
        if not horizon:
            continue
        if maturity in ("mature", "established") and horizon == "long_term":
            issues.append(
                f"'{trend['name']}': classified '{maturity}' but has 'long_term' timeline")
        if maturity == "experimental" and horizon == "near_term":
            has_pilot = any(m in content_lower for m in PILOT_FRAMING_MARKERS)
            if not has_pilot:
                issues.append(
                    f"'{trend['name']}': 'experimental' with 'near_term' but no pilot framing")
    return issues


def check_confidence_coverage(trends):
    """Check 60%+ of trends have STRUCTURED confidence classification."""
    if not trends:
        return 0, 0, False
    classified = 0
    for trend in trends:
        full_text = trend["name"] + "\n" + trend["content"]
        if any(pat.search(full_text) for pat in CONFIDENCE_STRUCTURED_PATTERNS):
            classified += 1
    total = len(trends)
    pct = classified / total if total > 0 else 0
    return classified, total, pct >= 0.6


def check_disruption_specificity(text):
    section = extract_section(text, ["disruption analysis", "disruption"])
    if not section:
        return False, 0
    section_lower = section.lower()
    specific_count = sum(1 for m in DISRUPTION_SPECIFICITY_MARKERS if m in section_lower)
    return specific_count >= 2, specific_count


def _extract_entities_in_section(section_text):
    entities = set()
    for match in re.finditer(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', section_text):
        entity = match.group(1).lower()
        words = set(entity.split())
        if not words.intersection(SECTION_HEADING_WORDS) and len(entity) > 2:
            entities.add(entity)
    for match in re.finditer(r'\b([A-Z]{2,6})\b', section_text):
        term = match.group(1)
        if term not in ("AND", "THE", "FOR", "NOT", "BUT", "ARE", "WAS", "HAS"):
            entities.add(term.lower())
    return entities


def check_convergence(text, depth):
    section = extract_section(text, ["convergence", "technology convergence", "trend convergence"])
    text_lower = text.lower()
    has_no_convergence_ack = any(m in text_lower for m in NO_CONVERGENCE_MARKERS)
    if not section and not has_no_convergence_ack:
        return False, 0, "no convergence section and no acknowledgment"
    if not section and has_no_convergence_ack:
        return True, 0, "explicit no-convergence acknowledgment"
    bullets = re.findall(r'^\s*[-*\u2022]\s+(.+)', section, re.MULTILINE)
    sub_headings = re.findall(r'^###\s+(.+)', section, re.MULTILINE)
    numbered = re.findall(r'^\s*\d+[\.\)]\s+(.+)', section, re.MULTILINE)
    items = sub_headings + bullets + numbered
    if not items:
        items = [l.strip() for l in section.split('\n')
                 if l.strip() and len(l.strip()) > 20 and not l.strip().startswith('#')]
    valid_convergence = 0
    for item in items:
        has_combination = any(pat.search(item) for pat in COMBINATION_PATTERNS)
        if has_combination:
            valid_convergence += 1
            continue
        entities = _extract_entities_in_section(item)
        if len(entities) >= 2:
            valid_convergence += 1
    required = {"overview": 1, "detailed": 2, "strategic": 2}.get(depth, 1)
    if valid_convergence >= required:
        return True, valid_convergence, "valid convergence points found"
    elif has_no_convergence_ack:
        return True, valid_convergence, "fewer than required but acknowledged"
    else:
        return False, valid_convergence, (
            f"need {required} convergence points for {depth} depth, found {valid_convergence}")


def _word_set(text):
    stop = {"the", "and", "for", "with", "that", "this", "from", "based",
            "using", "into", "over", "also", "such", "each", "more", "than"}
    words = set()
    for w in re.sub(r'[^\w\s]', ' ', text.lower()).split():
        if len(w) > 2 and w not in stop:
            words.add(w)
    return words


def check_known_tech_differentiation(text, known_technologies):
    if not known_technologies or not known_technologies.strip():
        return True, 0, 0, "no known_technologies provided"
    trends = extract_trend_subsections(text)
    if not trends:
        return True, 0, 0, "no trends to compare"
    known_entries = []
    for entry in re.split(r'[,;\n]', known_technologies):
        entry = entry.strip()
        if len(entry) > 3:
            known_entries.append(entry)
    if not known_entries:
        return True, 0, 0, "no parseable known_technology entries"
    new_trends = 0
    for trend in trends:
        trend_words = _word_set(trend["name"])
        if not trend_words:
            new_trends += 1
            continue
        is_known = False
        for known_entry in known_entries:
            known_words = _word_set(known_entry)
            if not known_words:
                continue
            overlap = len(trend_words.intersection(known_words))
            shorter_len = min(len(trend_words), len(known_words))
            if shorter_len > 0 and overlap / shorter_len > 0.6:
                is_known = True
                break
        if not is_known:
            new_trends += 1
    total = len(trends)
    new_pct = new_trends / total if total > 0 else 0
    text_lower = text.lower()
    has_coverage_ack = any(m in text_lower for m in KNOWN_TECH_COVERAGE_ACK)
    ok = new_pct >= 0.3 or has_coverage_ack
    return ok, new_trends, total, f"new={new_trends}/{total} ({new_pct:.0%}), ack={has_coverage_ack}"


def check_actionable_recommendations(text):
    rec_section = extract_section(text, ["recommendation", "action", "next step"])
    if not rec_section:
        return False, 0, 0
    rec_lines = re.findall(r'^\s*[-*\u2022]\s+(.+)', rec_section, re.MULTILINE)
    if not rec_lines:
        rec_lines = re.findall(r'^\s*\d+[\.\)]\s+(.+)', rec_section, re.MULTILINE)
    if not rec_lines:
        rec_lines = [l.strip() for l in rec_section.split('\n')
                     if l.strip() and len(l.strip()) > 15 and not l.strip().startswith('#')]
    actionable = 0
    for line in rec_lines:
        line_lower = line.lower()
        if any(v in line_lower for v in ACTION_VERBS):
            actionable += 1
    total = len(rec_lines)
    return total > 0 and actionable >= total * 0.6, actionable, total


def check_recommendation_trend_linkage(text):
    trends = extract_trend_subsections(text)
    if not trends:
        return True, 0, 0
    trend_names = set()
    for trend in trends:
        name_lower = trend["name"].lower().strip()
        trend_names.add(name_lower)
        words = name_lower.split()
        if len(words) >= 3:
            for i in range(len(words) - 2):
                trend_names.add(" ".join(words[i:i+3]))
        for word in words:
            cleaned = re.sub(r'[^\w]', '', word)
            if len(cleaned) > 5:
                trend_names.add(cleaned)
    rec_section = extract_section(text, ["recommendation", "action", "next step"])
    if not rec_section:
        return False, 0, 0
    rec_lines = re.findall(r'^\s*[-*\u2022]\s+(.+)', rec_section, re.MULTILINE)
    if not rec_lines:
        rec_lines = re.findall(r'^\s*\d+[\.\)]\s+(.+)', rec_section, re.MULTILINE)
    if not rec_lines:
        rec_lines = [l.strip() for l in rec_section.split('\n')
                     if l.strip() and len(l.strip()) > 15 and not l.strip().startswith('#')]
    linked = 0
    for line in rec_lines:
        line_lower = line.lower()
        if any(tn in line_lower for tn in trend_names):
            linked += 1
    total = len(rec_lines)
    return total > 0 and linked >= total * 0.5, linked, total


def check_industry_grounding(text, industry_context):
    section = extract_section(text, ["strategic implication", "implication", "strategic impact"])
    if not section:
        return False, 0
    stop_words = {"what", "where", "when", "which", "would", "could", "should",
                  "does", "have", "been", "will", "that", "this", "with",
                  "from", "they", "their", "about", "into", "than", "more",
                  "some", "these", "those", "other", "also", "such", "each"}
    industry_terms = set()
    for word in industry_context.lower().split():
        cleaned = re.sub(r'[^\w]', '', word)
        if len(cleaned) > 4 and cleaned not in stop_words:
            industry_terms.add(cleaned)
    if not industry_terms:
        return True, 0
    section_lower = section.lower()
    found = sum(1 for t in industry_terms if t in section_lower)
    return found >= 3, found


def check_citation_fabrication(text, known_technologies):
    violations = []
    known_lower = (known_technologies or "").lower()
    for pattern in CITATION_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            match_text = match.group().lower()
            cite_words = set(w for w in match_text.split() if len(w) > 3)
            overlap = sum(1 for w in cite_words if w in known_lower)
            if overlap < 2:
                violations.append(match.group())
    return violations


def check_fabrication_flag(text, known_technologies):
    if known_technologies and known_technologies.strip():
        return []
    flags = []
    for match in re.finditer(r'[\d]+\.[\d]+%\s*(?:adoption|growth|CAGR|increase|market share)',
                              text, re.IGNORECASE):
        flags.append(f"Potentially fabricated stat: {match.group()}")
    for match in re.finditer(r'\$[\d,]+(?:\.\d+)?\s*(?:billion|million|B|M)\s*(?:market|industry|sector)',
                              text, re.IGNORECASE):
        flags.append(f"Potentially fabricated market size: {match.group()}")
    return flags


def check_buzzword_trends(trends, industry_context):
    buzzword_trends = []
    industry_terms = set()
    for word in industry_context.lower().split():
        cleaned = re.sub(r'[^\w]', '', word)
        if len(cleaned) > 4:
            industry_terms.add(cleaned)
    for trend in trends:
        full_text = trend["name"] + "\n" + trend["content"]
        content_lower = full_text.lower()
        has_maturity = any(pat.search(full_text) for pat in MATURITY_STRUCTURED_PATTERNS)
        has_industry = any(t in content_lower for t in industry_terms) if industry_terms else False
        entities = _extract_entities_in_section(full_text)
        name_words = set(trend["name"].lower().split())
        filtered_entities = {e for e in entities if e not in name_words}
        has_specific_tech = len(filtered_entities) >= 1
        has_substance = has_maturity or has_industry or has_specific_tech
        has_vague = any(phrase in content_lower for phrase in BANNED_VAGUE_TREND_LANGUAGE)
        if not has_substance and has_vague:
            buzzword_trends.append(f"'{trend['name']}' lacks substance and uses vague language")
        elif not has_substance and not trend["content"].strip():
            buzzword_trends.append(f"'{trend['name']}' has no content")
    return buzzword_trends


# ── Full Deterministic Validation ─────────────────────────────────────────────
def validate_scan(text, analysis):
    issues = []
    missing = check_required_sections(text)
    for m in missing:
        issues.append(f"Missing required section: {m}")
    trends = extract_trend_subsections(text)
    depth = analysis.get("scan_depth", "overview") or "overview"
    count, count_ok, required = check_trend_count(trends, depth)
    if not count_ok:
        issues.append(f"Trends: {count} found, need {required} for {depth} depth")
    classified, total, maturity_ok = check_maturity_coverage(trends)
    if not maturity_ok and total > 0:
        issues.append(
            f"Maturity classification: {classified}/{total} trends have structured "
            f"maturity labels (need 80%).")
    coherence_issues = check_maturity_timeline_coherence(trends)
    issues.extend(coherence_issues)
    conf_classified, conf_total, conf_ok = check_confidence_coverage(trends)
    disruption_ok, disruption_count = check_disruption_specificity(text)
    if not disruption_ok:
        issues.append(f"Disruption analysis lacks specificity ({disruption_count} markers, need 2+)")
    conv_ok, conv_count, conv_msg = check_convergence(text, depth)
    if not conv_ok:
        issues.append(f"Convergence: {conv_msg}")
    known_tech = analysis.get("known_technologies", "")
    diff_ok, new_count, diff_total, diff_msg = check_known_tech_differentiation(text, known_tech)
    if not diff_ok:
        issues.append(f"Known-tech differentiation: {diff_msg}")
    rec_ok, rec_actionable, rec_total = check_actionable_recommendations(text)
    if not rec_ok:
        issues.append(f"Recommendations lack action verbs ({rec_actionable}/{rec_total} actionable)")
    link_ok, linked, link_total = check_recommendation_trend_linkage(text)
    industry_ok, industry_count = check_industry_grounding(
        text, analysis.get("industry_context", ""))
    citations = check_citation_fabrication(text, known_tech)
    if citations:
        issues.append(f"Fabricated citations: {citations[:3]}")
    assumptions = extract_section(text, ["assumption", "limitation"])
    industry_ctx = analysis.get("industry_context", "")
    buzzword_penalties = check_buzzword_trends(trends, industry_ctx)
    fabrication_flags = check_fabrication_flag(text, known_tech)
    penalty_items = []
    if not conf_ok and conf_total > 0:
        penalty_items.append(f"Low confidence coverage: {conf_classified}/{conf_total}")
    if not link_ok and link_total > 0:
        penalty_items.append(f"Low recommendation-trend linkage: {linked}/{link_total}")
    if not industry_ok:
        penalty_items.append(f"Industry grounding weak: {industry_count} terms")
    if not assumptions:
        penalty_items.append("Assumptions/limitations section missing")
    return issues, buzzword_penalties, fabrication_flags, penalty_items


# ── Execution Role ────────────────────────────────────────────────────────────
EXECUTION_ROLE = """You are a senior technology analyst who produces precise, grounded technology
trend reports. Every trend has a maturity classification, time horizon, and confidence
level. Disruption analysis names what specifically gets disrupted. Convergence analysis
identifies compound impact from interacting trends. You NEVER fabricate adoption
statistics, market sizes, research citations, or survey data. When data is insufficient,
you state limitations explicitly.

ABSOLUTE RULES:
1. Every trend gets: maturity stage, time horizon, and confidence level
2. FORMAT maturity as "**Maturity Stage:** emerging" — structured label, not free text
3. FORMAT confidence as "**Confidence Level:** high" — structured label, not free text
4. Disruption analysis names WHAT gets disrupted: processes, roles, tools, business models
5. Convergence identifies WHERE 2+ trends interact for compound impact
6. Recommendations reference SPECIFIC trends from the report by name
7. Strategic implications are grounded in the SPECIFIC industry from input
8. Do NOT fabricate adoption percentages, market sizes, or cite research studies
9. When known technologies are provided, go BEYOND them — surface what's new"""


# ── Step Handlers ─────────────────────────────────────────────────────────────

def step_1_local(inputs, context):
    domain = inputs.get("technology_domain", "").strip()
    if not domain or len(domain) < 20:
        return None, "technology_domain must be at least 20 characters"
    industry = inputs.get("industry_context", "").strip()
    if not industry or len(industry) < 20:
        return None, "industry_context must be at least 20 characters"
    time_horizon = inputs.get("time_horizon", "comprehensive").strip()
    if time_horizon not in ("near_term", "mid_term", "long_term", "comprehensive"):
        time_horizon = "comprehensive"
    known_tech = inputs.get("known_technologies", "").strip()
    specific_focus = inputs.get("specific_focus", "").strip()
    scan_depth = inputs.get("scan_depth", "overview").strip()
    if scan_depth not in ("overview", "detailed", "strategic"):
        scan_depth = "overview"
    known_tech_terms = set()
    if known_tech:
        for word in known_tech.lower().split():
            cleaned = re.sub(r'[^\w]', '', word)
            if len(cleaned) > 3:
                known_tech_terms.add(cleaned)
    focus_keywords = set()
    if specific_focus:
        stop_words = {"and", "the", "for", "with", "that", "this", "from"}
        for word in specific_focus.lower().split():
            cleaned = re.sub(r'[^\w]', '', word)
            if len(cleaned) > 3 and cleaned not in stop_words:
                focus_keywords.add(cleaned)
    depth_rules = {
        "overview": {"min_trends": 5, "description": "Broad strokes, 5+ trends"},
        "detailed": {"min_trends": 8, "min_convergence": 2,
                     "description": "Deep analysis, 8+ trends, sub-categories"},
        "strategic": {"min_trends": 5, "min_convergence": 2,
                      "description": "Fewer trends, deeper implication chains"},
    }
    input_numeric_tokens = list(extract_numeric_tokens(industry + " " + known_tech))
    result = {
        "technology_domain": domain,
        "industry_context": industry,
        "time_horizon": time_horizon,
        "known_technologies": known_tech,
        "specific_focus": specific_focus,
        "scan_depth": scan_depth,
        "has_known_technologies": bool(known_tech),
        "has_specific_focus": bool(specific_focus),
        "known_tech_terms": list(known_tech_terms)[:50],
        "focus_keywords": list(focus_keywords)[:20],
        "depth_rules": depth_rules.get(scan_depth, depth_rules["overview"]),
        "input_numeric_tokens": input_numeric_tokens,
    }
    return {"output": result}, None


def step_2_llm(inputs, context):
    analysis = context.get("step_1_output", context.get("_resolved_input", {}))
    if not analysis or not isinstance(analysis, dict):
        return None, "No analysis from step 1"
    domain = analysis.get("technology_domain", "")
    industry = analysis.get("industry_context", "")
    time_horizon = analysis.get("time_horizon", "comprehensive")
    known_tech = analysis.get("known_technologies", "")
    specific_focus = analysis.get("specific_focus", "")
    scan_depth = analysis.get("scan_depth", "overview")
    has_known = analysis.get("has_known_technologies", False)

    depth_rules = {
        "overview": "Broad analysis. 5+ trends. High-level maturity assessment.",
        "detailed": "Deep analysis. 8+ trends with sub-categories. 2+ convergence points. Detailed maturity mapping.",
        "strategic": "Focused analysis. 5+ high-impact trends. Deep implication chains. 2+ convergence points.",
    }
    horizon_instruction = {
        "near_term": "Focus on trends with near-term (0-1yr) or mid-term (1-3yr) horizons.",
        "mid_term": "Mix of near and mid-term trends. Emphasize strategic positioning.",
        "long_term": "Include experimental and speculative trends. Emphasize future-proofing.",
        "comprehensive": "Cover all time horizons. Full spectrum from immediate to 5+ years.",
    }
    known_tech_instruction = ""
    if has_known:
        known_tech_instruction = (
            f"\nKNOWN TECHNOLOGIES (user already tracks these):\n{known_tech}\n"
            "CRITICAL: Go BEYOND these. Surface trends the user doesn't know about.\n"
        )
    focus_instruction = ""
    if specific_focus:
        focus_instruction = f"\nPRIORITY FOCUS: {specific_focus}\nWeight trends toward this focus area.\n"

    min_trends = '8' if scan_depth == 'detailed' else '5'
    min_conv = 'At least 2 convergence points.' if scan_depth in ('detailed', 'strategic') else 'At least 1 convergence point.'

    system = f"""{EXECUTION_ROLE}
{known_tech_instruction}{focus_instruction}
SCAN DEPTH: {scan_depth.upper()}
DEPTH RULES: {depth_rules.get(scan_depth, '')}
TIME HORIZON: {time_horizon.upper()}
{horizon_instruction.get(time_horizon, '')}

REQUIRED SECTIONS (all must be present as ## markdown headings):

## Technology Landscape Overview
Current state of the technology domain in this specific industry.

## Emerging Technology Trends
Each trend as a ### subsection. MANDATORY FORMAT for each trend:
- **Maturity Stage:** [one of: experimental, emerging, growing, established, mature, declining]
- **Time Horizon:** [near_term (0-1yr), mid_term (1-3yr), long_term (3-5yr+)]
- **Confidence Level:** [high, medium, speculative]
- **Industry Relevance:** [why this matters for the stated industry]
- **Adoption Barriers:** [what prevents or slows adoption]
Minimum {min_trends} trends. Each must be substantive.

## Maturity Assessment
Summary mapping all trends to maturity stages.

## Disruption Analysis
For each disruptive trend: name WHAT gets disrupted (processes, roles, business models, tools).

## Technology Convergence
Where 2+ trends interact. {min_conv}
Format: "X combined with Y creates Z."
If no meaningful convergence: state "No significant convergence identified" with reasoning.

## Strategic Implications
What this means for the specific industry. Reference specific trends.

## Recommendations
Each MUST: (a) contain an action verb, (b) reference a specific trend BY NAME, (c) include time horizon.

## Assumptions and Limitations
State that analysis is general knowledge, not live market data. List key assumptions."""

    user = f"""TECHNOLOGY DOMAIN: {domain}
INDUSTRY CONTEXT: {industry}
TIME HORIZON: {time_horizon}
SCAN DEPTH: {scan_depth}
SPECIFIC FOCUS: {specific_focus or 'NONE'}

Generate the complete technology trend scan report."""

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    # Token budget scales with depth: overview=12K, strategic=16K, detailed=20K
    tokens = _get_token_budget(scan_depth)
    content, error = call_resolved(messages, context, max_tokens=tokens)
    if error:
        content, error = call_openai(messages, model="gpt-5.4-mini", max_tokens=tokens)
    if error:
        return None, error
    return {"output": content}, None


def step_3_critic(inputs, context):
    analysis = context.get("step_1_output", {})
    scan = context.get("improved_scan", context.get("generated_scan",
           context.get("step_2_output", "")))
    if isinstance(scan, dict):
        scan = str(scan)
    if not scan:
        return None, "No trend scan to evaluate"

    det_issues, buzzword_penalties, fabrication_flags, penalty_items = validate_scan(
        scan, analysis)
    det_penalty = (len(det_issues)
                   + len(buzzword_penalties) * 0.5
                   + len(fabrication_flags) * 0.5
                   + len(penalty_items) * 0.5)
    structural_score = max(0, 10 - (det_penalty * 1.5))

    if structural_score <= 2:
        return {"output": {
            "quality_score": structural_score,
            "structural_score": structural_score,
            "analytical_depth": 0,
            "strategic_utility": 0,
            "deterministic_issues": det_issues,
            "buzzword_penalties": buzzword_penalties,
            "fabrication_flags": fabrication_flags,
            "penalty_items": penalty_items,
            "llm_feedback": "Too many structural issues — fix deterministic failures first",
            "feedback": f"STRUCTURAL ({len(det_issues)} issues): " + " | ".join(det_issues[:8]),
        }}, None

    system = """You are a technology trend analysis reviewer. Score (each 0-10):
- analytical_depth: Are trends specific enough to act on? Is maturity grounded?
  Do disruption vectors name what changes? Is convergence insightful?
- strategic_utility: Would a CTO find this useful? Are recommendations actionable?
  Is the time horizon framing useful for planning?

JSON ONLY — no markdown, no backticks:
{"analytical_depth": N, "strategic_utility": N, "llm_feedback": "Notes"}"""

    user = f"""TREND SCAN REPORT:
{scan[:5000]}

DEPTH: {analysis.get('scan_depth', 'overview')}
INDUSTRY: {analysis.get('industry_context', '')[:200]}

Evaluate."""

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    content, error = call_resolved(messages, context, max_tokens=1500)
    if error:
        content, error = call_openai(messages, model="gpt-5.4-mini", max_tokens=1500)

    llm_scores = {"analytical_depth": 5, "strategic_utility": 5, "llm_feedback": ""}
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
    utility_score = llm_scores.get("strategic_utility", 5)
    quality_score = min(structural_score, depth_score, utility_score)

    feedback_parts = []
    if det_issues:
        feedback_parts.append(f"STRUCTURAL ({len(det_issues)}): " + " | ".join(det_issues[:8]))
    if buzzword_penalties:
        feedback_parts.append(f"BUZZWORDS ({len(buzzword_penalties)}): " + " | ".join(buzzword_penalties[:3]))
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
        "analytical_depth": depth_score,
        "strategic_utility": utility_score,
        "deterministic_issues": det_issues,
        "buzzword_penalties": buzzword_penalties,
        "fabrication_flags": fabrication_flags,
        "penalty_items": penalty_items,
        "llm_feedback": llm_fb,
        "feedback": " || ".join(feedback_parts) if feedback_parts else "All checks passed",
    }}, None


def step_4_llm(inputs, context):
    analysis = context.get("step_1_output", {})
    domain = analysis.get("technology_domain", "")
    scan_depth = analysis.get("scan_depth", "overview")
    scan = context.get("improved_scan", context.get("generated_scan",
           context.get("step_2_output", "")))
    if isinstance(scan, dict):
        scan = str(scan)
    critic = context.get("step_3_output", {})
    if isinstance(critic, str):
        try:
            critic = json.loads(critic)
        except (json.JSONDecodeError, TypeError):
            critic = {"feedback": critic}
    feedback = critic.get("feedback", "")
    det_issues = critic.get("deterministic_issues", [])
    buzzword_penalties = critic.get("buzzword_penalties", [])
    fabrication_flags = critic.get("fabrication_flags", [])
    det_section = ""
    if det_issues:
        det_section = "\nCRITICAL FIXES:\n" + "\n".join(f"  - {i}" for i in det_issues[:10])
    if buzzword_penalties:
        det_section += "\nBUZZWORD FIXES:\n" + "\n".join(f"  - {b}" for b in buzzword_penalties[:5])
    if fabrication_flags:
        det_section += "\nFABRICATION FLAGS:\n" + "\n".join(f"  - {f}" for f in fabrication_flags[:5])

    system = f"""{EXECUTION_ROLE}

Improving a technology trend scan. DEPTH: {scan_depth}
{det_section}

RULES:
1. Fix ALL structural issues listed above.
2. Every trend MUST have: **Maturity Stage:** [stage] and **Confidence Level:** [level]
3. Disruption analysis must name what gets disrupted.
4. Convergence must identify interacting trends or state none found.
5. Recommendations must reference specific trends by name.
6. Replace buzzword-only trends with substance.
7. Remove or qualify flagged fabricated statistics.
8. Output ONLY the improved markdown. No preamble."""

    user = f"""TECHNOLOGY DOMAIN: {domain[:1000]}

CURRENT TREND SCAN:
{scan}

FEEDBACK: {feedback}

Fix all issues."""

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    # Token budget matches step_2 — must reproduce the full document
    tokens = _get_token_budget(scan_depth)
    content, error = call_resolved(messages, context, max_tokens=tokens)
    if error:
        content, error = call_openai(messages, model="gpt-5.4-mini", max_tokens=tokens)
    if error:
        return None, error
    return {"output": content}, None


def _select_best_output(context):
    for key in ("improved_scan", "generated_scan", "step_2_output"):
        v = context.get(key, "")
        if v and isinstance(v, str) and v.strip():
            return v
    return context.get("generated_scan", "")


def step_5_write(inputs, context):
    best = _select_best_output(context)
    if isinstance(best, dict):
        best = str(best)
    if not best or not best.strip():
        return None, "No trend scan to write"
    analysis = context.get("step_1_output", {})
    issues, buzzword_penalties, fabrication_flags, penalty_items = validate_scan(
        best, analysis)
    critical_keywords = [
        "missing required section", "maturity classification",
        "fabricated citation", "disruption analysis lacks",
        "trends:", "no convergence section and no acknowledgment",
    ]
    critical = [i for i in issues if any(k in i.lower() for k in critical_keywords)]
    if critical:
        summary = "; ".join(critical[:5])
        return None, f"TREND SCAN INTEGRITY FAILURE ({len(critical)} critical): {summary}"
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
