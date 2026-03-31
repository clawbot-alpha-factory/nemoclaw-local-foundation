#!/usr/bin/env python3
"""
NemoClaw Skill: c07-setup-guide-writer
Setup Guide Writer v1.0.0
F07 | C | dual-use | executor
Schema v2 | Runner v4.0+

Generates step-by-step setup guides with verification per step.
Deterministic validation: per-step verification mapping, prerequisite
table row count, troubleshooting scenario count, banned fluff, section
presence. Supports both CLI commands and UI action instructions.
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
    if p == "google": return call_google(messages, model=m or "gemini-2.5-flash", max_tokens=max_tokens)
    if p == "openai": return call_openai(messages, model=m or "gpt-5.4-mini", max_tokens=max_tokens)
    return call_anthropic(messages, model=m or "claude-sonnet-4-6", max_tokens=max_tokens)


# ── Banned Fluff (reused from e08) ────────────────────────────────────────────
BANNED_FLUFF = [
    "leverage synergies", "optimize positioning", "drive innovation forward",
    "best-in-class solution", "paradigm shift", "move the needle",
    "low-hanging fruit", "circle back", "synergistic approach",
    "thought leadership", "value proposition alignment",
]


# ── Deterministic Guide Validation ────────────────────────────────────────────

# Patterns that indicate a verification instruction within a step
VERIFY_PATTERNS = [
    re.compile(r'\*\*(?:Expected|Verify|Confirm|Check|Should\s+(?:show|output|return|print|display))\s*[:\*]', re.IGNORECASE),
    re.compile(r'(?:Expected|Verify|Confirm|Check|Should\s+(?:show|output|return|print|display))\s*:', re.IGNORECASE),
    re.compile(r'#\s*Expected\b', re.IGNORECASE),
]

# Patterns that indicate a CLI command (code block)
CODE_BLOCK_PATTERN = re.compile(r'```(?:\w+)?\s*\n.*?\n\s*```', re.DOTALL)

# Patterns that indicate a UI action instruction
UI_ACTION_PATTERNS = [
    re.compile(r'(?:open|launch|navigate\s+to|go\s+to|click|select|check\s+the|toggle|enable|disable|drag|set)\s', re.IGNORECASE),
    re.compile(r'→|➜|→|>>|⟶', re.IGNORECASE),  # Arrow navigation indicators
    re.compile(r'\*\*UI\s*(?:Action|Step)\*\*', re.IGNORECASE),
    re.compile(r'(?:preferences|settings|menu|dialog|dropdown|checkbox|slider|tab)\b', re.IGNORECASE),
]

# Required section keywords (at least one of each group must appear)
REQUIRED_SECTION_GROUPS = [
    {"label": "Prerequisites/Requirements", "patterns": ["prerequisit", "requirement"]},
    {"label": "Numbered setup steps", "patterns": []},  # Checked separately
    {"label": "Troubleshooting", "patterns": ["troubleshoot"]},
    {"label": "Post-Setup/Checklist", "patterns": ["post-setup", "checklist", "verification checklist", "post setup"]},
]


def extract_numbered_steps(guide):
    """Extract numbered setup steps with their content blocks.
    Returns list of (step_number, step_content) tuples."""
    steps = []
    # Match patterns like "## Step 1 —", "### 1.", "## 1 —", "**Step 1:**"
    step_pattern = re.compile(
        r'(?:^|\n)(?:#{1,4}\s*)?(?:\*\*)?(?:Step\s+)?(\d+)[\.\):\s—–-]+(.+?)(?=\n(?:#{1,4}\s*)?(?:\*\*)?(?:Step\s+)?\d+[\.\):\s—–-]|\n##\s|\Z)',
        re.DOTALL | re.IGNORECASE
    )
    for match in step_pattern.finditer(guide):
        num = int(match.group(1))
        content = match.group(2).strip()
        steps.append((num, content))

    # Fallback: try simpler pattern if nothing matched
    if not steps:
        simple_pattern = re.compile(
            r'(?:^|\n)\s*(\d+)\.\s+(.+?)(?=\n\s*\d+\.|\n##|\Z)',
            re.DOTALL
        )
        for match in simple_pattern.finditer(guide):
            num = int(match.group(1))
            content = match.group(2).strip()
            steps.append((num, content))

    return steps


def step_has_command_or_ui_action(step_content):
    """Check if a step contains either a code block OR a UI action instruction.
    Returns (has_action, action_type) where action_type is 'cli', 'ui', or None."""
    # Check for code block
    if CODE_BLOCK_PATTERN.search(step_content):
        return True, "cli"

    # Check for UI action patterns (need at least 2 indicators for confidence)
    ui_hits = sum(1 for pat in UI_ACTION_PATTERNS if pat.search(step_content))
    if ui_hits >= 1:
        return True, "ui"

    return False, None


def step_has_verification(step_content):
    """Check if a step contains a verification instruction."""
    for pat in VERIFY_PATTERNS:
        if pat.search(step_content):
            return True
    # Also check for "Expected:" inside code blocks (common pattern)
    if re.search(r'#\s*(?:Expected|Output|Should)', step_content, re.IGNORECASE):
        return True
    return False


def count_troubleshooting_scenarios(guide):
    """Count distinct troubleshooting scenarios under the Troubleshooting heading.
    Counts bullet points, numbered items, or table rows."""
    # Find the troubleshooting section
    ts_match = re.search(
        r'(?:##\sTroubleshoot\w*)(.*?)(?=\n##\s[^#]|\Z)',
        guide, re.IGNORECASE | re.DOTALL
    )
    if not ts_match:
        return 0

    ts_content = ts_match.group(1)

    # Count bullet points
    bullets = len(re.findall(r'^\s*[-*•]\s', ts_content, re.MULTILINE))

    # Count numbered items
    numbered = len(re.findall(r'^\s*\d+[\.\)]\s', ts_content, re.MULTILINE))

    # Count table rows (excluding header and separator)
    table_rows = len(re.findall(r'^\s*\|(?!\s*-)', ts_content, re.MULTILINE))
    if table_rows >= 2:
        table_rows -= 1  # Subtract header row

    return max(bullets, numbered, table_rows)


def count_prerequisite_rows(guide):
    """Count rows in the prerequisites/requirements table."""
    # Find prerequisites section
    prereq_match = re.search(
        r'(?:##\s(?:Prerequisit|Requirement)\w*)(.*?)(?=\n##\s[^#]|\Z)',
        guide, re.IGNORECASE | re.DOTALL
    )
    if not prereq_match:
        return 0

    prereq_content = prereq_match.group(1)

    # Count table rows (excluding header and separator rows)
    all_rows = re.findall(r'^\s*\|.+\|', prereq_content, re.MULTILINE)
    # Filter out separator rows (|---|---|)
    data_rows = [r for r in all_rows if not re.match(r'^\s*\|[-\s:|]+\|$', r)]
    # Subtract header row
    if data_rows:
        return max(0, len(data_rows) - 1)

    # Fallback: count bullet items in prereq section
    bullets = len(re.findall(r'^\s*[-*•]\s', prereq_content, re.MULTILINE))
    return bullets


def validate_guide_structure(guide):
    """Full deterministic validation. Returns list of issues."""
    issues = []
    guide_lower = guide.lower()

    # ── Required sections ─────────────────────────────────────────────────
    for group in REQUIRED_SECTION_GROUPS:
        if group["patterns"]:
            found = any(p in guide_lower for p in group["patterns"])
            if not found:
                issues.append(f"Missing required section: {group['label']}")

    # ── Prerequisites table row count ─────────────────────────────────────
    prereq_rows = count_prerequisite_rows(guide)
    if prereq_rows < 2:
        issues.append(
            f"Prerequisites table has {prereq_rows} data rows (minimum 2 required)")

    # ── Per-step verification mapping ─────────────────────────────────────
    steps = extract_numbered_steps(guide)
    if len(steps) < 2:
        issues.append(f"Only {len(steps)} numbered steps found (minimum 2 expected)")
    else:
        for num, content in steps:
            # Check: command or UI action present
            has_action, action_type = step_has_command_or_ui_action(content)
            if not has_action:
                issues.append(
                    f"Step {num} has no CLI code block and no UI action instruction")

            # Check: verification present
            has_verify = step_has_verification(content)
            if not has_verify:
                issues.append(
                    f"Step {num} missing verification instruction "
                    f"(Expected:, Verify:, Confirm:, or equivalent)")

    # ── Troubleshooting scenario count ────────────────────────────────────
    ts_count = count_troubleshooting_scenarios(guide)
    if ts_count < 3:
        issues.append(
            f"Troubleshooting section has {ts_count} scenarios (minimum 3 required)")

    # ── Banned fluff ──────────────────────────────────────────────────────
    for phrase in BANNED_FLUFF:
        if phrase in guide_lower:
            issues.append(f"Guide contains banned fluff phrase: '{phrase}'")

    return issues


# ── Audience Configuration ────────────────────────────────────────────────────
AUDIENCE_PROFILES = {
    "developer": {
        "vocabulary": "Technical — use standard CLI terminology, assume shell familiarity",
        "explanation_depth": "Concise — command + expected output is sufficient",
        "gui_alternatives": "Not required unless the step is inherently GUI-only",
    },
    "devops": {
        "vocabulary": "Technical — use infrastructure and ops terminology freely",
        "explanation_depth": "Moderate — include flags and options explanation",
        "gui_alternatives": "Not required — assume CLI preference",
    },
    "non-technical": {
        "vocabulary": "Plain language — avoid jargon, explain technical terms on first use",
        "explanation_depth": "Detailed — explain what each command does and why",
        "gui_alternatives": "Required — always mention GUI alternative for CLI steps where one exists",
    },
}


# ── Step Handlers ─────────────────────────────────────────────────────────────

EXECUTION_ROLE = """You are a senior technical documentation engineer who writes precise,
testable setup guides. Every step you write includes either a CLI command
with expected output or a clearly marked UI action with a verification
instruction. You never assume the reader has prior context beyond what is
provided in the input. You never reference external documentation without
specifying what it contains. You adapt vocabulary complexity and explanation
depth to the target audience level."""


def step_1_local(inputs, context):
    """Parse system context and plan guide structure."""
    system_desc = inputs.get("system_description", "").strip()
    if not system_desc or len(system_desc) < 30:
        return None, "system_description too short (minimum 30 characters)"

    target_env = inputs.get("target_environment", "").strip()
    if not target_env or len(target_env) < 10:
        return None, "target_environment too short (minimum 10 characters)"

    prerequisites = inputs.get("prerequisites", "").strip()
    steps_hint = inputs.get("setup_steps_hint", "").strip()
    audience = inputs.get("audience", "developer").strip()
    if audience not in AUDIENCE_PROFILES:
        audience = "developer"

    # Extract likely components from system description
    components = []
    component_markers = [
        "docker", "python", "node", "npm", "git", "homebrew", "brew",
        "pip", "venv", "virtualenv", "api key", "database", "postgres",
        "redis", "nginx", "terraform", "kubernetes", "k8s", "helm",
        "aws", "gcp", "azure", "supabase", "vercel", "firebase",
    ]
    desc_lower = system_desc.lower() + " " + target_env.lower()
    for marker in component_markers:
        if marker in desc_lower:
            components.append(marker)

    # Detect prerequisite gaps
    prereq_lower = prerequisites.lower() if prerequisites else ""
    detected_needs = []
    if "docker" in desc_lower and "docker" not in prereq_lower:
        detected_needs.append("Docker — mentioned in system but not in prerequisites")
    if "python" in desc_lower and "python" not in prereq_lower:
        detected_needs.append("Python — mentioned in system but not in prerequisites")
    if "api key" in desc_lower or "api_key" in desc_lower:
        if "key" not in prereq_lower:
            detected_needs.append("API keys — referenced in system but not listed in prerequisites")

    audience_profile = AUDIENCE_PROFILES[audience]

    result = {
        "system_description": system_desc,
        "target_environment": target_env,
        "prerequisites": prerequisites,
        "setup_steps_hint": steps_hint,
        "audience": audience,
        "audience_profile": audience_profile,
        "detected_components": components,
        "prerequisite_gaps": detected_needs,
        "word_count": len(system_desc.split()),
    }

    return {"output": result}, None


def step_2_llm(inputs, context):
    """Generate complete setup guide with verification commands."""
    analysis = context.get("step_1_output", context.get("_resolved_input", {}))
    if not analysis or not isinstance(analysis, dict):
        return None, "No analysis from step 1"

    system_desc = analysis.get("system_description", "")
    target_env = analysis.get("target_environment", "")
    prerequisites = analysis.get("prerequisites", "")
    steps_hint = analysis.get("setup_steps_hint", "")
    audience = analysis.get("audience", "developer")
    audience_profile = analysis.get("audience_profile", {})
    prereq_gaps = analysis.get("prerequisite_gaps", [])

    gap_note = ""
    if prereq_gaps:
        gap_note = "\nDETECTED PREREQUISITE GAPS (include these in the Prerequisites section):\n"
        gap_note += "\n".join(f"  - {g}" for g in prereq_gaps)

    steps_instruction = ""
    if steps_hint:
        steps_instruction = f"\nSUGGESTED STEP ORDER (use as guide, add detail):\n{steps_hint}"

    system = f"""{EXECUTION_ROLE}

TARGET ENVIRONMENT: {target_env}
AUDIENCE: {audience}
VOCABULARY: {audience_profile.get('vocabulary', 'Technical')}
EXPLANATION DEPTH: {audience_profile.get('explanation_depth', 'Concise')}
GUI ALTERNATIVES: {audience_profile.get('gui_alternatives', 'Not required')}
{gap_note}
{steps_instruction}

GUIDE STRUCTURE — produce ALL of these sections as markdown headings:

## Prerequisites

A table with columns: Requirement | Version | Check Command | Install
Minimum 2 rows. Include every dependency needed before starting.

## Step 1 — [Step Title]

Each numbered step MUST contain EITHER:
- A CLI code block (```bash\\n command \\n```) with the command to run
- OR a clearly marked **UI Action:** instruction for GUI-only steps
  (e.g., "**UI Action:** Open Docker Desktop → Preferences → Resources → set memory to 8GB")

Each numbered step MUST contain a verification instruction:
- After a CLI command: show expected output (e.g., "**Expected:** `Docker version 29.x.x`")
- After a UI action: describe how to verify (e.g., "**Verify:** The Resources panel shows 8.00 GB allocated")

## Environment Notes

Important runtime details: what is gitignored, where logs go, version pins, etc.

## Troubleshooting

At least 3 distinct failure scenarios. For each:
- Symptom (what the user sees)
- Cause (why it happens)
- Fix (exact command or action to resolve)

Format as a table or bullet list with clear structure.

## Post-Setup Checklist

Checkbox-style list confirming the setup is complete:
- [ ] [verification item]

ABSOLUTE RULES:
1. Use ONLY the information provided below. Do NOT reference external docs
   without specifying what they contain.
2. Do NOT fabricate commands, paths, or version numbers not derivable from input.
3. Do NOT use banned phrases: "leverage synergies", "best-in-class",
   "paradigm shift", "move the needle", "low-hanging fruit".
4. Every step must be independently verifiable — no "trust me, it worked" steps.
5. Adapt vocabulary and explanation depth to the {audience} audience level.
{"6. For non-technical audience: always mention GUI alternatives for CLI steps where they exist." if audience == "non-technical" else ""}

Output ONLY the markdown guide. No preamble, no explanation."""

    user = f"""SYSTEM DESCRIPTION:
{system_desc}

TARGET ENVIRONMENT:
{target_env}

{"KNOWN PREREQUISITES:" + chr(10) + prerequisites if prerequisites else "No prerequisites provided — infer from system description."}

Generate the complete setup guide."""

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
    audience = analysis.get("audience", "developer")

    guide = context.get("improved_guide", context.get("generated_guide",
            context.get("step_2_output", "")))
    if isinstance(guide, dict):
        guide = str(guide)
    if not guide:
        return None, "No guide to evaluate"

    # ── Layer 1: Deterministic validation ─────────────────────────────────
    det_issues = validate_guide_structure(guide)

    det_penalty = len(det_issues)
    structural_score = max(0, 10 - (det_penalty * 2))

    if structural_score <= 2:
        return {"output": {
            "quality_score": structural_score,
            "structural_score": structural_score,
            "command_accuracy": 0,
            "audience_fit": 0,
            "deterministic_issues": det_issues,
            "llm_feedback": "Too many structural issues — fix deterministic failures first",
            "feedback": f"STRUCTURAL ({len(det_issues)} issues): " + " | ".join(det_issues[:8]),
        }}, None

    # ── Layer 2: LLM quality evaluation ───────────────────────────────────
    system = f"""You are a strict setup guide evaluator.

Score these dimensions (each 0-10):

- command_accuracy: Are CLI commands plausible and correctly formatted?
  Are paths, flags, and arguments reasonable? Are version numbers consistent?
  Do verification commands actually test what the step claims to accomplish?

- audience_fit: Is the guide appropriate for a {audience} audience?
  Vocabulary complexity, explanation depth, GUI alternatives mentioned
  where appropriate? Would the target reader understand every step?

Respond with JSON ONLY — no markdown, no backticks:
{{"command_accuracy": N, "audience_fit": N, "llm_feedback": "Specific notes"}}"""

    user = f"""GENERATED SETUP GUIDE:
{guide[:5000]}

TARGET AUDIENCE: {audience}

Evaluate command accuracy and audience fit."""

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    content, error = call_resolved(messages, context, max_tokens=1500)
    if error:
        content, error = call_openai(messages, model="gpt-5.4-mini", max_tokens=1500)

    llm_scores = {"command_accuracy": 5, "audience_fit": 5, "llm_feedback": ""}
    if not error and content:
        try:
            cleaned = content.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
                cleaned = re.sub(r'\s*```$', '', cleaned)
            llm_scores = json.loads(cleaned)
        except (json.JSONDecodeError, TypeError):
            llm_scores["llm_feedback"] = content

    cmd_accuracy = llm_scores.get("command_accuracy", 5)
    audience_fit = llm_scores.get("audience_fit", 5)
    quality_score = min(structural_score, cmd_accuracy, audience_fit)

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
        "command_accuracy": cmd_accuracy,
        "audience_fit": audience_fit,
        "deterministic_issues": det_issues,
        "llm_feedback": llm_fb,
        "feedback": " || ".join(feedback_parts) if feedback_parts else "All checks passed",
    }}, None


def step_4_llm(inputs, context):
    """Strengthen guide based on critic feedback."""
    analysis = context.get("step_1_output", {})
    system_desc = analysis.get("system_description", "")
    target_env = analysis.get("target_environment", "")
    audience = analysis.get("audience", "developer")
    audience_profile = analysis.get("audience_profile", {})

    guide = context.get("improved_guide", context.get("generated_guide",
            context.get("step_2_output", "")))
    if isinstance(guide, dict):
        guide = str(guide)

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

You are improving a setup guide based on critic feedback.
TARGET AUDIENCE: {audience}
VOCABULARY: {audience_profile.get('vocabulary', 'Technical')}
EXPLANATION DEPTH: {audience_profile.get('explanation_depth', 'Concise')}
GUI ALTERNATIVES: {audience_profile.get('gui_alternatives', 'Not required')}
{det_section}

RULES:
1. Fix ALL structural issues listed above first.
2. Every numbered step MUST have either a CLI code block or a **UI Action:** instruction.
3. Every numbered step MUST have a verification (Expected:, Verify:, Confirm:).
4. Troubleshooting must have at least 3 distinct failure scenarios.
5. Prerequisites table must have at least 2 data rows.
6. Use ONLY information from the input — do not fabricate.
7. Do NOT use banned fluff phrases.
8. Output ONLY the improved markdown guide. No preamble."""

    user = f"""SYSTEM DESCRIPTION (reference):
{system_desc[:2000]}

TARGET ENVIRONMENT:
{target_env}

CURRENT GUIDE:
{guide}

CRITIC FEEDBACK: {feedback}

Fix all issues. Output ONLY the improved guide."""

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
    for key in ("improved_guide", "generated_guide", "step_2_output"):
        v = context.get(key, "")
        if v and isinstance(v, str) and v.strip():
            return v
    return context.get("generated_guide", "")


def step_5_write(inputs, context):
    """Full deterministic gate — hard-fail on structural violations."""
    best = _select_best_output(context)
    if isinstance(best, dict):
        best = str(best)
    if not best or not best.strip():
        return None, "No guide to write"

    issues = validate_guide_structure(best)

    # Hard-fail on critical structural issues
    critical = [i for i in issues if any(k in i.lower() for k in [
        "missing required section", "prerequisite", "troubleshooting",
        "missing verification", "no cli code block and no ui action",
    ])]

    if critical:
        summary = "; ".join(critical[:5])
        return None, f"GUIDE INTEGRITY FAILURE ({len(critical)} critical): {summary}"

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
