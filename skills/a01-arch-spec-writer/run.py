#!/usr/bin/env python3
"""
NemoClaw Skill: a01-arch-spec-writer
Architecture Specification Writer v1.0.0
F01 | A | internal | executor
Schema v2 | Runner v4.0+

Generates architecture specifications with enforced structural rigor.
Deterministic validation:
- Required sections presence
- Layer breakdown (2+ layers)
- Component responsibility + interface per component
- Data/control flow: directional steps referencing 2+ components
- Dependencies: direction markers + interaction type
- Risk count (3+)
- Banned vague architecture language
- Constraint propagation from input
- Assumptions section when info is missing
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


def call_openai(messages, model=None, max_tokens=6000):
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


def call_anthropic(messages, model=None, max_tokens=6000):
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


# ── Banned Vague Architecture Language ────────────────────────────────────────
BANNED_VAGUE = [
    "handles everything", "manages stuff", "general purpose layer",
    "flexible component", "does various things", "as needed",
    "multi-purpose module", "generic handler", "universal adapter",
    "smart layer", "magic layer",
]

# Reuse fluff from e08/c07
BANNED_FLUFF = [
    "leverage synergies", "optimize positioning", "drive innovation forward",
    "best-in-class solution", "paradigm shift", "move the needle",
    "low-hanging fruit", "circle back", "synergistic approach",
    "thought leadership", "value proposition alignment",
]


# ── Required Sections ─────────────────────────────────────────────────────────
REQUIRED_SECTION_GROUPS = [
    {"label": "Purpose/Problem Statement",
     "patterns": ["purpose", "problem", "objective", "motivation", "why"]},
    {"label": "Scope (in-scope/out-of-scope)",
     "patterns": ["scope", "in-scope", "out of scope", "non-goal", "not in scope"]},
    {"label": "Architecture Overview / Layer Breakdown",
     "patterns": ["layer", "architecture overview", "stack", "tier"]},
    {"label": "Components",
     "patterns": ["component", "module", "service", "subsystem"]},
    {"label": "Data/Control Flow",
     "patterns": ["data flow", "control flow", "flow", "sequence", "pipeline"]},
    {"label": "Dependencies",
     "patterns": ["dependenc", "depend"]},
    {"label": "Risks",
     "patterns": ["risk"]},
    {"label": "Extension Points / Open Questions",
     "patterns": ["extension", "open question", "future", "evolution"]},
]


# ── Layer Detection ───────────────────────────────────────────────────────────
def count_layers(spec):
    """Count distinct layers mentioned in the spec.
    Looks for patterns like '### Layer 1', '- **Layer:', 'Layer N —'."""
    layer_patterns = [
        re.compile(r'#{1,4}\s*(?:Layer\s+\d|.+Layer\b)', re.IGNORECASE),
        re.compile(r'[-*]\s*\*?\*?Layer\s', re.IGNORECASE),
        re.compile(r'(?:Layer|Tier)\s+\d', re.IGNORECASE),
    ]
    layers = set()
    for pat in layer_patterns:
        for m in pat.finditer(spec):
            layers.add(m.group().strip().lower()[:40])
    return max(len(layers), 0)


# ── Component Validation ──────────────────────────────────────────────────────
RESPONSIBILITY_MARKERS = [
    "responsibility", "role", "purpose", "owns", "responsible for",
    "handles", "manages", "provides", "produces", "controls",
]

INTERFACE_MARKERS = [
    "interface", "contract", "api", "exposes", "accepts", "endpoint",
    "input", "output", "protocol", "format", "schema", "method",
    "receives", "returns", "publishes", "subscribes", "emits",
]


def extract_component_sections(spec):
    """Extract component subsections from the spec.
    Returns list of (component_name, section_content) tuples."""
    components = []

    # Find the components section
    comp_match = re.search(
        r'(?:##\sComponent\w*)(.*?)(?=\n##\s[^#]|\Z)',
        spec, re.IGNORECASE | re.DOTALL
    )
    if not comp_match:
        return components

    comp_section = comp_match.group(1)

    # Extract subsections (### Component Name or **Component Name**)
    sub_pattern = re.compile(
        r'(?:###\s*(.+?)|([\*]{2}.+?[\*]{2}))\s*\n(.*?)(?=\n###\s|\n\*\*[A-Z]|\Z)',
        re.DOTALL
    )
    for m in sub_pattern.finditer(comp_section):
        name = (m.group(1) or m.group(2) or "").strip().strip("*")
        content = m.group(3).strip()
        if name and content:
            components.append((name, content))

    # Fallback: if no sub-headings, check for bullet-style components
    if not components:
        bullet_pattern = re.compile(
            r'[-*]\s*\*?\*?([^:\n*]+)\*?\*?\s*[:—–-]\s*(.+?)(?=\n[-*]\s|\Z)',
            re.DOTALL
        )
        for m in bullet_pattern.finditer(comp_section):
            name = m.group(1).strip().strip("*")
            content = m.group(2).strip()
            if name and len(name) < 60:
                components.append((name, content))

    return components


def validate_component(name, content):
    """Check if a component has both responsibility and interface descriptions.
    Returns (has_responsibility, has_interface)."""
    content_lower = content.lower()
    has_resp = any(m in content_lower for m in RESPONSIBILITY_MARKERS)
    has_iface = any(m in content_lower for m in INTERFACE_MARKERS)
    return has_resp, has_iface


# ── Data/Control Flow Validation ──────────────────────────────────────────────
DIRECTIONAL_PATTERNS = [
    re.compile(r'→|->|⟶|➜|>>'),  # Arrow symbols
    re.compile(r'\bstep\s+\d', re.IGNORECASE),  # "Step 1", "Step 2"
    re.compile(r'^\s*\d+[\.\)]\s', re.MULTILINE),  # Numbered steps
    re.compile(r'\b(?:sends?\s+to|passes?\s+to|forwards?\s+to|routes?\s+to|writes?\s+to|reads?\s+from|receives?\s+from|calls?|invokes?|triggers?)\b', re.IGNORECASE),
]


def validate_data_flow(spec):
    """Validate data/control flow section has directional steps referencing components.
    Returns (valid, issues)."""
    issues = []

    # Find the flow section
    flow_match = re.search(
        r'(?:##\s(?:Data|Control)\s*(?:/\s*(?:Data|Control))?\s*Flow\w*)(.*?)(?=\n##\s[^#]|\Z)',
        spec, re.IGNORECASE | re.DOTALL
    )
    if not flow_match:
        # Try broader match
        flow_match = re.search(
            r'(?:##\s(?:Flow|Sequence|Pipeline)\w*)(.*?)(?=\n##\s[^#]|\Z)',
            spec, re.IGNORECASE | re.DOTALL
        )
    if not flow_match:
        issues.append("Data/Control Flow section not found")
        return False, issues

    flow_content = flow_match.group(1)

    # Check 1: Must have directional indicators
    has_direction = any(pat.search(flow_content) for pat in DIRECTIONAL_PATTERNS)
    if not has_direction:
        issues.append(
            "Data/Control Flow has no directional structure "
            "(need numbered steps, arrows, or directional verbs)")

    # Check 2: Must reference at least 2 distinct components/nouns
    # Extract capitalized multi-word phrases or known component-like terms
    component_refs = set()
    # Look for capitalized words that might be component names
    cap_words = re.findall(r'\b[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*\b', flow_content)
    for w in cap_words:
        if len(w) >= 3 and w not in {"The", "This", "Step", "Note", "When", "Data", "Flow"}:
            component_refs.add(w)
    # Also look for backtick-quoted terms
    backtick_refs = re.findall(r'`([^`]+)`', flow_content)
    component_refs.update(r for r in backtick_refs if len(r) >= 2)

    if len(component_refs) < 2:
        issues.append(
            f"Data/Control Flow references {len(component_refs)} component(s) "
            f"(minimum 2 required for meaningful flow)")

    return len(issues) == 0, issues


# ── Dependency Validation ─────────────────────────────────────────────────────
DIRECTION_MARKERS = [
    re.compile(r'\b(?:depends?\s+on|requires?|relies?\s+on|consumes?|reads?\s+from|imports?\s+from)\b', re.IGNORECASE),
    re.compile(r'\b(?:provides?\s+to|exposes?\s+to|writes?\s+to|publishes?\s+to|exports?\s+to|feeds?)\b', re.IGNORECASE),
    re.compile(r'→|->|⟶|←|<-'), # Arrows
    re.compile(r'\b(?:upstream|downstream)\b', re.IGNORECASE),
    re.compile(r'\b(?:calls?|invokes?|triggers?|notifies?)\b', re.IGNORECASE),
]

INTERACTION_TYPE_MARKERS = [
    re.compile(r'\b(?:API|REST|gRPC|GraphQL|HTTP|RPC|endpoint)\b', re.IGNORECASE),
    re.compile(r'\b(?:database|DB|SQL|SQLite|Postgres|Redis|Mongo)\b', re.IGNORECASE),
    re.compile(r'\b(?:queue|message|event|pub.?sub|stream|Kafka|AMQP)\b', re.IGNORECASE),
    re.compile(r'\b(?:file|filesystem|disk|JSON|YAML|CSV|log)\b', re.IGNORECASE),
    re.compile(r'\b(?:SDK|library|package|import|module)\b', re.IGNORECASE),
    re.compile(r'\b(?:CLI|command|subprocess|shell|stdin|stdout)\b', re.IGNORECASE),
    re.compile(r'\b(?:env|environment variable|config|\.env)\b', re.IGNORECASE),
]


def validate_dependencies(spec):
    """Validate dependencies section has direction markers and interaction types.
    Returns (valid, issues)."""
    issues = []

    dep_match = re.search(
        r'(?:##\sDependenc\w*)(.*?)(?=\n##\s[^#]|\Z)',
        spec, re.IGNORECASE | re.DOTALL
    )
    if not dep_match:
        issues.append("Dependencies section not found")
        return False, issues

    dep_content = dep_match.group(1)

    # Check direction markers
    has_direction = any(pat.search(dep_content) for pat in DIRECTION_MARKERS)
    if not has_direction:
        issues.append(
            "Dependencies lack direction markers "
            "(need: depends on, provides to, calls, →, upstream/downstream)")

    # Check interaction types
    has_interaction = any(pat.search(dep_content) for pat in INTERACTION_TYPE_MARKERS)
    if not has_interaction:
        issues.append(
            "Dependencies lack interaction type specification "
            "(need: API, DB, file, queue, CLI, SDK, config, etc.)")

    return len(issues) == 0, issues


# ── Risk Count ────────────────────────────────────────────────────────────────
def count_risks(spec):
    """Count distinct risks in the Risk section."""
    risk_match = re.search(
        r'(?:##\sRisk\w*)(.*?)(?=\n##\s[^#]|\Z)',
        spec, re.IGNORECASE | re.DOTALL
    )
    if not risk_match:
        return 0
    risk_content = risk_match.group(1)
    bullets = len(re.findall(r'^\s*[-*•]\s', risk_content, re.MULTILINE))
    numbered = len(re.findall(r'^\s*\d+[\.\)]\s', risk_content, re.MULTILINE))
    sub_headings = len(re.findall(r'^###\s', risk_content, re.MULTILINE))
    table_rows = len(re.findall(r'^\s*\|(?!\s*[-:])', risk_content, re.MULTILINE))
    if table_rows >= 2:
        table_rows -= 1  # Subtract header
    return max(bullets, numbered, sub_headings, table_rows)


# ── Full Validation ───────────────────────────────────────────────────────────
def validate_spec_structure(spec, constraint_keywords=None):
    """Full deterministic validation. Returns list of issues."""
    issues = []
    spec_lower = spec.lower()

    # ── Required sections ─────────────────────────────────────────────────
    for group in REQUIRED_SECTION_GROUPS:
        found = any(p in spec_lower for p in group["patterns"])
        if not found:
            issues.append(f"Missing required section: {group['label']}")

    # ── Layer count ───────────────────────────────────────────────────────
    layers = count_layers(spec)
    if layers < 2:
        # Fallback: count distinct heading-level items in architecture section
        arch_match = re.search(
            r'(?:##\s(?:Architecture|Layer|Stack|Tier)\w*)(.*?)(?=\n##\s[^#]|\Z)',
            spec, re.IGNORECASE | re.DOTALL
        )
        if arch_match:
            arch_content = arch_match.group(1)
            sub_items = len(re.findall(r'(?:^|\n)###\s', arch_content))
            bullet_items = len(re.findall(r'^\s*[-*]\s*\*?\*?(?:Layer|Tier)\b', arch_content,
                                           re.MULTILINE | re.IGNORECASE))
            layers = max(layers, sub_items, bullet_items)
        if layers < 2:
            issues.append(
                f"Architecture layer breakdown has {layers} layers (minimum 2 required)")

    # ── Component validation ──────────────────────────────────────────────
    components = extract_component_sections(spec)
    if len(components) == 0:
        issues.append("No component subsections found in Components section")
    else:
        for name, content in components:
            has_resp, has_iface = validate_component(name, content)
            if not has_resp:
                issues.append(
                    f"Component '{name}' missing responsibility description "
                    f"(need: responsibility, role, purpose, handles, manages)")
            if not has_iface:
                issues.append(
                    f"Component '{name}' missing interface/contract description "
                    f"(need: interface, contract, API, exposes, accepts, protocol)")

    # ── Data/Control Flow ─────────────────────────────────────────────────
    flow_valid, flow_issues = validate_data_flow(spec)
    issues.extend(flow_issues)

    # ── Dependencies ──────────────────────────────────────────────────────
    dep_valid, dep_issues = validate_dependencies(spec)
    issues.extend(dep_issues)

    # ── Risk count ────────────────────────────────────────────────────────
    risk_count = count_risks(spec)
    if risk_count < 3:
        issues.append(
            f"Risk section has {risk_count} risks (minimum 3 required)")

    # ── Banned vague architecture language ─────────────────────────────────
    for phrase in BANNED_VAGUE:
        if phrase in spec_lower:
            issues.append(f"Spec contains banned vague language: '{phrase}'")

    for phrase in BANNED_FLUFF:
        if phrase in spec_lower:
            issues.append(f"Spec contains banned fluff: '{phrase}'")

    # ── Constraint propagation ────────────────────────────────────────────
    if constraint_keywords:
        missing_constraints = []
        for kw in constraint_keywords:
            if kw.lower() not in spec_lower:
                missing_constraints.append(kw)
        if missing_constraints:
            issues.append(
                f"Input constraints not addressed in spec: "
                f"{missing_constraints[:5]}")

    return issues


# ── Step Handlers ─────────────────────────────────────────────────────────────

EXECUTION_ROLE = """You are a senior systems architect who writes precise, reviewable architecture
specifications. You follow these absolute rules:

1. Every component has an explicit RESPONSIBILITY and INTERFACE/CONTRACT description.
2. Data/control flow is DIRECTIONAL — numbered steps or arrows, referencing specific components.
3. Every dependency specifies DIRECTION (depends on / provides to / calls) and INTERACTION TYPE
   (API, DB, file, queue, CLI, SDK, config, etc.).
4. Risks are SPECIFIC to this subsystem — not generic architecture risks.
5. You NEVER introduce systems, technologies, or behaviors not implied by the input.
6. When information is missing, you state ASSUMPTIONS explicitly in a dedicated section.
7. You NEVER use vague architecture language: "handles everything", "manages stuff",
   "general purpose layer", "flexible component", "does various things".
8. If constraints are provided, they MUST appear in the spec (performance, cost, etc.)."""


def step_1_local(inputs, context):
    """Parse subsystem concept and identify architectural concerns."""
    name = inputs.get("subsystem_name", "").strip()
    if not name or len(name) < 3:
        return None, "subsystem_name too short (minimum 3 characters)"

    concept = inputs.get("subsystem_concept", "").strip()
    if not concept or len(concept) < 30:
        return None, "subsystem_concept too short (minimum 30 characters)"

    boundaries = inputs.get("boundaries", "").strip()
    integration = inputs.get("integration_context", "").strip()
    constraints = inputs.get("constraints", "").strip()

    # Extract component hints from concept
    component_hints = []
    concept_lower = concept.lower()
    component_markers = [
        "layer", "service", "module", "engine", "handler", "manager",
        "processor", "store", "cache", "queue", "gateway", "router",
        "enforcer", "validator", "runner", "scheduler", "monitor",
        "logger", "database", "api", "interface",
    ]
    for marker in component_markers:
        if marker in concept_lower:
            component_hints.append(marker)

    # Extract constraint keywords for propagation check
    constraint_keywords = []
    if constraints:
        # Extract significant terms from constraints
        for word in re.findall(r'\b\w{4,}\b', constraints.lower()):
            if word not in {"must", "should", "that", "with", "this", "from",
                            "have", "need", "will", "been", "being", "about",
                            "than", "more", "less", "also", "each", "every"}:
                constraint_keywords.append(word)
        # Deduplicate and limit
        constraint_keywords = sorted(set(constraint_keywords))[:10]

    # Detect integration points
    integration_points = []
    if integration:
        int_lower = integration.lower()
        for marker in ["api", "database", "queue", "file", "config", "sdk",
                        "http", "grpc", "rest", "webhook", "event"]:
            if marker in int_lower:
                integration_points.append(marker)

    result = {
        "subsystem_name": name,
        "subsystem_concept": concept,
        "boundaries": boundaries,
        "integration_context": integration,
        "constraints": constraints,
        "constraint_keywords": constraint_keywords,
        "component_hints": component_hints,
        "integration_points": integration_points,
        "word_count": len(concept.split()),
    }

    return {"output": result}, None


def step_2_llm(inputs, context):
    """Generate complete architecture specification."""
    analysis = context.get("step_1_output", context.get("_resolved_input", {}))
    if not analysis or not isinstance(analysis, dict):
        return None, "No analysis from step 1"

    name = analysis.get("subsystem_name", "")
    concept = analysis.get("subsystem_concept", "")
    boundaries = analysis.get("boundaries", "")
    integration = analysis.get("integration_context", "")
    constraints = analysis.get("constraints", "")
    constraint_kws = analysis.get("constraint_keywords", [])

    boundary_block = ""
    if boundaries:
        boundary_block = f"\nBOUNDARIES PROVIDED:\n{boundaries}"

    integration_block = ""
    if integration:
        integration_block = f"\nINTEGRATION CONTEXT:\n{integration}"

    constraint_block = ""
    if constraints:
        constraint_block = f"""
CONSTRAINTS PROVIDED (must appear in the spec):
{constraints}

These constraints MUST be referenced in the Architecture Overview, Components,
or a dedicated Constraints section. Do not ignore them."""

    system = f"""{EXECUTION_ROLE}

SUBSYSTEM: {name}
{boundary_block}
{integration_block}
{constraint_block}

SPECIFICATION STRUCTURE — produce ALL sections as markdown headings:

## Purpose

What this subsystem does, why it exists, what problem it solves.

## Scope

### In Scope
What this subsystem owns and handles.

### Out of Scope
What this subsystem explicitly does NOT handle.

## Architecture Overview

### Layer Breakdown
List at least 2 distinct layers. For each layer:
- Name and purpose
- What it owns
- What it does NOT own

## Components

For EACH component, create a subsection:

### [Component Name]
- **Responsibility:** What this component does and owns
- **Interface:** What it exposes, accepts, or provides to other components
  (API, method signatures, data formats, events)

Every component MUST have both Responsibility and Interface.

## Data/Control Flow

DIRECTIONAL flow description. Use one of:
- Numbered steps: "1. User submits request → Router... 2. Router calls Enforcer..."
- Arrow notation: "Component A → Component B → Component C"
- Sequential description with directional verbs (sends to, passes to, reads from)

MUST reference at least 2 specific components by name.

## Dependencies

For EACH dependency:
- **Direction:** depends on / provides to / calls / reads from
- **Interaction type:** API, DB, file, queue, CLI, SDK, config, environment variable
- What the dependency provides and what breaks if it is unavailable

## Risks

At least 3 SPECIFIC risks for this subsystem. For each:
- What could go wrong
- Impact
- Mitigation or monitoring approach

Not generic risks. Specific to this subsystem's architecture.

## Extension Points

What can be changed, added, or replaced without breaking the architecture.
What is locked and should NOT be changed without careful review.

## Assumptions

State any assumptions made due to missing information in the input.
If no assumptions were needed, state "No assumptions required — all
information was provided in the input."

## Open Questions

Unresolved design questions that need answers before implementation.

ABSOLUTE RULES:
1. Use ONLY the information provided. Do not introduce technologies or
   systems not implied by the input.
2. When information is missing, add it to Assumptions — do not silently invent.
3. Every component has Responsibility AND Interface.
4. Data flow is DIRECTIONAL with component references.
5. Dependencies have DIRECTION and INTERACTION TYPE.
6. Risks are SPECIFIC, not generic.
7. Do NOT use: "handles everything", "manages stuff", "general purpose layer",
   "flexible component", "does various things", "as needed".

Output ONLY the markdown specification. No preamble, no explanation."""

    user = f"""SUBSYSTEM NAME: {name}

CONCEPT:
{concept}

Generate the complete architecture specification."""

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
    constraint_kws = analysis.get("constraint_keywords", [])

    spec = context.get("improved_spec", context.get("generated_spec",
           context.get("step_2_output", "")))
    if isinstance(spec, dict):
        spec = str(spec)
    if not spec:
        return None, "No spec to evaluate"

    # ── Layer 1: Deterministic validation ─────────────────────────────────
    det_issues = validate_spec_structure(spec, constraint_kws)

    det_penalty = len(det_issues)
    structural_score = max(0, 10 - (det_penalty * 2))

    if structural_score <= 2:
        return {"output": {
            "quality_score": structural_score,
            "structural_score": structural_score,
            "logical_consistency": 0,
            "boundary_clarity": 0,
            "deterministic_issues": det_issues,
            "llm_feedback": "Too many structural issues — fix deterministic failures first",
            "feedback": f"STRUCTURAL ({len(det_issues)} issues): " + " | ".join(det_issues[:8]),
        }}, None

    # ── Layer 2: LLM quality evaluation ───────────────────────────────────
    system = """You are a strict architecture specification evaluator.

Score these dimensions (each 0-10):

- logical_consistency: Does the spec make internal sense? Do components
  reference each other consistently? Does the data flow match the component
  descriptions? Are layer boundaries respected in the flow?

- boundary_clarity: Are in-scope and out-of-scope clearly defined? Is it
  unambiguous what this subsystem owns vs what adjacent systems own?
  Could a developer implement from this spec without guessing scope?

Respond with JSON ONLY — no markdown, no backticks:
{"logical_consistency": N, "boundary_clarity": N, "llm_feedback": "Specific notes"}"""

    user = f"""GENERATED ARCHITECTURE SPEC:
{spec[:5000]}

Evaluate logical consistency and boundary clarity."""

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    content, error = call_resolved(messages, context, max_tokens=1500)
    if error:
        content, error = call_openai(messages, max_tokens=1500)

    llm_scores = {"logical_consistency": 5, "boundary_clarity": 5, "llm_feedback": ""}
    if not error and content:
        try:
            cleaned = content.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
                cleaned = re.sub(r'\s*```$', '', cleaned)
            llm_scores = json.loads(cleaned)
        except (json.JSONDecodeError, TypeError):
            llm_scores["llm_feedback"] = content

    logic = llm_scores.get("logical_consistency", 5)
    boundary = llm_scores.get("boundary_clarity", 5)
    quality_score = min(structural_score, logic, boundary)

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
        "logical_consistency": logic,
        "boundary_clarity": boundary,
        "deterministic_issues": det_issues,
        "llm_feedback": llm_fb,
        "feedback": " || ".join(feedback_parts) if feedback_parts else "All checks passed",
    }}, None


def step_4_llm(inputs, context):
    """Strengthen specification based on critic feedback."""
    analysis = context.get("step_1_output", {})
    concept = analysis.get("subsystem_concept", "")
    name = analysis.get("subsystem_name", "")
    constraints = analysis.get("constraints", "")

    spec = context.get("improved_spec", context.get("generated_spec",
           context.get("step_2_output", "")))
    if isinstance(spec, dict):
        spec = str(spec)

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

    constraint_note = ""
    if constraints:
        constraint_note = f"\nCONSTRAINTS (must appear in spec): {constraints}"

    system = f"""{EXECUTION_ROLE}

You are improving an architecture specification based on critic feedback.
SUBSYSTEM: {name}
{constraint_note}
{det_section}

RULES:
1. Fix ALL structural issues listed above first.
2. Every component MUST have Responsibility AND Interface descriptions.
3. Data flow MUST be directional with numbered steps or arrows referencing components.
4. Dependencies MUST have direction (depends on / provides to) and interaction type (API, DB, file, etc.).
5. Risks must be specific — at least 3.
6. Do NOT introduce systems not implied by the input.
7. State assumptions explicitly.
8. Output ONLY the improved markdown specification. No preamble."""

    user = f"""CURRENT SPEC:
{spec}

CRITIC FEEDBACK: {feedback}

CONCEPT (reference): {concept[:1000]}

Fix all issues. Output ONLY the improved spec."""

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
    """Latest surviving candidate."""
    for key in ("improved_spec", "generated_spec", "step_2_output"):
        v = context.get(key, "")
        if v and isinstance(v, str) and v.strip():
            return v
    return context.get("generated_spec", "")


def step_5_write(inputs, context):
    """Full deterministic gate — hard-fail on critical violations."""
    best = _select_best_output(context)
    if isinstance(best, dict):
        best = str(best)
    if not best or not best.strip():
        return None, "No spec to write"

    analysis = context.get("step_1_output", {})
    constraint_kws = analysis.get("constraint_keywords", [])

    issues = validate_spec_structure(best, constraint_kws)

    # Hard-fail on critical structural issues
    critical_keywords = [
        "missing required section", "no component subsections",
        "missing responsibility", "missing interface",
        "no directional structure", "references 0 component",
        "references 1 component", "dependencies section not found",
        "lack direction markers", "lack interaction type",
        "risk section has 0", "risk section has 1", "risk section has 2",
    ]
    critical = [i for i in issues if any(k in i.lower() for k in critical_keywords)]

    if critical:
        summary = "; ".join(critical[:5])
        return None, f"SPEC INTEGRITY FAILURE ({len(critical)} critical): {summary}"

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
