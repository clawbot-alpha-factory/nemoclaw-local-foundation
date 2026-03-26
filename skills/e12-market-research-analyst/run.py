#!/usr/bin/env python3
"""
NemoClaw Skill: e12-market-research-analyst
Market Research Analyst v1.0.0
F12 | E | dual-use | executor
Schema v2 | Runner v4.0+

Generates structured market research reports.
Deterministic validation:
- Required sections presence (7 sections)
- Market sizing: numeric indicator, qualitative scoping, or explicit data gap
- Question coverage: 60% of specific_questions topic words in output
- Data grounding: known_data references integrated in analysis context
- Competitive entity detection (section-scoped, not full document)
- Trend count scaled by depth (overview 3, detailed 5, competitive_focus 3)
- Actionable recommendations with verbs
- Anti-hallucination: no fabricated citations
- Fabrication flagging: precise stats when known_data empty
- Segment naming quality: no generic labels
- Insight linkage: opportunities/recommendations reference trends/segments/competition
- Risk grounding: risks tied to market forces
- Competitive archetype fallback when no competitors provided
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


# ── Section Extraction (reused from c07/f09 pattern) ─────────────────────────
def extract_section(text, heading_keywords):
    """Extract content under a heading matching any of the keywords."""
    for kw in heading_keywords:
        pattern = re.compile(
            rf'(?:^|\n)##?\s*[^\n]*{re.escape(kw)}[^\n]*\n(.*?)(?=\n##?\s[^#]|\Z)',
            re.IGNORECASE | re.DOTALL
        )
        m = pattern.search(text)
        if m:
            return m.group(1).strip()
    return ""


# ── Numeric Token Extraction (reused from i35/f09-pricing pattern) ────────────
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
    {"label": "Market Overview", "keywords": ["market overview", "overview"]},
    {"label": "Market Segmentation", "keywords": ["segmentation", "segment"]},
    {"label": "Key Trends", "keywords": ["trend", "key trend"]},
    {"label": "Competitive Landscape", "keywords": ["competitive", "competitor", "landscape"]},
    {"label": "Opportunities", "keywords": ["opportunit"]},
    {"label": "Risk Factors", "keywords": ["risk", "threat", "challenge"]},
    {"label": "Recommendations", "keywords": ["recommendation", "action", "next step"]},
]

QUALITATIVE_SCOPING = [
    "early-stage", "early stage", "mature market", "emerging",
    "niche", "fragmented", "consolidated", "nascent",
    "growing market", "declining market", "saturated",
    "high-growth", "established market", "developing",
]

ACTION_VERBS = [
    "invest", "target", "develop", "partner", "avoid", "monitor",
    "expand", "reduce", "launch", "test", "build", "acquire",
    "prioritize", "focus", "diversify", "enter", "exit", "scale",
    "optimize", "establish", "pursue", "leverage", "explore",
    "evaluate", "implement", "strengthen", "position",
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

BANNED_VAGUE_ANALYSIS = [
    "the market is growing",
    "there is significant opportunity",
    "competition is fierce",
    "the industry is evolving",
    "there is strong demand",
    "the market is competitive",
    "there are many players",
]

GENERIC_SEGMENT_NAMES = [
    "segment a", "segment b", "segment c", "segment d",
    "group 1", "group 2", "group 3",
    "category a", "category b",
    "type 1", "type 2",
]

SECTION_HEADING_WORDS = {
    "market", "overview", "segmentation", "trends", "competitive",
    "landscape", "opportunities", "risk", "factors", "recommendations",
    "key", "analysis", "appendix", "summary", "conclusion",
    "assumptions", "methodology",
}

INSIGHT_LINK_KEYWORDS = [
    "trend", "segment", "competitor", "competitive", "growth",
    "demand", "shift", "gap", "emerging", "declining",
]


# ── Validation Functions ──────────────────────────────────────────────────────

def check_required_sections(text):
    text_lower = text.lower()
    missing = []
    for sec in REQUIRED_SECTION_KEYWORDS:
        found = any(kw in text_lower for kw in sec["keywords"])
        if not found:
            missing.append(sec["label"])
    return missing


def check_market_sizing(text):
    """Check market overview has sizing: numeric, qualitative, or explicit gap."""
    overview = extract_section(text, ["market overview", "overview"])
    if not overview:
        return False, "no market overview section"

    # Path 1: Numeric sizing
    has_number = bool(re.search(
        r'(?:\$[\d,]+|\d+(?:\.\d+)?%|\d[\d,]*\s*(?:billion|million|trillion|B|M|T))',
        overview, re.IGNORECASE
    ))
    if has_number:
        return True, "numeric sizing found"

    # Path 2: Explicit data gap acknowledgment
    gap_markers = [
        "insufficient data", "data not available", "no reliable data",
        "market size data", "sizing data", "not enough data",
        "data would be needed", "requires additional data",
    ]
    has_gap_ack = any(m in overview.lower() for m in gap_markers)
    if has_gap_ack:
        return True, "explicit data gap acknowledged"

    # Path 3: Qualitative scoping language
    has_qualitative = any(q in overview.lower() for q in QUALITATIVE_SCOPING)
    if has_qualitative:
        return True, "qualitative scoping found"

    return False, "no sizing indicator, gap acknowledgment, or qualitative scoping"


def check_question_coverage(text, specific_questions):
    """Check that specific questions are addressed (60% topic word coverage)."""
    if not specific_questions:
        return True, 0, 0

    # Extract topic words from questions (>3 chars, not stop words)
    stop_words = {"what", "where", "when", "which", "would", "could", "should",
                  "does", "have", "been", "will", "that", "this", "with",
                  "from", "they", "their", "about", "into", "than", "more",
                  "some", "these", "those", "other"}
    topic_words = set()
    for word in specific_questions.lower().split():
        cleaned = re.sub(r'[^\w]', '', word)
        if len(cleaned) > 3 and cleaned not in stop_words:
            topic_words.add(cleaned)

    if not topic_words:
        return True, 0, 0

    text_lower = text.lower()
    covered = sum(1 for w in topic_words if w in text_lower)
    coverage_pct = covered / len(topic_words) if topic_words else 1.0

    return coverage_pct >= 0.6, covered, len(topic_words)


def check_data_grounding(text, known_data):
    """Check that known_data is integrated into analysis, not just repeated."""
    if not known_data:
        return True, "no known_data provided", 0

    input_tokens = extract_numeric_tokens(known_data)
    text_lower = text.lower()
    grounding_count = 0

    for token in input_tokens:
        raw_nums = re.findall(r'[\d]+(?:\.[\d]+)?', token)
        for num in raw_nums:
            if num in text_lower:
                grounding_count += 1

    # Also check for contextual integration (not just number repetition)
    integration_markers = [
        "based on", "provided data", "given that", "the data shows",
        "as indicated", "according to the provided", "from the input",
        "known data", "supplied information",
    ]
    has_integration = any(m in text_lower for m in integration_markers)

    ok = grounding_count >= 2 or has_integration
    return ok, f"grounding={grounding_count}, integration={has_integration}", grounding_count


def check_data_gap_acknowledgment(text, known_data):
    """When known_data insufficient, check sections acknowledge gaps."""
    if not known_data:
        return True  # Checked elsewhere via assumptions requirement
    # If known_data is thin (<100 chars), check for gap language
    if len(known_data.strip()) < 100:
        gap_markers = [
            "limited data", "insufficient", "additional data needed",
            "data gap", "would require", "not enough information",
        ]
        has_gap = any(m in text.lower() for m in gap_markers)
        return has_gap
    return True


def check_competitive_entities(text, industry_context, known_data):
    """Check competitive landscape section has entities (section-scoped)."""
    comp_section = extract_section(text, ["competitive", "competitor", "landscape"])
    if not comp_section:
        return False, 0, "no competitive landscape section"

    # Extract entities: capitalized words that aren't section headings
    entities = set()
    for match in re.finditer(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', comp_section):
        entity = match.group(1).lower()
        words = set(entity.split())
        if not words.intersection(SECTION_HEADING_WORDS) and len(entity) > 2:
            entities.add(entity)

    # Also check for archetype language (fallback when no competitors given)
    archetype_markers = [
        "enterprise vendor", "open-source", "startup", "incumbent",
        "market leader", "niche player", "challenger", "disruptor",
        "legacy provider", "saas competitor", "direct competitor",
        "indirect competitor", "new entrant",
    ]
    has_archetypes = any(m in comp_section.lower() for m in archetype_markers)

    # Check for explicit "no data" acknowledgment
    no_data_markers = [
        "no competitive data", "competitor data not",
        "competitive information needed", "competitor information would",
    ]
    has_no_data_ack = any(m in comp_section.lower() for m in no_data_markers)

    entity_count = len(entities)
    ok = entity_count >= 2 or has_archetypes or has_no_data_ack

    return ok, entity_count, "ok" if ok else "need 2+ entities, archetypes, or data gap ack"


def check_trend_count(text, depth):
    """Check trend count scales with depth."""
    trend_section = extract_section(text, ["trend", "key trend"])
    if not trend_section:
        return 0, False

    bullets = len(re.findall(r'^\s*[-*•]\s', trend_section, re.MULTILINE))
    numbered = len(re.findall(r'^\s*\d+[\.\)]\s', trend_section, re.MULTILINE))
    sub_headings = len(re.findall(r'^###\s', trend_section, re.MULTILINE))
    count = max(bullets, numbered, sub_headings)

    required = {"overview": 3, "detailed": 5, "competitive_focus": 3}.get(depth, 3)
    return count, count >= required


def check_actionable_recommendations(text):
    """Check recommendations contain action verbs."""
    rec_section = extract_section(text, ["recommendation", "action", "next step"])
    if not rec_section:
        return False, 0

    rec_lines = re.findall(r'^\s*[-*•]\s+(.+)', rec_section, re.MULTILINE)
    if not rec_lines:
        rec_lines = [l.strip() for l in rec_section.split('\n')
                     if l.strip() and len(l.strip()) > 15 and not l.strip().startswith('#')]

    actionable = 0
    for line in rec_lines:
        line_lower = line.lower()
        if any(v in line_lower for v in ACTION_VERBS):
            actionable += 1

    total = len(rec_lines)
    return total > 0 and actionable >= total * 0.5, actionable


def check_citation_fabrication(text, known_data):
    """Check for fabricated research citations."""
    violations = []
    known_lower = (known_data or "").lower()
    for pattern in CITATION_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            # Check if the citation references something from known_data
            match_text = match.group().lower()
            # Extract key words from citation
            cite_words = set(w for w in match_text.split() if len(w) > 3)
            overlap = sum(1 for w in cite_words if w in known_lower)
            if overlap < 2:
                violations.append(match.group())
    return violations


def check_fabrication_flag(text, known_data):
    """When known_data is empty, flag precise stats as potentially fabricated."""
    if known_data and known_data.strip():
        return []

    flags = []
    # Flag precise percentages
    for match in re.finditer(r'[\d]+\.[\d]+%\s*(?:CAGR|growth|increase|decline)', text, re.IGNORECASE):
        flags.append(f"Potentially fabricated stat (no known_data): {match.group()}")

    # Flag specific dollar amounts with market context
    for match in re.finditer(r'\$[\d,]+(?:\.\d+)?\s*(?:billion|million|B|M)\s*(?:market|industry|sector)', text, re.IGNORECASE):
        flags.append(f"Potentially fabricated market size (no known_data): {match.group()}")

    return flags


def check_segment_naming(text):
    """Check segments have meaningful names, not generic labels."""
    seg_section = extract_section(text, ["segmentation", "segment"])
    if not seg_section:
        return True, []

    seg_lower = seg_section.lower()
    generic_found = [g for g in GENERIC_SEGMENT_NAMES if g in seg_lower]
    return len(generic_found) == 0, generic_found


def check_insight_linkage(text):
    """Check opportunities and recommendations reference trends/segments/competition."""
    issues = []

    opp_section = extract_section(text, ["opportunit"])
    if opp_section:
        opp_lower = opp_section.lower()
        has_link = any(kw in opp_lower for kw in INSIGHT_LINK_KEYWORDS)
        if not has_link:
            issues.append("Opportunities section doesn't reference trends, segments, or competitive insights")

    rec_section = extract_section(text, ["recommendation", "action"])
    if rec_section:
        rec_lower = rec_section.lower()
        has_link = any(kw in rec_lower for kw in INSIGHT_LINK_KEYWORDS)
        if not has_link:
            issues.append("Recommendations section doesn't reference trends, segments, or competitive insights")

    return issues


def check_risk_grounding(text):
    """Check risks are tied to market forces, not generic."""
    risk_section = extract_section(text, ["risk", "threat", "challenge"])
    if not risk_section:
        return False

    risk_grounding_words = [
        "trend", "competitor", "regulation", "market", "demand",
        "technology", "cost", "supply", "adoption", "pricing",
        "economic", "geopolitical", "compliance",
    ]
    risk_lower = risk_section.lower()
    grounding_count = sum(1 for w in risk_grounding_words if w in risk_lower)
    return grounding_count >= 2


def check_depth_rules(text, depth):
    """Check depth-specific rules."""
    issues = []
    if depth == "detailed":
        # Must have sub-segments
        seg_section = extract_section(text, ["segmentation", "segment"])
        if seg_section:
            sub_headings = len(re.findall(r'^###\s', seg_section, re.MULTILINE))
            named_segments = len(re.findall(
                r'(?:^|\n)\s*[-*•]\s*\*\*([^*]+)\*\*',
                seg_section
            ))
            if sub_headings + named_segments < 2:
                issues.append("Detailed depth requires 2+ named sub-segments")

    elif depth == "competitive_focus":
        comp_section = extract_section(text, ["competitive", "competitor"])
        if comp_section:
            entities = set()
            for match in re.finditer(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', comp_section):
                entity = match.group(1).lower()
                words = set(entity.split())
                if not words.intersection(SECTION_HEADING_WORDS) and len(entity) > 2:
                    entities.add(entity)
            if len(entities) < 3:
                issues.append(f"Competitive focus requires 3+ competitor names, found {len(entities)}")

    return issues


# ── Full Deterministic Validation ─────────────────────────────────────────────
def validate_research(text, analysis):
    """Full deterministic validation. Returns (issues, vague_found, fabrication_flags)."""
    issues = []
    text_lower = text.lower()

    # 1. Required sections
    missing = check_required_sections(text)
    if missing:
        for m in missing:
            issues.append(f"Missing required section: {m}")

    # 2. Market sizing (3 paths)
    sizing_ok, sizing_msg = check_market_sizing(text)
    if not sizing_ok:
        issues.append(f"Market sizing: {sizing_msg}")

    # 3. Question coverage
    questions = analysis.get("specific_questions", "")
    q_ok, q_covered, q_total = check_question_coverage(text, questions)
    if not q_ok:
        issues.append(f"Question coverage: {q_covered}/{q_total} topic words found (need 60%)")

    # 4. Data grounding
    known_data = analysis.get("known_data", "")
    data_ok, data_msg, data_count = check_data_grounding(text, known_data)
    if not data_ok:
        issues.append(f"Data grounding: {data_msg}")

    # 4b. Data gap acknowledgment
    if known_data and not check_data_gap_acknowledgment(text, known_data):
        issues.append("Known data is thin but no data gap acknowledgment in report")

    # 5. Competitive entities (section-scoped)
    comp_ok, entity_count, comp_msg = check_competitive_entities(
        text, analysis.get("industry_context", ""), known_data)
    if not comp_ok:
        issues.append(f"Competitive landscape: {comp_msg}")

    # 6. Trend count (depth-scaled)
    depth = analysis.get("research_depth", "overview") or "overview"
    trend_count, trends_ok = check_trend_count(text, depth)
    if not trends_ok:
        required = {"overview": 3, "detailed": 5, "competitive_focus": 3}.get(depth, 3)
        issues.append(f"Trends: {trend_count} found, need {required} for {depth} depth")

    # 7. Actionable recommendations
    rec_ok, rec_actionable = check_actionable_recommendations(text)
    if not rec_ok:
        issues.append(f"Recommendations lack action verbs ({rec_actionable} actionable)")

    # 8. Citation fabrication
    citations = check_citation_fabrication(text, known_data)
    if citations:
        issues.append(f"Fabricated citations: {citations[:3]}")

    # 9. Segment naming quality
    naming_ok, generic_found = check_segment_naming(text)
    if not naming_ok:
        issues.append(f"Generic segment names: {generic_found}")

    # 10. Insight linkage
    linkage_issues = check_insight_linkage(text)
    issues.extend(linkage_issues)

    # 11. Risk grounding
    if not check_risk_grounding(text):
        issues.append("Risks not grounded in market forces, competition, or constraints")

    # 12. Depth-specific rules
    depth_issues = check_depth_rules(text, depth)
    issues.extend(depth_issues)

    # 13. Assumptions when no known_data
    if not known_data or not known_data.strip():
        assumptions = extract_section(text, ["assumption"])
        if not assumptions:
            issues.append("No known_data provided but Assumptions section missing")

    # 14. Banned vague analysis (penalty, not hard-fail)
    vague_found = [p for p in BANNED_VAGUE_ANALYSIS if p in text_lower]

    # 15. Fabrication flagging (penalty when known_data empty)
    fabrication_flags = check_fabrication_flag(text, known_data)

    return issues, vague_found, fabrication_flags


# ── Execution Role ────────────────────────────────────────────────────────────
EXECUTION_ROLE = """You are a senior market research analyst who produces precise, grounded
research reports. Every claim is tied to provided input data or clearly labeled as
an assumption. You NEVER fabricate statistics, market sizes, research citations, or
survey data. When data is insufficient, you state what data would be needed.

ABSOLUTE RULES:
1. Segments have meaningful names (SMB, enterprise, prosumers) — NEVER "Segment A/B"
2. Opportunities and recommendations must reference specific trends, segments, or
   competitive insights from the analysis — no disconnected claims
3. Risks must be tied to market forces, competition, or constraints — not generic
4. Do NOT reference external sources unless provided in the input
5. If making general observations, label them explicitly as assumptions
6. When no competitive data is provided, describe competitive archetypes or
   categories (enterprise vendors, open-source alternatives, etc.)
7. Each recommendation must contain an action verb (invest, target, develop, etc.)"""


# ── Step Handlers ─────────────────────────────────────────────────────────────

def step_1_local(inputs, context):
    """Parse research context and identify analysis dimensions."""
    topic = inputs.get("research_topic", "").strip()
    if not topic or len(topic) < 20:
        return None, "research_topic must be at least 20 characters"

    industry = inputs.get("industry_context", "").strip()
    if not industry or len(industry) < 20:
        return None, "industry_context must be at least 20 characters"

    questions = inputs.get("specific_questions", "").strip()
    known_data = inputs.get("known_data", "").strip()
    depth = inputs.get("research_depth", "overview").strip()
    if depth not in ("overview", "detailed", "competitive_focus"):
        depth = "overview"

    has_questions = bool(questions)
    has_data = bool(known_data)
    input_numeric_tokens = list(extract_numeric_tokens(known_data)) if known_data else []

    # Extract sub-topics from questions
    sub_topics = []
    if questions:
        for line in questions.split('\n'):
            line = line.strip().strip('?').strip('-').strip('*').strip()
            if len(line) > 10:
                sub_topics.append(line)

    depth_rules = {
        "overview": {"min_trends": 3, "description": "High-level, broad strokes"},
        "detailed": {"min_trends": 5, "min_sub_segments": 2, "description": "Deep with sub-segments"},
        "competitive_focus": {"min_trends": 3, "min_competitors": 3, "description": "Competitor-centric"},
    }

    result = {
        "research_topic": topic,
        "industry_context": industry,
        "specific_questions": questions,
        "known_data": known_data,
        "research_depth": depth,
        "has_specific_questions": has_questions,
        "has_known_data": has_data,
        "input_numeric_tokens": input_numeric_tokens,
        "sub_topics": sub_topics,
        "depth_rules": depth_rules.get(depth, depth_rules["overview"]),
    }

    return {"output": result}, None


def step_2_llm(inputs, context):
    """Generate complete market research report."""
    analysis = context.get("step_1_output", context.get("_resolved_input", {}))
    if not analysis or not isinstance(analysis, dict):
        return None, "No analysis from step 1"

    topic = analysis.get("research_topic", "")
    industry = analysis.get("industry_context", "")
    questions = analysis.get("specific_questions", "")
    known_data = analysis.get("known_data", "")
    depth = analysis.get("research_depth", "overview")
    has_data = analysis.get("has_known_data", False)

    depth_rules = {
        "overview": "High-level analysis. Broad market segments. 3+ key trends. Overview-level competitive landscape.",
        "detailed": "Deep analysis. 2+ named sub-segments with characteristics. 5+ trends with implications. Detailed competitive positioning.",
        "competitive_focus": "Competitor-centric analysis. Name 3+ competitors. Competitive comparison. Positioning gaps and advantages. Competitive landscape is the primary section.",
    }

    data_instruction = ""
    if not has_data:
        data_instruction = (
            "\nCRITICAL: No known_data provided. You MUST:\n"
            "1. NOT fabricate any statistics, market sizes, percentages, or dollar amounts\n"
            "2. Use qualitative scoping (e.g., 'emerging market', 'fragmented landscape')\n"
            "3. State what data would be needed for quantitative analysis\n"
            "4. Include an Assumptions section listing all assumptions made\n"
        )

    questions_block = ""
    if questions:
        questions_block = f"\nSPECIFIC QUESTIONS TO ADDRESS:\n{questions}\n(Address ALL questions in the report)"

    system = f"""{EXECUTION_ROLE}
{data_instruction}

RESEARCH DEPTH: {depth.upper()}
DEPTH RULES: {depth_rules.get(depth, '')}

REQUIRED SECTIONS (all must be present as markdown headings):
1. ## Market Overview — Size/scope context (numbers if available, qualitative scoping if not, or explicit data gap)
2. ## Market Segmentation — Distinct segments with MEANINGFUL names (never "Segment A/B"). Each with characteristics.
3. ## Key Trends — {'5+ trends with implications' if depth == 'detailed' else '3+ specific trends'}. Not generic.
4. ## Competitive Landscape — {'3+ named competitors with positioning comparison' if depth == 'competitive_focus' else 'Named entities from input, or competitive archetypes if no data'}
5. ## Opportunities — Must reference specific trends, segments, or competitive gaps from your analysis
6. ## Risk Factors — Tied to market forces, competition, regulations, or constraints. Not generic.
7. ## Recommendations — Each must contain an action verb. Each must reference trends/segments/competition.
{"8. ## Assumptions — Required since no quantitative data provided." if not has_data else "8. ## Assumptions — State any assumptions made."}

RULES:
- Do NOT fabricate research citations, survey data, or precise statistics not in known_data
- Do NOT use generic segment names (Segment A, Group 1)
- Opportunities and recommendations must link to analysis sections
- Risks must be grounded in specific market forces
- If no competitors in input: describe archetypes (enterprise vendors, open-source, etc.)
- If specific questions provided: address each one in the relevant section"""

    user = f"""RESEARCH TOPIC: {topic}

INDUSTRY CONTEXT: {industry}

KNOWN DATA: {known_data or 'NOT PROVIDED — do not fabricate statistics'}
{questions_block}

Generate the complete market research report ({depth} depth)."""

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

    research = context.get("improved_research", context.get("generated_research",
               context.get("step_2_output", "")))
    if isinstance(research, dict):
        research = str(research)
    if not research:
        return None, "No research report to evaluate"

    # ── Layer 1: Deterministic ────────────────────────────────────────────
    det_issues, vague_found, fabrication_flags = validate_research(research, analysis)
    det_penalty = len(det_issues) + len(vague_found) * 0.5 + len(fabrication_flags) * 0.5
    structural_score = max(0, 10 - (det_penalty * 1.5))

    if structural_score <= 2:
        return {"output": {
            "quality_score": structural_score,
            "structural_score": structural_score,
            "analytical_depth": 0,
            "practical_value": 0,
            "deterministic_issues": det_issues,
            "vague_phrases": vague_found,
            "fabrication_flags": fabrication_flags,
            "llm_feedback": "Too many structural issues — fix deterministic failures first",
            "feedback": f"STRUCTURAL ({len(det_issues)} issues): " + " | ".join(det_issues[:8]),
        }}, None

    # ── Layer 2: LLM quality ──────────────────────────────────────────────
    system = """You are a market research quality reviewer. Score (each 0-10):
- analytical_depth: Are insights specific and actionable? Do they go beyond
  surface-level observations? Are segments, trends, and competitors analyzed
  with enough depth for the requested research level?
- practical_value: Would a decision-maker find this useful? Are recommendations
  tied to analysis? Are risks actionable?

JSON ONLY — no markdown, no backticks:
{"analytical_depth": N, "practical_value": N, "llm_feedback": "Notes"}"""

    user = f"""RESEARCH REPORT:
{research[:5000]}

DEPTH: {analysis.get('research_depth', 'overview')}
KNOWN DATA PROVIDED: {analysis.get('has_known_data', False)}

Evaluate."""

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    content, error = call_resolved(messages, context, max_tokens=1500)
    if error:
        content, error = call_openai(messages, model="gpt-5.4-mini", max_tokens=1500)

    llm_scores = {"analytical_depth": 5, "practical_value": 5, "llm_feedback": ""}
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
    value_score = llm_scores.get("practical_value", 5)
    quality_score = min(structural_score, depth_score, value_score)

    feedback_parts = []
    if det_issues:
        feedback_parts.append(f"STRUCTURAL ({len(det_issues)}): " + " | ".join(det_issues[:8]))
    if vague_found:
        feedback_parts.append(f"VAGUE ({len(vague_found)}): " + ", ".join(vague_found))
    if fabrication_flags:
        feedback_parts.append(f"FABRICATION ({len(fabrication_flags)}): " + " | ".join(fabrication_flags[:3]))
    llm_fb = llm_scores.get("llm_feedback", "")
    if llm_fb:
        feedback_parts.append(f"QUALITY: {llm_fb}")

    return {"output": {
        "quality_score": quality_score,
        "structural_score": structural_score,
        "analytical_depth": depth_score,
        "practical_value": value_score,
        "deterministic_issues": det_issues,
        "vague_phrases": vague_found,
        "fabrication_flags": fabrication_flags,
        "llm_feedback": llm_fb,
        "feedback": " || ".join(feedback_parts) if feedback_parts else "All checks passed",
    }}, None


def step_4_llm(inputs, context):
    """Strengthen research based on critic feedback."""
    analysis = context.get("step_1_output", {})
    topic = analysis.get("research_topic", "")
    depth = analysis.get("research_depth", "overview")

    research = context.get("improved_research", context.get("generated_research",
               context.get("step_2_output", "")))
    if isinstance(research, dict):
        research = str(research)

    critic = context.get("step_3_output", {})
    if isinstance(critic, str):
        try:
            critic = json.loads(critic)
        except (json.JSONDecodeError, TypeError):
            critic = {"feedback": critic}

    feedback = critic.get("feedback", "")
    det_issues = critic.get("deterministic_issues", [])
    fabrication_flags = critic.get("fabrication_flags", [])

    det_section = ""
    if det_issues:
        det_section = "\nCRITICAL FIXES:\n" + "\n".join(f"  - {i}" for i in det_issues[:10])
    if fabrication_flags:
        det_section += "\nFABRICATION FLAGS (remove or qualify):\n" + "\n".join(f"  - {f}" for f in fabrication_flags[:5])

    system = f"""{EXECUTION_ROLE}

Improving a market research report based on critic feedback. DEPTH: {depth}
{det_section}

RULES:
1. Fix ALL structural issues listed above.
2. Use meaningful segment names — NEVER "Segment A/B".
3. Link opportunities and recommendations to specific trends/segments/competition.
4. Ground risks in market forces, not generic statements.
5. Remove or qualify any flagged fabricated statistics.
6. If no competitive data: use archetypes (enterprise vendors, open-source, etc.).
7. Every recommendation needs an action verb.
8. Do NOT add fabricated citations.
9. Output ONLY the improved markdown. No preamble."""

    user = f"""RESEARCH TOPIC: {topic[:1000]}

CURRENT REPORT:
{research}

FEEDBACK: {feedback}

Fix all issues."""

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
    for key in ("improved_research", "generated_research", "step_2_output"):
        v = context.get(key, "")
        if v and isinstance(v, str) and v.strip():
            return v
    return context.get("generated_research", "")


def step_5_write(inputs, context):
    """Full deterministic gate."""
    best = _select_best_output(context)
    if isinstance(best, dict):
        best = str(best)
    if not best or not best.strip():
        return None, "No research report to write"

    analysis = context.get("step_1_output", {})

    issues, vague_found, fabrication_flags = validate_research(best, analysis)

    critical_keywords = [
        "missing required section", "no market overview",
        "no competitive landscape", "fabricated citation",
        "question coverage", "no sizing indicator",
    ]
    critical = [i for i in issues if any(k in i.lower() for k in critical_keywords)]

    if critical:
        summary = "; ".join(critical[:5])
        return None, f"RESEARCH INTEGRITY FAILURE ({len(critical)} critical): {summary}"

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
