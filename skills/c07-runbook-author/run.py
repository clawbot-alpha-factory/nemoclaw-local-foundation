#!/usr/bin/env python3
"""
NemoClaw Skill: c07-runbook-author
Runbook Author v1.0.0
F07 | C | dual-use | executor
Schema v2 | Runner v4.0+

Generates structured operational runbooks with decision trees, verification
checkpoints, rollback instructions, and quick reference cards.

Deterministic validation:
- Procedure coverage: section + actionable steps + verification per procedure
- Decision tree branching: recovery/incident must have real if/else branching
- Rollback enforcement: recovery/modification must have rollback or explicit no-rollback
- Quick reference card presence
- Troubleshooting scenario count (3+)
- Extended banned phrase list (operational vagueness)
- Escalation paths for on-call audience
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone



# ── LLM Helpers (routed through lib/routing.py — L-003 compliant) ────────────
def call_openai(messages, model=None, max_tokens=6000):
    from lib.routing import call_llm_or_chain
    return call_llm_or_chain(messages, task_class="general_short", task_domain="creative_writing", max_tokens=max_tokens)

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


# ── Banned Phrases (extended from e08 + operational vagueness) ────────────────
BANNED_FLUFF = [
    "leverage synergies", "optimize positioning", "drive innovation forward",
    "best-in-class solution", "paradigm shift", "move the needle",
    "low-hanging fruit", "circle back", "synergistic approach",
    "thought leadership", "value proposition alignment",
]

BANNED_VAGUE_OPS = [
    # "check logs" without specifying which — pattern checks context
    # "investigate further" without specifying what
    "investigate further",
    "investigate as needed",
    "debug as necessary",
    "troubleshoot accordingly",
    "look into it",
    "check and fix",
    "handle appropriately",
    "resolve as needed",
    "take appropriate action",
]


def check_vague_log_references(text):
    """Detect 'check logs' without specifying which logs.
    Returns list of vague references found."""
    vague = []
    # Find all "check logs" / "review logs" / "inspect logs" occurrences
    log_refs = re.finditer(
        r'(?:check|review|inspect|look at|examine)\s+(?:the\s+)?logs?\b',
        text, re.IGNORECASE
    )
    for match in log_refs:
        # Look for specificity within 80 chars after the match
        start = match.start()
        end = min(match.end() + 80, len(text))
        context_after = text[match.end():end].lower()
        # Specific log references: file paths, log names, or "at" + path
        has_specificity = any(marker in context_after for marker in [
            "/", ".log", ".jsonl", "provider-", "budget-", "tools-",
            "validation-", "audit", "usage", "stderr", "stdout",
            "docker logs", "journalctl", "syslog",
        ])
        if not has_specificity:
            vague.append(match.group())
    return vague


# ── Procedure Classification ──────────────────────────────────────────────────
PROCEDURE_KEYWORDS = {
    "startup": ["start", "cold start", "boot", "initialize", "launch", "spin up",
                 "restart", "reboot"],
    "verification": ["health check", "verify", "validate", "status", "check", "test"],
    "recovery": ["recover", "restore", "repair", "failover", "fallback",
                  "disaster", "corrupt", "broken"],
    "maintenance": ["backup", "cleanup", "rotate", "upgrade", "update", "patch",
                     "migrate", "archive", "prune", "reset", "fix"],
    "incident": ["incident", "outage", "alert", "escalat", "triage", "on-call",
                  "page", "sev1", "sev2", "emergency", "response"],
    "modification": ["config change", "modify", "reconfigure", "change", "adjust",
                      "tune", "scale", "resize"],
}

# These types require decision trees
DECISION_TREE_REQUIRED = {"recovery", "incident"}

# These types require rollback instructions
ROLLBACK_REQUIRED = {"recovery", "modification"}


def classify_procedure(name):
    """Classify a procedure by its name. Returns set of types."""
    name_lower = name.lower().strip()
    types = set()
    for ptype, keywords in PROCEDURE_KEYWORDS.items():
        if any(kw in name_lower for kw in keywords):
            types.add(ptype)
    if not types:
        types.add("maintenance")  # Default fallback
    return types


# ── Decision Tree Detection ───────────────────────────────────────────────────
# Prefix that handles bullets, numbers, bold markers before conditionals
# Matches: "  - If", "  * If", "  1. If", "  **If", "  - **If", "If"
_LINE_PREFIX = r'^\s*(?:[-*•]\s+)?(?:\d+[\.\)]\s+)?\*?\*?\s*'

# Conditional openers
CONDITIONAL_PATTERNS = [
    re.compile(_LINE_PREFIX + r'(?:If|When)\b', re.MULTILINE | re.IGNORECASE),
]

# Branch alternatives
BRANCH_PATTERNS = [
    re.compile(_LINE_PREFIX + r'(?:Otherwise|Else|If not|If this fails|If it does not|If the .+ fails|If .+ is not)\b',
               re.MULTILINE | re.IGNORECASE),
]

# Multi-conditional blocks (at least 2 If/When blocks = implicit branching)
MULTI_CONDITIONAL = re.compile(
    r'(?:' + _LINE_PREFIX + r'(?:If|When)\b)',
    re.MULTILINE | re.IGNORECASE
)


def has_real_decision_tree(section_text):
    """Check if section contains real decision tree branching.
    Requires EITHER:
    - At least one If/When AND at least one Otherwise/Else
    - OR at least 2 distinct conditional blocks
    Returns (has_tree, detail)."""

    # Count conditional openers
    conditionals = len(MULTI_CONDITIONAL.findall(section_text))

    # Check for branch alternatives
    has_else = any(pat.search(section_text) for pat in BRANCH_PATTERNS)

    # Path 1: If + Else/Otherwise = real branching
    if conditionals >= 1 and has_else:
        return True, f"{conditionals} conditional(s) with else/otherwise branch"

    # Path 2: 2+ distinct conditional blocks = implicit branching
    if conditionals >= 2:
        return True, f"{conditionals} conditional blocks (implicit branching)"

    if conditionals == 1 and not has_else:
        return False, "Only 1 conditional with no alternative path — not real branching"

    return False, "No conditional logic found"


# ── Verification Checkpoint Detection ─────────────────────────────────────────
VERIFY_PATTERNS = [
    re.compile(r'\*?\*?(?:Expected|Verify|Confirm|Check|Should\s+(?:show|output|return|print|display))\s*[:\*]', re.IGNORECASE),
    re.compile(r'#\s*Expected\b', re.IGNORECASE),
]


def count_verification_checkpoints(section_text):
    """Count verification checkpoints in a section."""
    count = 0
    for pat in VERIFY_PATTERNS:
        count += len(pat.findall(section_text))
    return count


# ── Actionable Step Detection ─────────────────────────────────────────────────
CODE_BLOCK_PATTERN = re.compile(r'```(?:\w+)?\s*\n.*?\n\s*```', re.DOTALL)

UI_ACTION_PATTERNS = [
    re.compile(r'(?:open|launch|navigate\s+to|go\s+to|click|select|toggle|enable|disable|set)\s', re.IGNORECASE),
    re.compile(r'→|➜|⟶|>>', re.IGNORECASE),
    re.compile(r'\*\*UI\s*(?:Action|Step)\*\*', re.IGNORECASE),
]

NUMBERED_STEP_PATTERN = re.compile(r'^\s*\d+[\.\)]\s', re.MULTILINE)


def count_actionable_steps(section_text):
    """Count actionable steps: code blocks, UI actions, or numbered instructions."""
    code_blocks = len(CODE_BLOCK_PATTERN.findall(section_text))
    ui_actions = sum(1 for pat in UI_ACTION_PATTERNS if pat.search(section_text))
    numbered = len(NUMBERED_STEP_PATTERN.findall(section_text))
    return code_blocks + min(ui_actions, 3) + numbered


# ── Rollback Detection ────────────────────────────────────────────────────────
ROLLBACK_PATTERNS = [
    re.compile(r'\b(?:rollback|roll back|revert|undo|reverse|restore previous|back out)\b', re.IGNORECASE),
    re.compile(r'\bno rollback\b', re.IGNORECASE),
    re.compile(r'\bnot applicable\b.*\brollback\b', re.IGNORECASE),
    re.compile(r'\brollback\b.*\bnot applicable\b', re.IGNORECASE),
    re.compile(r'\bno reversal\b', re.IGNORECASE),
    re.compile(r'\bcannot be undone\b', re.IGNORECASE),
    re.compile(r'\bnon-reversible\b', re.IGNORECASE),
]


def has_rollback_content(section_text):
    """Check if section mentions rollback, revert, or explicit no-rollback."""
    return any(pat.search(section_text) for pat in ROLLBACK_PATTERNS)


# ── Escalation Detection ─────────────────────────────────────────────────────
ESCALATION_PATTERNS = [
    re.compile(r'\b(?:escalat|page|notify|alert|contact|reach out to|inform)\b', re.IGNORECASE),
    re.compile(r'\b(?:on-call|oncall|pager|incident commander|team lead)\b', re.IGNORECASE),
]


def has_escalation_content(text):
    """Check if text contains escalation instructions."""
    return sum(1 for pat in ESCALATION_PATTERNS if pat.search(text)) >= 1


# ── Section Extraction ────────────────────────────────────────────────────────

# Words to ignore when matching procedure names to headings
STOP_WORDS = {
    "a", "an", "the", "of", "for", "to", "in", "on", "at", "by",
    "and", "or", "with", "after", "before", "from", "into", "during",
    "#", "##", "###", "####", "procedure", "procedure:",
}


def _significant_words(text):
    """Extract significant words from text, filtering stop words and markdown."""
    words = re.sub(r'[^a-z0-9\s]', ' ', text.lower()).split()
    return {w for w in words if w not in STOP_WORDS and len(w) >= 2}


def extract_procedure_sections(runbook, procedure_names):
    """Extract sections corresponding to each procedure.
    Uses word-overlap matching with minimum 40% threshold.
    Content includes sub-headings (splits only at same or higher level).
    Returns dict: {procedure_name: section_content or None}."""

    # Step 1: Extract all headings with their level and position
    heading_pattern = re.compile(r'(?:^|\n)(#{1,4})[^\S\n]*([^\n]+)\n', re.MULTILINE)
    headings = []  # (level, full_heading_text, content_start_pos, match_obj)
    matches = list(heading_pattern.finditer(runbook))

    for hm in matches:
        level = len(hm.group(1))  # Number of # chars
        full_text = hm.group(1) + " " + hm.group(2).strip()
        headings.append((level, full_text, hm.end()))

    # Step 2: Build blocks — each heading's content extends until the next
    # heading of SAME or HIGHER level (fewer or equal #), INCLUDING sub-headings
    heading_blocks = []
    for i, (level, text, start) in enumerate(headings):
        end = len(runbook)
        for j in range(i + 1, len(headings)):
            if headings[j][0] <= level:  # Same or higher level heading
                end = headings[j][2] - len(headings[j][1]) - 2  # Before the next heading
                break
        content = runbook[start:end].strip()
        heading_blocks.append((text, content, level))

    # Step 3: Score each procedure against each heading by word overlap
    sections = {}
    used_headings = set()

    for proc_name in procedure_names:
        proc_words = _significant_words(proc_name)
        if not proc_words:
            sections[proc_name] = None
            continue

        best_idx = None
        best_score = 0
        best_overlap = 0

        for idx, (heading_text, content, level) in enumerate(heading_blocks):
            if idx in used_headings:
                continue
            heading_words = _significant_words(heading_text)
            if not heading_words:
                continue

            overlap = proc_words & heading_words
            overlap_count = len(overlap)
            score = overlap_count / len(proc_words)

            if score > best_score or (score == best_score and overlap_count > best_overlap):
                best_score = score
                best_overlap = overlap_count
                best_idx = idx

        if best_idx is not None and best_score >= 0.4 and best_overlap >= 1:
            used_headings.add(best_idx)
            sections[proc_name] = heading_blocks[best_idx][1]
        else:
            sections[proc_name] = None

    return sections


# ── Troubleshooting Count (reused from c07-setup-guide-writer) ────────────────
def count_troubleshooting_scenarios(runbook):
    ts_match = re.search(
        r'(?:##\s(?:Troubleshoot|Failure|Known Issues)\w*)(.*?)(?=\n##\s[^#]|\Z)',
        runbook, re.IGNORECASE | re.DOTALL
    )
    if not ts_match:
        return 0
    ts_content = ts_match.group(1)
    bullets = len(re.findall(r'^\s*[-*•]\s', ts_content, re.MULTILINE))
    numbered = len(re.findall(r'^\s*\d+[\.\)]\s', ts_content, re.MULTILINE))
    table_rows = len(re.findall(r'^\s*\|(?!\s*[-:])', ts_content, re.MULTILINE))
    if table_rows >= 2:
        table_rows -= 1
    # Also count ### subheadings as scenarios (common pattern: ### Failure 1 — ...)
    sub_headings = len(re.findall(r'^###\s', ts_content, re.MULTILINE))
    return max(bullets, numbered, table_rows, sub_headings)


# ── Full Validation ───────────────────────────────────────────────────────────
def validate_runbook_structure(runbook, procedure_names, procedure_types, audience):
    """Full deterministic validation. Returns list of issues."""
    issues = []
    runbook_lower = runbook.lower()

    # ── Quick reference card ──────────────────────────────────────────────
    has_qrc = any(phrase in runbook_lower for phrase in [
        "quick reference", "reference card", "cheat sheet", "summary card"])
    if not has_qrc:
        issues.append("Missing Quick Reference Card section")

    # ── Per-procedure validation ──────────────────────────────────────────
    sections = extract_procedure_sections(runbook, procedure_names)

    for proc_name in procedure_names:
        ptypes = procedure_types.get(proc_name, set())
        section = sections.get(proc_name)

        if section is None:
            issues.append(f"Procedure '{proc_name}' has no dedicated section")
            continue

        # Actionable steps
        action_count = count_actionable_steps(section)
        if action_count < 1:
            issues.append(
                f"Procedure '{proc_name}' has no actionable steps "
                f"(need code blocks, UI actions, or numbered instructions)")

        # Verification checkpoints
        verify_count = count_verification_checkpoints(section)
        if verify_count < 1:
            issues.append(
                f"Procedure '{proc_name}' has no verification checkpoint "
                f"(Expected:, Verify:, Confirm:, Check:)")

        # Decision trees for recovery and incident procedures
        needs_tree = bool(ptypes & DECISION_TREE_REQUIRED)
        if needs_tree:
            has_tree, tree_detail = has_real_decision_tree(section)
            if not has_tree:
                issues.append(
                    f"Procedure '{proc_name}' (type: {', '.join(sorted(ptypes))}) "
                    f"requires decision tree with real branching — {tree_detail}")

        # Rollback for recovery and modification procedures
        needs_rollback = bool(ptypes & ROLLBACK_REQUIRED)
        if needs_rollback:
            if not has_rollback_content(section):
                issues.append(
                    f"Procedure '{proc_name}' (type: {', '.join(sorted(ptypes))}) "
                    f"missing rollback/revert instructions or explicit 'no rollback' statement")

    # ── Escalation for on-call audience ───────────────────────────────────
    if audience == "on-call":
        if not has_escalation_content(runbook):
            issues.append(
                "On-call audience requires escalation instructions "
                "(who/when to escalate) — none found")

    # ── Troubleshooting scenario count ────────────────────────────────────
    ts_count = count_troubleshooting_scenarios(runbook)
    if ts_count < 3:
        issues.append(
            f"Troubleshooting section has {ts_count} scenarios (minimum 3 required)")

    # ── Banned fluff ──────────────────────────────────────────────────────
    for phrase in BANNED_FLUFF:
        if phrase in runbook_lower:
            issues.append(f"Runbook contains banned fluff: '{phrase}'")

    # ── Banned vague operational language ──────────────────────────────────
    for phrase in BANNED_VAGUE_OPS:
        if phrase in runbook_lower:
            issues.append(f"Runbook contains banned vague ops language: '{phrase}'")

    # ── Vague log references ──────────────────────────────────────────────
    vague_logs = check_vague_log_references(runbook)
    if vague_logs:
        issues.append(
            f"Vague log references without specifying which logs: "
            f"{vague_logs[:3]}")

    return issues


# ── Audience Configuration ────────────────────────────────────────────────────
AUDIENCE_PROFILES = {
    "operator": {
        "style": "Step-by-step with no assumed system knowledge. Heavy verification after every action.",
        "decision_trees": "Include with clear if/then formatting and explicit paths",
        "escalation": "Optional — include if failure scenarios warrant it",
    },
    "developer": {
        "style": "Concise commands. Assumes familiarity with the stack and CLI tools.",
        "decision_trees": "Include for recovery/incident. Can be more compact.",
        "escalation": "Optional",
    },
    "on-call": {
        "style": "Triage-first structure. Decision trees prioritized. Fastest path to resolution.",
        "decision_trees": "Required and prominent — first thing after symptom description",
        "escalation": "REQUIRED — every incident procedure must include who/when to escalate",
    },
}


# ── Step Handlers ─────────────────────────────────────────────────────────────

EXECUTION_ROLE = """You are a senior operations engineer who writes precise, testable operational
runbooks. You follow these absolute rules:

1. Every procedure has actionable steps (commands or UI actions) and verification checkpoints.
2. Recovery and incident procedures ALWAYS include decision trees with REAL branching:
   - At least one "If/When" condition with an "Otherwise/Else" alternative path
   - OR at least 2 distinct conditional blocks
   - NOT just a single "If X, do Y" without alternatives
3. Recovery and modification procedures ALWAYS include rollback instructions:
   - Specific rollback commands or steps
   - OR an explicit "No rollback applicable — [reason]" statement
4. You NEVER use vague operational language:
   - NEVER "check logs" without specifying WHICH logs (file path or log name)
   - NEVER "investigate further" without specifying WHAT to investigate
   - NEVER "troubleshoot accordingly" — always give specific steps
5. Quick reference card includes estimated completion time per procedure.
6. You use ONLY the information provided in the input."""


def step_1_local(inputs, context):
    """Parse system context and classify procedures."""
    system_desc = inputs.get("system_description", "").strip()
    if not system_desc or len(system_desc) < 30:
        return None, "system_description too short (minimum 30 characters)"

    procedures_raw = inputs.get("procedures", "").strip()
    if not procedures_raw:
        return None, "procedures list is required"

    procedure_names = [p.strip() for p in procedures_raw.split(",") if p.strip()]
    if len(procedure_names) < 1:
        return None, "At least 1 procedure required"

    failure_scenarios = inputs.get("failure_scenarios", "").strip()
    audience = inputs.get("audience", "operator").strip()
    if audience not in AUDIENCE_PROFILES:
        audience = "operator"

    # Classify each procedure
    procedure_types = {}
    procedures_needing_trees = []
    procedures_needing_rollback = []

    for name in procedure_names:
        ptypes = classify_procedure(name)
        procedure_types[name] = sorted(ptypes)
        if ptypes & DECISION_TREE_REQUIRED:
            procedures_needing_trees.append(name)
        if ptypes & ROLLBACK_REQUIRED:
            procedures_needing_rollback.append(name)

    audience_profile = AUDIENCE_PROFILES[audience]

    result = {
        "system_description": system_desc,
        "procedure_names": procedure_names,
        "procedure_types": {k: list(v) for k, v in procedure_types.items()},
        "procedures_needing_trees": procedures_needing_trees,
        "procedures_needing_rollback": procedures_needing_rollback,
        "failure_scenarios": failure_scenarios,
        "audience": audience,
        "audience_profile": audience_profile,
    }

    return {"output": result}, None


def step_2_llm(inputs, context):
    """Generate operational runbook with decision trees and checkpoints."""
    analysis = context.get("step_1_output", context.get("_resolved_input", {}))
    if not analysis or not isinstance(analysis, dict):
        return None, "No analysis from step 1"

    system_desc = analysis.get("system_description", "")
    procedure_names = analysis.get("procedure_names", [])
    procedure_types = analysis.get("procedure_types", {})
    trees_needed = analysis.get("procedures_needing_trees", [])
    rollback_needed = analysis.get("procedures_needing_rollback", [])
    failure_scenarios = analysis.get("failure_scenarios", "")
    audience = analysis.get("audience", "operator")
    audience_profile = analysis.get("audience_profile", {})

    proc_descriptions = []
    for name in procedure_names:
        ptypes = procedure_types.get(name, [])
        flags = []
        if name in trees_needed:
            flags.append("DECISION TREE REQUIRED")
        if name in rollback_needed:
            flags.append("ROLLBACK REQUIRED")
        proc_descriptions.append(
            f"  - {name} (types: {', '.join(ptypes)}) {' | '.join(flags)}")
    procedures_block = "\n".join(proc_descriptions)

    failure_block = ""
    if failure_scenarios:
        failure_block = f"\nKNOWN FAILURE SCENARIOS:\n{failure_scenarios}"

    escalation_rule = ""
    if audience == "on-call":
        escalation_rule = """
ESCALATION REQUIREMENT (on-call audience):
Every incident and recovery procedure MUST include escalation instructions:
- When to escalate (time threshold or severity condition)
- Who to escalate to (role or team name)
- How to escalate (communication channel)"""

    system = f"""{EXECUTION_ROLE}

SYSTEM: {system_desc}
AUDIENCE: {audience}
STYLE: {audience_profile.get('style', 'Step-by-step')}
DECISION TREES: {audience_profile.get('decision_trees', 'Include for recovery/incident')}
{escalation_rule}

PROCEDURES TO DOCUMENT:
{procedures_block}
{failure_block}

RUNBOOK STRUCTURE — produce ALL sections:

For EACH procedure, create a section with:
## [Procedure Name]

1. Numbered actionable steps (commands or UI actions)
2. Verification checkpoint after each major step (Expected:, Verify:, Confirm:)

For procedures marked DECISION TREE REQUIRED, include:
**Decision tree with REAL branching:**
- "If [condition] → [action]"
- "Otherwise / Else → [different action]"
- OR multiple "If" blocks for different scenarios
This must be real branching with at least two distinct paths, not a single conditional.

For procedures marked ROLLBACK REQUIRED, include:
**Rollback:**
- Specific commands or steps to revert the procedure
- OR: "**No rollback applicable** — [specific reason why]"

After all procedures:

## Troubleshooting

At least 3 failure scenarios with:
- Symptom
- Cause
- Fix (specific commands, not "investigate further")

## Quick Reference Card

Table or compact list summarizing all procedures:
| Procedure | Est. Time | Key Command/Action | When to Use |

ABSOLUTE RULES:
1. Use ONLY information from the input below.
2. NEVER write "check logs" without specifying which log file or path.
3. NEVER write "investigate further" — always say what to investigate and how.
4. NEVER use banned phrases: "leverage synergies", "best-in-class", etc.
5. Decision trees must have REAL branching — at least 2 paths.
6. Rollback instructions must be specific or explicitly marked not applicable.

Output ONLY the markdown runbook. No preamble, no explanation."""

    user = f"""SYSTEM DESCRIPTION:
{system_desc}

PROCEDURES TO DOCUMENT:
{', '.join(procedure_names)}

{"KNOWN FAILURE SCENARIOS:" + chr(10) + failure_scenarios if failure_scenarios else "No specific failure scenarios provided — infer common failures from system description."}

Generate the complete operational runbook."""

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
    procedure_names = analysis.get("procedure_names", [])
    procedure_types_raw = analysis.get("procedure_types", {})
    audience = analysis.get("audience", "operator")

    # Reconstruct sets from lists
    procedure_types = {k: set(v) for k, v in procedure_types_raw.items()}

    runbook = context.get("improved_runbook", context.get("generated_runbook",
              context.get("step_2_output", "")))
    if isinstance(runbook, dict):
        runbook = str(runbook)
    if not runbook:
        return None, "No runbook to evaluate"

    # ── Layer 1: Deterministic validation ─────────────────────────────────
    det_issues = validate_runbook_structure(
        runbook, procedure_names, procedure_types, audience)

    det_penalty = len(det_issues)
    structural_score = max(0, 10 - (det_penalty * 2))

    if structural_score <= 2:
        return {"output": {
            "quality_score": structural_score,
            "structural_score": structural_score,
            "decision_tree_quality": 0,
            "audience_fit": 0,
            "deterministic_issues": det_issues,
            "llm_feedback": "Too many structural issues — fix deterministic failures first",
            "feedback": f"STRUCTURAL ({len(det_issues)} issues): " + " | ".join(det_issues[:8]),
        }}, None

    # ── Layer 2: LLM quality evaluation ───────────────────────────────────
    system = f"""You are a strict operational runbook evaluator.

Score these dimensions (each 0-10):

- decision_tree_quality: Do decision trees have logical branching? Are the
  conditions specific and testable? Do the paths lead to different concrete
  actions? Are edge cases considered?

- audience_fit: Is the runbook appropriate for a {audience} audience?
  For operator: is every step explicit with no assumed knowledge?
  For developer: is it concise without being dangerously terse?
  For on-call: is triage-first structure followed with escalation paths?

Respond with JSON ONLY — no markdown, no backticks:
{{"decision_tree_quality": N, "audience_fit": N, "llm_feedback": "Specific notes"}}"""

    user = f"""GENERATED RUNBOOK:
{runbook[:5000]}

TARGET AUDIENCE: {audience}
PROCEDURES: {', '.join(procedure_names)}

Evaluate decision tree logic and audience fit."""

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    content, error = call_resolved(messages, context, max_tokens=1500)
    if error:
        content, error = call_openai(messages, max_tokens=1500)

    llm_scores = {"decision_tree_quality": 5, "audience_fit": 5, "llm_feedback": ""}
    if not error and content:
        try:
            cleaned = content.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
                cleaned = re.sub(r'\s*```$', '', cleaned)
            llm_scores = json.loads(cleaned)
        except (json.JSONDecodeError, TypeError):
            llm_scores["llm_feedback"] = content

    tree_quality = llm_scores.get("decision_tree_quality", 5)
    audience_fit = llm_scores.get("audience_fit", 5)
    quality_score = min(structural_score, tree_quality, audience_fit)

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
        "decision_tree_quality": tree_quality,
        "audience_fit": audience_fit,
        "deterministic_issues": det_issues,
        "llm_feedback": llm_fb,
        "feedback": " || ".join(feedback_parts) if feedback_parts else "All checks passed",
    }}, None


def step_4_llm(inputs, context):
    """Strengthen runbook based on critic feedback."""
    analysis = context.get("step_1_output", {})
    system_desc = analysis.get("system_description", "")
    procedure_names = analysis.get("procedure_names", [])
    trees_needed = analysis.get("procedures_needing_trees", [])
    rollback_needed = analysis.get("procedures_needing_rollback", [])
    audience = analysis.get("audience", "operator")
    audience_profile = analysis.get("audience_profile", {})

    runbook = context.get("improved_runbook", context.get("generated_runbook",
              context.get("step_2_output", "")))
    if isinstance(runbook, dict):
        runbook = str(runbook)

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

    escalation_note = ""
    if audience == "on-call":
        escalation_note = "\nOn-call audience: MUST include escalation instructions in every incident/recovery procedure."

    system = f"""{EXECUTION_ROLE}

You are improving an operational runbook based on critic feedback.
AUDIENCE: {audience}
STYLE: {audience_profile.get('style', 'Step-by-step')}
PROCEDURES NEEDING DECISION TREES: {', '.join(trees_needed) if trees_needed else 'none'}
PROCEDURES NEEDING ROLLBACK: {', '.join(rollback_needed) if rollback_needed else 'none'}
{escalation_note}
{det_section}

RULES:
1. Fix ALL structural issues listed above first.
2. Decision trees must have REAL branching: If + Otherwise/Else, or 2+ conditional blocks.
3. Rollback must be specific commands or explicit "No rollback applicable — [reason]".
4. Every procedure must have actionable steps AND verification checkpoints.
5. NEVER use "check logs" without specifying which logs.
6. NEVER use "investigate further" — say what to investigate and how.
7. Quick reference card must include estimated time per procedure.
8. Use ONLY information from the input.
9. Output ONLY the improved markdown runbook. No preamble."""

    user = f"""SYSTEM DESCRIPTION (reference):
{system_desc[:2000]}

CURRENT RUNBOOK:
{runbook}

CRITIC FEEDBACK: {feedback}

PROCEDURES: {', '.join(procedure_names)}

Fix all issues. Output ONLY the improved runbook."""

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
    for key in ("improved_runbook", "generated_runbook", "step_2_output"):
        v = context.get(key, "")
        if v and isinstance(v, str) and v.strip():
            return v
    return context.get("generated_runbook", "")


def step_5_write(inputs, context):
    """Full deterministic gate — hard-fail on critical violations."""
    best = _select_best_output(context)
    if isinstance(best, dict):
        best = str(best)
    if not best or not best.strip():
        return None, "No runbook to write"

    analysis = context.get("step_1_output", {})
    procedure_names = analysis.get("procedure_names", [])
    procedure_types_raw = analysis.get("procedure_types", {})
    audience = analysis.get("audience", "operator")
    procedure_types = {k: set(v) for k, v in procedure_types_raw.items()}

    issues = validate_runbook_structure(
        best, procedure_names, procedure_types, audience)

    # Hard-fail on critical issues only
    critical_keywords = [
        "no dedicated section", "no actionable steps",
        "no verification checkpoint", "requires decision tree",
        "missing rollback", "quick reference card",
        "escalation instructions",
    ]
    critical = [i for i in issues if any(k in i.lower() for k in critical_keywords)]

    if critical:
        summary = "; ".join(critical[:5])
        return None, f"RUNBOOK INTEGRITY FAILURE ({len(critical)} critical): {summary}"

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
