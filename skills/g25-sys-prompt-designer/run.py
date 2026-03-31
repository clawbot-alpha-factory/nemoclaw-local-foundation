#!/usr/bin/env python3
"""
NemoClaw Skill: g25-sys-prompt-designer
System Prompt Designer v1.0.0
F25 | G | internal | executor
Schema v2 | Runner v4.0+

Generates structured system prompts for skill LLM steps following the F35
reference pattern. Accepts either skill_yaml or llm_steps JSON input.
Deterministic validation: banned phrases, required structure, capability
hallucination detection, output format enforcement, critic prompt checks.
"""

import argparse
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


# ── Banned Phrases & Validation Constants ─────────────────────────────────────
BANNED_VAGUE_PHRASES = [
    "be helpful", "do your best", "try to", "if possible",
    "feel free to", "you may want to", "consider maybe",
    "as appropriate", "when relevant", "if needed",
    "as you see fit", "use your judgment", "be creative",
    "do a good job", "make it nice",
]

BANNED_CAPABILITY_HALLUCINATIONS = [
    "browse the web", "search the web", "access the internet",
    "access the database", "query the database",
    "remember from previous", "recall our earlier",
    "use tools", "call functions", "execute code",
    "access files on disk", "read from the filesystem",
    "send emails", "make api calls",
]

# Required structural elements in each prompt
REQUIRED_PROMPT_ELEMENTS = [
    "role",       # Who the LLM is
    "task",       # What it must do
    "constraint", # At least one explicit rule
    "output",     # Output format instruction
]


def strip_json_fences(text):
    """Strip markdown code fences from JSON output."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r'^```(?:json)?\s*\n?', '', text)
        text = re.sub(r'\n?\s*```\s*$', '', text)
    return text.strip()


# ── Deterministic Prompt Validation ───────────────────────────────────────────
def deterministic_validate_prompts(prompts_json, expected_step_ids, output_format,
                                   has_critic_steps):
    """Validate generated prompts against all deterministic rules.
    Returns (issues: list[str], parsed: dict|None, parse_ok: bool)."""
    issues = []

    # Layer 1: JSON parse
    cleaned = strip_json_fences(prompts_json)
    try:
        parsed = json.loads(cleaned)
    except (json.JSONDecodeError, TypeError) as e:
        return [f"JSON PARSE FAILURE: {str(e)[:200]}"], None, False

    if not isinstance(parsed, dict):
        return [f"Expected JSON object, got {type(parsed).__name__}"], None, False

    # Layer 2: Step coverage
    for sid in expected_step_ids:
        if sid not in parsed:
            issues.append(f"Missing prompt for step '{sid}'")

    # Layer 3: Per-prompt validation
    for sid, prompt in parsed.items():
        if not isinstance(prompt, str):
            issues.append(f"Prompt for '{sid}' is not a string — got {type(prompt).__name__}")
            continue

        # Minimum length
        if len(prompt) < 100:
            issues.append(f"Prompt for '{sid}' too short: {len(prompt)} chars (min 100)")

        # Banned vague phrases
        prompt_lower = prompt.lower()
        for phrase in BANNED_VAGUE_PHRASES:
            if phrase in prompt_lower:
                issues.append(f"Prompt for '{sid}' contains banned phrase: '{phrase}'")

        # Banned capability hallucinations
        for hallucination in BANNED_CAPABILITY_HALLUCINATIONS:
            if hallucination in prompt_lower:
                issues.append(
                    f"Prompt for '{sid}' claims unavailable capability: '{hallucination}'")

        # Required structural elements (heuristic check)
        has_role = any(marker in prompt_lower for marker in [
            "you are", "your role", "your job", "you serve as",
            "act as", "your expertise"])
        has_task = any(marker in prompt_lower for marker in [
            "your task", "you must", "you will", "produce", "generate",
            "evaluate", "score", "analyze", "create", "write"])
        has_constraint = any(marker in prompt_lower for marker in [
            "must", "never", "always", "do not", "forbidden",
            "required", "critical", "rule", "constraint"])
        has_output = any(marker in prompt_lower for marker in [
            "output", "respond with", "return", "format",
            "json", "yaml", "markdown", "produce"])

        if not has_role:
            issues.append(f"Prompt for '{sid}' missing role definition")
        if not has_task:
            issues.append(f"Prompt for '{sid}' missing task description")
        if not has_constraint:
            issues.append(f"Prompt for '{sid}' missing explicit constraints")
        if not has_output:
            issues.append(f"Prompt for '{sid}' missing output format instruction")

    # Layer 4: Output format positive checks
    for sid, prompt in parsed.items():
        if not isinstance(prompt, str):
            continue
        prompt_lower = prompt.lower()
        if output_format == "structured_json":
            if "json" not in prompt_lower:
                issues.append(
                    f"Prompt for '{sid}': output_format is structured_json but "
                    f"prompt does not mention 'JSON'")
        elif output_format == "yaml":
            if "yaml" not in prompt_lower:
                issues.append(
                    f"Prompt for '{sid}': output_format is yaml but "
                    f"prompt does not mention 'YAML'")
        elif output_format == "markdown_sections":
            if not any(m in prompt_lower for m in ["heading", "section", "##", "markdown"]):
                issues.append(
                    f"Prompt for '{sid}': output_format is markdown_sections but "
                    f"prompt does not define headers or sections")

    # Layer 5: Critic step prompt enforcement
    for sid in has_critic_steps:
        prompt = parsed.get(sid, "")
        if not isinstance(prompt, str):
            continue
        prompt_lower = prompt.lower()
        if "quality_score" not in prompt_lower:
            issues.append(
                f"Critic prompt for '{sid}' must instruct JSON with 'quality_score'")
        if "feedback" not in prompt_lower:
            issues.append(
                f"Critic prompt for '{sid}' must instruct 'feedback' field")
        if "json" not in prompt_lower:
            issues.append(
                f"Critic prompt for '{sid}' must instruct JSON output format")

    return issues, parsed, True


# ── Step Handlers ─────────────────────────────────────────────────────────────

def step_1_local(inputs, context):
    """Parse inputs and build prompt generation plan."""
    skill_purpose = inputs.get("skill_purpose", "").strip()
    skill_id = inputs.get("skill_id", "").strip()
    tag = inputs.get("tag", "internal").strip()
    skill_yaml_text = inputs.get("skill_yaml", "").strip()
    llm_steps_text = inputs.get("llm_steps", "").strip()
    execution_role = inputs.get("execution_role", "").strip()
    domain_constraints = inputs.get("domain_constraints", "").strip()
    output_format = inputs.get("output_format_preference", "prose").strip()

    if not skill_purpose or len(skill_purpose) < 20:
        return None, "skill_purpose required (min 20 chars)"
    if not skill_id:
        return None, "skill_id required"
    if tag not in ("internal", "customer-facing", "dual-use"):
        return None, f"Invalid tag: '{tag}'"

    llm_steps = []

    # Path 1: Extract from skill_yaml
    if skill_yaml_text and not llm_steps_text:
        try:
            parsed_yaml = yaml.safe_load(skill_yaml_text)
        except yaml.YAMLError as e:
            return None, f"skill_yaml parse failed: {str(e)[:200]}"

        if not isinstance(parsed_yaml, dict):
            return None, "skill_yaml did not produce a dict"

        for step in parsed_yaml.get("steps", []):
            if not isinstance(step, dict):
                continue
            stype = step.get("step_type", "local")
            if stype in ("llm", "critic"):
                llm_steps.append({
                    "step_id": step.get("id", ""),
                    "step_name": step.get("name", ""),
                    "step_description": step.get("description", ""),
                    "step_type": stype,
                    "input_description": step.get("input_source", ""),
                    "output_description": step.get("output_key", ""),
                    "task_class": step.get("task_class", ""),
                })

        if not llm_steps:
            return None, "No LLM/critic steps found in skill_yaml"

        # Also extract execution_role from YAML if not provided
        if not execution_role:
            execution_role = parsed_yaml.get("execution_role", "")

    # Path 2: Parse llm_steps JSON
    elif llm_steps_text:
        try:
            llm_steps = json.loads(llm_steps_text)
        except (json.JSONDecodeError, TypeError) as e:
            return None, f"llm_steps JSON parse failed: {str(e)[:200]}"

        if not isinstance(llm_steps, list) or len(llm_steps) == 0:
            return None, "llm_steps must be a non-empty JSON array"

        # Validate required fields
        for i, step in enumerate(llm_steps):
            if not isinstance(step, dict):
                return None, f"llm_steps[{i}] is not a dict"
            for field in ("step_id", "step_name", "step_type"):
                if not step.get(field):
                    return None, f"llm_steps[{i}] missing required field: '{field}'"
            if step.get("step_type") not in ("llm", "critic"):
                return None, (
                    f"llm_steps[{i}] step_type '{step.get('step_type')}' "
                    f"must be 'llm' or 'critic'")
    else:
        return None, "Must provide either skill_yaml or llm_steps"

    # Classify prompt needs
    step_plan = []
    critic_step_ids = []
    for step in llm_steps:
        sid = step["step_id"]
        stype = step.get("step_type", "llm")
        if stype == "critic":
            prompt_type = "evaluation"
            critic_step_ids.append(sid)
        else:
            prompt_type = "generation"

        step_plan.append({
            "step_id": sid,
            "step_name": step.get("step_name", ""),
            "step_description": step.get("step_description", ""),
            "step_type": stype,
            "prompt_type": prompt_type,
            "input_description": step.get("input_description", ""),
            "output_description": step.get("output_description", ""),
            "task_class": step.get("task_class", ""),
        })

    quality_bar = {
        "internal": "functional and correct",
        "customer-facing": "polished, professional, and high-quality — represents the company",
        "dual-use": "high quality for both internal and external use",
    }.get(tag, "functional and correct")

    result = {
        "skill_purpose": skill_purpose,
        "skill_id": skill_id,
        "tag": tag,
        "quality_bar": quality_bar,
        "execution_role": execution_role,
        "domain_constraints": domain_constraints,
        "output_format": output_format,
        "step_plan": step_plan,
        "expected_step_ids": [s["step_id"] for s in step_plan],
        "critic_step_ids": critic_step_ids,
    }

    return {"output": result}, None


PROMPT_REFERENCE = """
=== SYSTEM PROMPT REFERENCE ARCHITECTURE (from F35 Tone Calibrator) ===

Every system prompt MUST have these four sections:

1. ROLE DEFINITION — Who the LLM is:
   "You are a [specific expert role] with expertise in [specific domains]."
   NOT: "You are a helpful assistant." / "Be helpful."

2. TASK DESCRIPTION — What it must do:
   "Your task is to [specific action] the [specific input] to produce [specific output]."
   Must explicitly reference the skill purpose and this step's specific objective.
   NOT: "Do your best to process the input."

3. EXPLICIT CONSTRAINTS — Hard rules:
   "You MUST [rule]. You MUST NEVER [forbidden behavior]."
   At least 3 constraints per prompt. Be specific.
   NOT: "Try to follow the rules if possible."

4. OUTPUT FORMAT — What to produce:
   "Output ONLY [format]. No preamble. No explanation."
   Or: "Respond with JSON ONLY: {specific schema}"
   NOT: "Return your response as appropriate."

=== BANNED PHRASES — Never include these ===
"be helpful"         → Replace with: specific role ("You are a competitive intelligence analyst")
"do your best"       → Replace with: definitive instruction ("Produce a complete analysis")
"try to"             → Replace with: direct command ("Extract all numeric claims exactly")
"if possible"        → Replace with: explicit condition ("If fewer than 3 data points, state this")
"feel free to"       → Replace with: direct instruction ("Include examples for each finding")
"you may want to"    → Replace with: requirement ("You must include severity ratings")
"consider maybe"     → Replace with: clear decision ("Categorize each item as high/medium/low")
"as appropriate"     → Replace with: specific trigger ("When input contains bullets, preserve structure")
"when relevant"      → Replace with: always or explicit condition ("Always include source attribution")
"if needed"          → Replace with: specific check ("If the text exceeds 500 words, summarize first")

=== BANNED CAPABILITY CLAIMS — Never claim these ===
"browse the web", "search the web", "access the internet"
"access the database", "query the database"
"remember from previous", "recall our earlier"
"use tools", "call functions", "execute code"
"access files on disk", "send emails", "make api calls"
(Unless the skill explicitly has these capabilities)

=== CRITIC PROMPT REQUIREMENTS ===
Every critic step prompt MUST:
- Define scoring dimensions by name (e.g., tone_accuracy, meaning_preservation)
- Instruct JSON output format with "quality_score" field
- Include "feedback" field for actionable improvement notes
- Define what score 0-10 means for each dimension

=== OUTPUT FORMAT ENFORCEMENT ===
- If output_format is "structured_json": prompt MUST mention "JSON" and show expected schema
- If output_format is "yaml": prompt MUST mention "YAML"
- If output_format is "markdown_sections": prompt MUST define section headers
- If output_format is "prose": prompt must specify "Output ONLY the text"
"""


def step_2_llm(inputs, context):
    """Generate structured system prompts for all LLM steps."""
    plan = context.get("step_1_output", context.get("_resolved_input", {}))
    if not plan or not isinstance(plan, dict):
        return None, "No generation plan from step 1"

    skill_purpose = plan.get("skill_purpose", "")
    skill_id = plan.get("skill_id", "")
    tag = plan.get("tag", "internal")
    quality_bar = plan.get("quality_bar", "")
    execution_role = plan.get("execution_role", "")
    domain_constraints = plan.get("domain_constraints", "")
    output_format = plan.get("output_format", "prose")
    step_plan = plan.get("step_plan", [])

    step_descriptions = []
    for sp in step_plan:
        step_descriptions.append(
            f"  {sp['step_id']} ({sp['step_type']}): {sp['step_name']}\n"
            f"    Description: {sp['step_description'][:300]}\n"
            f"    Prompt type: {sp['prompt_type']}\n"
            f"    Input: {sp.get('input_description', 'previous step')}\n"
            f"    Output: {sp.get('output_description', 'text')}")
    steps_block = "\n".join(step_descriptions)

    role_instruction = ""
    if execution_role:
        role_instruction = f"\nFOUNDATION ROLE (use as starting point for all prompts):\n{execution_role}"

    constraint_instruction = ""
    if domain_constraints:
        constraint_instruction = f"\nDOMAIN CONSTRAINTS (must appear in relevant prompts):\n{domain_constraints}"

    system = f"""{PROMPT_REFERENCE}

Generate system prompts for the skill described below.

SKILL: {skill_id}
PURPOSE: {skill_purpose}
TAG: {tag}
QUALITY BAR: {quality_bar}
OUTPUT FORMAT PREFERENCE: {output_format}
{role_instruction}
{constraint_instruction}

STEPS REQUIRING PROMPTS:
{steps_block}

GENERATION RULES:
1. Output a JSON object where each key is a step_id and each value is the
   complete system prompt string for that step.
2. Every prompt must have all 4 required sections: role, task, constraints, output format.
3. Every prompt must explicitly reference the skill purpose AND the step-specific objective.
4. Critic prompts must instruct JSON output with quality_score, named dimensions, and feedback.
5. Never use any banned phrases or claim unavailable capabilities.
6. {'Customer-facing quality: prompts must enforce polished, professional output.' if tag == 'customer-facing' else ''}
7. Output ONLY the JSON object. No markdown fences. No explanation. No preamble.

Example output structure:
{{"step_2": "You are a ... Your task is to ... RULES: 1. You MUST ... Output ONLY ...", "step_3": "..."}}"""

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Generate prompts for all {len(step_plan)} LLM steps of skill '{skill_id}'."},
    ]

    content, error = call_resolved(messages, context, max_tokens=6000)
    if error:
        content, error = call_openai(messages, max_tokens=6000)
    if error:
        return None, error

    content = strip_json_fences(content)
    return {"output": content}, None


def step_3_critic(inputs, context):
    """Two-layer validation: deterministic then LLM."""
    prompts_text = context.get("improved_prompts", context.get("generated_prompts",
                   context.get("step_2_output", "")))
    if isinstance(prompts_text, dict):
        prompts_text = json.dumps(prompts_text)
    if not prompts_text:
        return None, "No prompts to validate"

    plan = context.get("step_1_output", {})
    expected_ids = plan.get("expected_step_ids", [])
    output_format = plan.get("output_format", "prose")
    critic_ids = plan.get("critic_step_ids", [])

    # ── Layer 1: Deterministic validation ─────────────────────────────────
    cleaned = strip_json_fences(prompts_text)
    det_issues, parsed, parse_ok = deterministic_validate_prompts(
        cleaned, expected_ids, output_format, critic_ids)

    if not parse_ok:
        return {"output": {
            "quality_score": 1,
            "structural_score": 0,
            "specificity_score": 0,
            "constraint_score": 0,
            "deterministic_issues": det_issues,
            "llm_feedback": "JSON parse failed — cannot evaluate further",
            "feedback": f"CRITICAL: {det_issues[0]}",
        }}, None

    det_penalty = len(det_issues)
    structural_score = max(0, 10 - (det_penalty * 2))

    # ── Layer 2: LLM quality evaluation ───────────────────────────────────
    skill_purpose = plan.get("skill_purpose", "")

    system = """You are a strict prompt quality evaluator for NemoClaw skills.

Score these dimensions (each 0-10):

- specificity_score: Are prompts specific to this skill's purpose? Do they
  reference the skill's domain explicitly? Are constraints meaningful (not
  generic "be accurate")? Does each prompt state the step-specific objective?

- constraint_score: Do prompts have strong, enforceable constraints? Are there
  at least 3 per prompt? Are forbidden behaviors explicit? Are output format
  rules clear and unambiguous?

Respond with JSON ONLY — no markdown, no backticks:
{"specificity_score": N, "constraint_score": N, "llm_feedback": "Specific notes"}"""

    user = f"""GENERATED PROMPTS:
{cleaned[:5000]}

SKILL PURPOSE: {skill_purpose}

Evaluate specificity and constraint quality."""

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    content, error = call_resolved(messages, context, max_tokens=1500)
    if error:
        content, error = call_openai(messages, max_tokens=1500)

    llm_scores = {"specificity_score": 5, "constraint_score": 5, "llm_feedback": ""}
    if not error and content:
        try:
            llm_cleaned = content.strip()
            if llm_cleaned.startswith("```"):
                llm_cleaned = re.sub(r'^```(?:json)?\s*', '', llm_cleaned)
                llm_cleaned = re.sub(r'\s*```$', '', llm_cleaned)
            llm_scores = json.loads(llm_cleaned)
        except (json.JSONDecodeError, TypeError):
            llm_scores["llm_feedback"] = content

    specificity = llm_scores.get("specificity_score", 5)
    constraint = llm_scores.get("constraint_score", 5)
    quality_score = min(structural_score, specificity, constraint)

    feedback_parts = []
    if det_issues:
        feedback_parts.append(
            f"STRUCTURAL ISSUES ({len(det_issues)}): " +
            " | ".join(det_issues[:8]))
    llm_fb = llm_scores.get("llm_feedback", "")
    if llm_fb:
        feedback_parts.append(f"QUALITY NOTES: {llm_fb}")

    return {"output": {
        "quality_score": quality_score,
        "structural_score": structural_score,
        "specificity_score": specificity,
        "constraint_score": constraint,
        "deterministic_issues": det_issues,
        "llm_feedback": llm_fb,
        "feedback": " || ".join(feedback_parts) if feedback_parts else "All checks passed",
    }}, None


def step_4_llm(inputs, context):
    """Improve prompts based on critic feedback."""
    plan = context.get("step_1_output", {})
    skill_purpose = plan.get("skill_purpose", "")

    prompts_text = context.get("improved_prompts", context.get("generated_prompts",
                   context.get("step_2_output", "")))
    if isinstance(prompts_text, dict):
        prompts_text = json.dumps(prompts_text, indent=2)

    critic = context.get("step_3_output", {})
    if isinstance(critic, str):
        try:
            critic = json.loads(critic)
        except (json.JSONDecodeError, TypeError):
            critic = {"feedback": critic}

    feedback = critic.get("feedback", "No specific feedback")
    det_issues = critic.get("deterministic_issues", [])
    structural = critic.get("structural_score", "?")
    specificity = critic.get("specificity_score", "?")
    constraint = critic.get("constraint_score", "?")

    det_section = ""
    if det_issues:
        det_section = "\nCRITICAL ISSUES TO FIX:\n" + "\n".join(
            f"  - {issue}" for issue in det_issues[:10])

    system = f"""{PROMPT_REFERENCE}

You are fixing system prompts that have quality issues.

FIX RULES:
1. Output ONLY the corrected JSON object. No markdown fences. No explanation.
2. Fix ALL structural issues listed below first.
3. Replace any banned phrases with specific alternatives (see reference).
4. Remove any capability hallucinations.
5. Ensure every prompt has role, task, constraints, output format.
6. Ensure critic prompts instruct JSON with quality_score and feedback.
7. Preserve the overall intent of each prompt.
{det_section}"""

    user = f"""CURRENT PROMPTS:
{strip_json_fences(prompts_text)}

CRITIC FEEDBACK: {feedback}
SCORES: structural={structural}/10 | specificity={specificity}/10 | constraint={constraint}/10

SKILL PURPOSE: {skill_purpose}

Fix all issues. Output ONLY the corrected JSON object."""

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    content, error = call_resolved(messages, context, max_tokens=6000)
    if error:
        content, error = call_openai(messages, max_tokens=6000)
    if error:
        return None, error

    content = strip_json_fences(content)
    return {"output": content}, None


def _select_best_output(context):
    """Latest surviving candidate after critic loop."""
    for key in ("improved_prompts", "generated_prompts", "step_2_output"):
        v = context.get(key, "")
        if v and isinstance(v, str) and v.strip():
            return v
    return context.get("generated_prompts", "")


def step_5_write(inputs, context):
    """Full deterministic validation gate — hard-fail on any violation."""
    best = _select_best_output(context)
    if isinstance(best, dict):
        best = json.dumps(best)

    if not best or not best.strip():
        return None, "No prompt output to write"

    plan = context.get("step_1_output", {})
    expected_ids = plan.get("expected_step_ids", [])
    output_format = plan.get("output_format", "prose")
    critic_ids = plan.get("critic_step_ids", [])

    cleaned = strip_json_fences(best)
    det_issues, parsed, parse_ok = deterministic_validate_prompts(
        cleaned, expected_ids, output_format, critic_ids)

    if not parse_ok:
        return None, f"JSON INTEGRITY FAILURE: {det_issues[0]}"

    if det_issues:
        summary = "; ".join(det_issues[:5])
        count = len(det_issues)
        return None, f"PROMPT INTEGRITY FAILURE — {count} issue(s): {summary}"

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
