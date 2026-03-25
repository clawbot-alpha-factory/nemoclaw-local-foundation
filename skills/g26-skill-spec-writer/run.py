#!/usr/bin/env python3
"""
NemoClaw Skill: g26-skill-spec-writer
Skill Spec Writer v1.0.0
F26 | G | internal | executor
Schema v2 | Runner v4.0+

Generates complete schema-v2-compliant skill.yaml specifications.
Fix 1: Deterministic YAML parsing in step 3 before LLM evaluation.
Fix 2: "YAML only" in step 2, strip fences in step 3.
Fix 4: Split deterministic + LLM validation in step 3.
Fix 7: "No invented fields, no renamed fields" in step 2 prompt.
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


def call_openai(messages, model="gpt-5.4-mini", max_tokens=4000):
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, SystemMessage
    env = load_env()
    key = env.get("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
    if not key: return None, "OPENAI_API_KEY not found"
    llm = ChatOpenAI(model=model, api_key=key, max_tokens=max_tokens, temperature=0.2)
    lc = [SystemMessage(content=m["content"]) if m["role"] == "system" else HumanMessage(content=m["content"]) for m in messages]
    return llm.invoke(lc).content, None


def call_anthropic(messages, model="claude-sonnet-4-6", max_tokens=4000):
    from langchain_anthropic import ChatAnthropic
    from langchain_core.messages import HumanMessage, SystemMessage
    env = load_env()
    key = env.get("ANTHROPIC_API_KEY", os.environ.get("ANTHROPIC_API_KEY", ""))
    if not key: return None, "ANTHROPIC_API_KEY not found"
    llm = ChatAnthropic(model=model, api_key=key, max_tokens=max_tokens, temperature=0.2)
    lc = [SystemMessage(content=m["content"]) if m["role"] == "system" else HumanMessage(content=m["content"]) for m in messages]
    return llm.invoke(lc).content, None


def call_google(messages, model="gemini-2.5-flash", max_tokens=4000):
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
    p = context.get("resolved_provider", "anthropic")
    if p == "google": return call_google(messages, model=m or "gemini-2.5-flash", max_tokens=max_tokens)
    if p == "openai": return call_openai(messages, model=m or "gpt-5.4-mini", max_tokens=max_tokens)
    return call_anthropic(messages, model=m or "claude-sonnet-4-6", max_tokens=max_tokens)


# ── Naming Convention Validation ──────────────────────────────────────────────
SKILL_ID_PATTERN = re.compile(r'^[a-l]\d{2}-[a-z][a-z0-9-]{2,29}$')
FAMILY_PATTERN = re.compile(r'^F\d{2}$')
VALID_DOMAINS = set("ABCDEFGHIJKL")
VALID_TAGS = {"internal", "customer-facing", "dual-use"}
VALID_SKILL_TYPES = {"executor", "planner", "evaluator", "transformer", "router"}
VALID_STEP_TYPES = {"local", "llm", "critic"}

BANNED_STEP_NAME_TERMS = [
    "todo", "llm step", "processing step", "step 1", "step 2", "step 3",
    "step 4", "step 5", "step 6", "step 7", "step 8", "step 9", "step n",
]

# Fields that must NOT appear in v2 skill.yaml
FORBIDDEN_FIELDS_TOP = {"machine_conditions"}
FORBIDDEN_STEP_FIELDS = {"makes_llm_call", "machine_conditions"}
FORBIDDEN_STEP_TYPES = {"decision"}

# Required top-level keys in a v2 skill.yaml
REQUIRED_TOP_KEYS = {
    "name", "version", "display_name", "description", "author", "created",
    "family", "domain", "tag", "skill_type", "schema_version",
    "runner_version_required", "routing_system_version_required",
    "max_loop_iterations", "context_requirements", "execution_role",
    "inputs", "outputs", "artifacts", "steps", "contracts",
    "approval_boundaries", "routing", "composable",
}

# Required step keys
REQUIRED_STEP_KEYS = {
    "id", "name", "step_type", "task_class", "description",
    "input_source", "output_key", "idempotency", "requires_human_approval",
    "failure", "transition",
}


# ── Deterministic Schema Validation ───────────────────────────────────────────
def strip_yaml_fences(text):
    """Fix 2: Strip markdown code fences from YAML output."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r'^```(?:ya?ml)?\s*\n?', '', text)
        text = re.sub(r'\n?\s*```\s*$', '', text)
    return text.strip()


def deterministic_validate(yaml_text):
    """Fix 1 + Fix 4: Deterministic structural validation of generated YAML.
    Returns (issues: list[str], parsed: dict|None, parse_ok: bool)."""
    issues = []

    # Layer 1: YAML parse
    cleaned = strip_yaml_fences(yaml_text)
    try:
        parsed = yaml.safe_load(cleaned)
    except yaml.YAMLError as e:
        return [f"YAML PARSE FAILURE: {str(e)[:200]}"], None, False

    if not isinstance(parsed, dict):
        return ["YAML did not produce a dict — got " + type(parsed).__name__], None, False

    # Layer 2: Required top-level keys
    present = set(parsed.keys())
    missing_top = REQUIRED_TOP_KEYS - present
    if missing_top:
        issues.append(f"Missing required top-level keys: {sorted(missing_top)}")

    # Layer 3: Forbidden top-level fields
    forbidden_found = FORBIDDEN_FIELDS_TOP & present
    if forbidden_found:
        issues.append(f"Forbidden top-level fields present: {sorted(forbidden_found)}")

    # Layer 4: schema_version must be 2
    if parsed.get("schema_version") != 2:
        issues.append(f"schema_version must be 2, got: {parsed.get('schema_version')}")

    # Layer 5: skill_type validity
    st = parsed.get("skill_type", "")
    if st and st not in VALID_SKILL_TYPES:
        issues.append(f"Invalid skill_type: '{st}'. Must be one of: {sorted(VALID_SKILL_TYPES)}")

    # Layer 6: tag validity
    tg = parsed.get("tag", "")
    if tg and tg not in VALID_TAGS:
        issues.append(f"Invalid tag: '{tg}'. Must be one of: {sorted(VALID_TAGS)}")

    # Layer 7: Steps validation
    steps = parsed.get("steps", [])
    step_ids = []
    if not isinstance(steps, list) or len(steps) == 0:
        issues.append("Steps must be a non-empty list")
    else:
        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                issues.append(f"Step {i} is not a dict")
                continue

            sid = step.get("id", f"<missing_id_{i}>")
            step_ids.append(sid)

            # Required step keys
            step_present = set(step.keys())
            missing_step = REQUIRED_STEP_KEYS - step_present
            if missing_step:
                issues.append(f"Step '{sid}' missing keys: {sorted(missing_step)}")

            # Forbidden step fields
            forbidden_step = FORBIDDEN_STEP_FIELDS & step_present
            if forbidden_step:
                issues.append(f"Step '{sid}' has forbidden fields: {sorted(forbidden_step)}")

            # Step type validity
            stype = step.get("step_type", "")
            if stype in FORBIDDEN_STEP_TYPES:
                issues.append(f"Step '{sid}' uses forbidden step_type: '{stype}'")
            elif stype and stype not in VALID_STEP_TYPES:
                issues.append(f"Step '{sid}' has invalid step_type: '{stype}'")

            # Step name: semantic, 3+ words, no banned terms
            sname = step.get("name", "")
            if sname:
                word_count = len(sname.strip().split())
                if word_count < 3:
                    issues.append(f"Step '{sid}' name has only {word_count} words (min 3): '{sname}'")
                name_lower = sname.lower()
                for banned in BANNED_STEP_NAME_TERMS:
                    if banned in name_lower:
                        issues.append(f"Step '{sid}' name contains banned term '{banned}': '{sname}'")

            # success_conditions must be structured (left/op/right)
            failure = step.get("failure", {})
            if isinstance(failure, dict):
                sc = failure.get("success_conditions", [])
                if isinstance(sc, list):
                    for j, cond in enumerate(sc):
                        if isinstance(cond, dict):
                            if "left" not in cond or "op" not in cond:
                                issues.append(
                                    f"Step '{sid}' success_conditions[{j}] missing 'left' or 'op' — "
                                    f"must use structured format")
                        elif isinstance(cond, str):
                            issues.append(
                                f"Step '{sid}' success_conditions[{j}] is a string — "
                                f"must use structured {{left, op, right}} format")

            # Transition conditions must be structured
            trans = step.get("transition", {})
            if isinstance(trans, dict):
                for j, tc in enumerate(trans.get("conditions", [])):
                    if isinstance(tc, dict):
                        if "left" not in tc or "op" not in tc or "go_to" not in tc:
                            issues.append(
                                f"Step '{sid}' transition condition[{j}] missing "
                                f"'left', 'op', or 'go_to'")
                    elif isinstance(tc, str):
                        issues.append(
                            f"Step '{sid}' transition condition[{j}] is a string — "
                            f"must use structured {{left, op, right, go_to}} format")

            # input_source must not be best_available
            isrc = step.get("input_source", "")
            if isrc == "best_available":
                issues.append(
                    f"Step '{sid}' uses 'best_available' as input_source — "
                    f"use '__final_output__' instead")

        # Unique step IDs
        if len(step_ids) != len(set(step_ids)):
            dupes = [s for s in step_ids if step_ids.count(s) > 1]
            issues.append(f"Duplicate step IDs: {sorted(set(dupes))}")

    # Layer 8: Contracts must be split
    contracts = parsed.get("contracts", {})
    if isinstance(contracts, dict):
        if "machine_validated" not in contracts and any(
                k in contracts for k in ("output_format", "required_fields", "quality", "sla")):
            issues.append(
                "Contracts must be split into 'machine_validated' and "
                "'declarative_guarantees' — found flat structure")

    # Layer 9: observability field validation
    obs = parsed.get("observability", {})
    if isinstance(obs, dict):
        ALLOWED_OBS_KEYS = {"log_level", "track_cost", "track_latency", "track_tokens",
                            "track_quality", "metrics_file"}
        invented_obs = set(obs.keys()) - ALLOWED_OBS_KEYS
        if invented_obs:
            issues.append(f"observability has invented fields: {sorted(invented_obs)}. "
                          f"Allowed: {sorted(ALLOWED_OBS_KEYS)}")

    # Layer 10: critic_loop structure (if present)
    cl = parsed.get("critic_loop", {})
    if isinstance(cl, dict) and cl.get("enabled"):
        for req_key in ("generator_step", "critic_step", "improve_step",
                        "score_field", "acceptance_score", "max_improvements",
                        "counter_name", "fallback_final_step"):
            if req_key not in cl:
                issues.append(f"critic_loop missing required key: '{req_key}'")
        # score_field must be a dotted path like "step_3_output.quality_score"
        sf = cl.get("score_field", "")
        if sf and "." not in sf:
            issues.append(f"critic_loop.score_field '{sf}' must be a dotted path "
                          f"(e.g., 'step_3_output.quality_score')")
        # counter_name must be a simple name, not a dotted path
        cn = cl.get("counter_name", "")
        if cn and "." in cn:
            issues.append(f"critic_loop.counter_name '{cn}' must be a simple name "
                          f"(e.g., 'critic_loop'), not a dotted path")

    # Layer 11: final_output structure (if present)
    fo = parsed.get("final_output")
    if fo and isinstance(fo, dict):
        for cand in fo.get("candidates", []):
            if isinstance(cand, dict) and "score_from" not in cand:
                issues.append(f"final_output candidate '{cand.get('key', '?')}' missing 'score_from'")

    # Layer 12: Cross-reference validation
    step_id_set = set(step_ids)
    if step_id_set:
        # critic_loop step references must exist
        cl = parsed.get("critic_loop", {})
        if isinstance(cl, dict) and cl.get("enabled"):
            for ref_key in ("generator_step", "critic_step", "improve_step", "fallback_final_step"):
                ref_val = cl.get(ref_key, "")
                if ref_val and ref_val not in step_id_set:
                    issues.append(f"critic_loop.{ref_key} '{ref_val}' not found in step IDs: {sorted(step_id_set)}")

        # final_output.candidates[].from_step must exist
        if fo and isinstance(fo, dict):
            for cand in fo.get("candidates", []):
                if isinstance(cand, dict):
                    fs = cand.get("from_step", "")
                    if fs and fs not in step_id_set:
                        issues.append(f"final_output candidate from_step '{fs}' not found in step IDs")
            # final_output.fallback must match a candidate key
            fb = fo.get("fallback", "")
            cand_keys = {c.get("key", "") for c in fo.get("candidates", []) if isinstance(c, dict)}
            if fb and cand_keys and fb not in cand_keys:
                issues.append(f"final_output.fallback '{fb}' not in candidate keys: {sorted(cand_keys)}")

        # transition.conditions[].go_to must reference valid step IDs or __end__
        for step in parsed.get("steps", []):
            if not isinstance(step, dict):
                continue
            sid = step.get("id", "?")
            trans = step.get("transition", {})
            if isinstance(trans, dict):
                # Check default target
                default_target = trans.get("default", "")
                if default_target and default_target != "__end__" and default_target not in step_id_set:
                    issues.append(f"Step '{sid}' transition.default '{default_target}' not found in step IDs")
                # Check condition go_to targets
                for tc in trans.get("conditions", []):
                    if isinstance(tc, dict):
                        gt = tc.get("go_to", "")
                        if gt and gt != "__end__" and gt not in step_id_set:
                            issues.append(f"Step '{sid}' transition go_to '{gt}' not found in step IDs")

            # failure.fallback_step must reference valid step ID
            failure = step.get("failure", {})
            if isinstance(failure, dict):
                fbs = failure.get("fallback_step")
                if fbs and fbs not in step_id_set:
                    issues.append(f"Step '{sid}' failure.fallback_step '{fbs}' not found in step IDs")

    return issues, parsed, True


# ── Step Handlers ─────────────────────────────────────────────────────────────

def step_1_local(inputs, context):
    """Parse skill concept and validate naming convention."""
    skill_id = inputs.get("skill_id", "").strip()
    skill_name = inputs.get("skill_name", "").strip()
    family = inputs.get("family", "").strip()
    domain = inputs.get("domain", "").strip().upper()
    tag = inputs.get("tag", "").strip()
    skill_type = inputs.get("skill_type", "executor").strip()
    concept = inputs.get("skill_concept", "").strip()
    step_hints = inputs.get("step_hints", "").strip()
    has_critic = inputs.get("has_critic_loop", "false")

    if isinstance(has_critic, str):
        has_critic = has_critic.lower() in ("true", "1", "yes")

    errors = []

    if not concept or len(concept) < 20:
        errors.append("skill_concept is required and must be at least 20 characters")
    if not skill_id:
        errors.append("skill_id is required")
    elif not SKILL_ID_PATTERN.match(skill_id):
        errors.append(
            f"skill_id '{skill_id}' does not match pattern: "
            f"{{domain_letter}}{{family_zero_padded}}-{{slug}}")
    if not skill_name:
        errors.append("skill_name is required")
    if not FAMILY_PATTERN.match(family):
        errors.append(f"family '{family}' must match pattern F## (e.g., F26)")
    if domain not in VALID_DOMAINS:
        errors.append(f"domain '{domain}' must be A-L")
    if tag not in VALID_TAGS:
        errors.append(f"tag '{tag}' must be: internal, customer-facing, or dual-use")
    if skill_type not in VALID_SKILL_TYPES:
        errors.append(f"skill_type '{skill_type}' must be: executor, planner, evaluator, transformer, router")

    # Cross-validate: skill_id domain letter should match domain
    if skill_id and domain:
        expected_prefix = domain.lower()
        if not skill_id.startswith(expected_prefix):
            errors.append(
                f"skill_id '{skill_id}' starts with '{skill_id[0]}' "
                f"but domain is '{domain}' (expected prefix '{expected_prefix}')")

    # Cross-validate: skill_id family digits should match family
    if skill_id and family and len(skill_id) >= 3:
        id_family_num = skill_id[1:3]
        fam_num = family.replace("F", "").replace("f", "")
        if id_family_num != fam_num.zfill(2):
            errors.append(
                f"skill_id family digits '{id_family_num}' don't match "
                f"family '{family}' (expected '{fam_num.zfill(2)}')")

    if errors:
        return None, " | ".join(errors)

    result = {
        "skill_id": skill_id,
        "skill_name": skill_name,
        "family": family,
        "domain": domain,
        "tag": tag,
        "skill_type": skill_type,
        "concept": concept,
        "step_hints": step_hints,
        "has_critic_loop": has_critic,
        "default_alias": {"internal": "moderate", "customer-facing": "premium", "dual-use": "complex_reasoning"}.get(tag, "moderate"),
    }

    return {"output": result}, None


# ── Schema v2 Reference for Step 2 Prompt ─────────────────────────────────────
SCHEMA_V2_REFERENCE = """
=== SKILL.YAML SCHEMA V2 — COMPLETE STRUCTURAL RULES ===

REQUIRED TOP-LEVEL FIELDS (all must be present):
  name, version, display_name, description, author, created,
  family, domain, tag, skill_type, schema_version, runner_version_required,
  routing_system_version_required, max_loop_iterations, context_requirements,
  execution_role, inputs, outputs, artifacts, steps, contracts,
  approval_boundaries, routing, composable

OPTIONAL TOP-LEVEL FIELDS:
  final_output, critic_loop, observability

FIELD RULES:
- schema_version: MUST be 2
- runner_version_required: ">=4.0.0"
- routing_system_version_required: ">=3.0.0"
- skill_type: one of executor | planner | evaluator | transformer | router
- tag: one of internal | customer-facing | dual-use
- max_loop_iterations: integer, default 3
- context_requirements: list, usually [workflow_id, budget_state, step_history]
- execution_role: string, the agent persona for this skill

INPUT FIELDS:
  - name, type, required, description
  - optional: validation (min_length, max_length, allowed_values), default

OUTPUT FIELDS:
  - name, type, description
  - Standard outputs: result (string), result_file (file_path), envelope_file (file_path)

ARTIFACTS:
  storage_location, filename_pattern, envelope_pattern, format, committed_to_repo, gitignored

STEP FIELDS (all required per step):
  id, name, step_type, task_class, description, input_source, output_key,
  idempotency, requires_human_approval, failure, transition

STEP RULES:
- step_type: ONLY local | llm | critic (NO "decision" type)
- name: semantic, minimum 3 words, BANNED: "TODO", "LLM step", "Processing step", "Step N"
- input_source: use "inputs.field_name", "step_N.output", or "__final_output__"
  NEVER use "best_available"
- output_key: unique string for storing step output in context
- task_class: general_short | moderate | premium | reasoning_claude etc.

IDEMPOTENCY:
  rerunnable: bool, cached: bool, never_auto_rerun: bool

FAILURE BLOCK:
  success_conditions: list of STRUCTURED conditions — each is {left, op, right}
    Supported ops: not_empty, contains, >=, <=, >, <, ==, !=
    Example: {left: "generated_yaml", op: "not_empty", right: true}
  strategy: retry | fallback | halt
  retry_count: integer
  fallback_step: step_id or null
  escalation_message: string

  CRITICAL: success_conditions must NEVER be strings. Always structured {left, op, right}.
  The field name is "success_conditions" NOT "machine_conditions".

TRANSITION BLOCK:
  default: next_step_id or "__end__"
  conditions: list of STRUCTURED conditions — each is {left, op, right, go_to, reason}
    Example: {left: "step_3_output.quality_score", op: ">=", right: 8, go_to: step_5, reason: "..."}

  CRITICAL: transition conditions must NEVER be strings like "if quality_score >= 8".
  Always structured {left, op, right, go_to}.

CONTRACTS (must be split):
  machine_validated:
    output_format, required_fields, quality (min_length, max_length, min_quality_score),
    sla (max_execution_seconds, max_cost_usd)
  declarative_guarantees: list of guarantee strings

CRITIC_LOOP (when enabled):
  enabled: true
  generator_step, critic_step, improve_step, score_field,
  acceptance_score, max_improvements, counter_name, fallback_final_step
  RULES:
  - score_field MUST be a dotted path: "{critic_output_key}.quality_score"
    Example: "step_3_output.quality_score" or "critic_evaluation.quality_score"
    NEVER just "quality_score" — it must reference the critic step's output_key
  - counter_name MUST be a simple name like "critic_loop" — NOT a dotted path
  - acceptance_score: default 8
  - max_improvements: default 2

OBSERVABILITY (optional but if present, use ONLY these fields):
  log_level: minimal | standard | detailed
  track_cost: true | false
  track_latency: true | false
  track_tokens: true | false
  track_quality: true | false
  metrics_file: string path (e.g., "~/.nemoclaw/logs/skill-metrics.jsonl")
  DO NOT invent fields like "trace_outputs", "emit_quality_scores", etc.

FINAL_OUTPUT (when critic loop is used):
  select: highest_quality | latest | specific
  candidates: list of {key, from_step, score_from}
  fallback: key string

APPROVAL_BOUNDARIES:
  safe_steps, approval_gated_steps, blocked_external_effect_steps, notes

ROUTING:
  default_alias, allow_override

COMPOSABLE:
  output_type, can_feed_into (list), accepts_input_from (list)

=== ABSOLUTELY FORBIDDEN ===
- makes_llm_call field (step_type determines this)
- decision step type
- best_available as input_source
- machine_conditions (use success_conditions)
- String-format conditions in success_conditions or transitions
- Any field not listed above — do NOT invent new fields
- Renaming any required field (e.g., "execution_context" instead of "execution_role")
"""


def step_2_llm(inputs, context):
    """Generate complete skill.yaml specification."""
    parsed = context.get("step_1_output", context.get("_resolved_input", {}))
    if not parsed or not isinstance(parsed, dict):
        return None, "No parsed input from step 1"

    skill_id = parsed.get("skill_id", "")
    skill_name = parsed.get("skill_name", "")
    family = parsed.get("family", "")
    domain = parsed.get("domain", "")
    tag = parsed.get("tag", "internal")
    skill_type = parsed.get("skill_type", "executor")
    concept = parsed.get("concept", "")
    step_hints = parsed.get("step_hints", "")
    has_critic = parsed.get("has_critic_loop", False)
    default_alias = parsed.get("default_alias", "production")

    critic_instruction = ""
    if has_critic:
        critic_instruction = """
This skill REQUIRES a critic loop. You must include:
- A generator step (step_type: llm) that produces the main output
- A critic step (step_type: critic) that evaluates quality with a score 0-10
- An improve step (step_type: llm) that fixes issues based on critic feedback
- The improve step transitions back to the critic step (loop)
- A final local step that writes the artifact
- A top-level critic_loop block with all required fields
- A top-level final_output block with candidates and score_from
- Transition conditions on the critic step to exit when score >= acceptance or max loops reached
"""
    else:
        critic_instruction = """
This skill does NOT use a critic loop. Do not include critic_loop or final_output blocks.
Use simple sequential step transitions.
"""

    # Fix 7: Explicit "no invented fields, no renamed fields"
    system = f"""You are an expert NemoClaw skill architect. Your task is to produce a complete,
valid skill.yaml file that strictly follows the v2 schema specification below.

{SCHEMA_V2_REFERENCE}

GENERATION RULES:
1. Output ONLY valid YAML. No markdown fences. No explanations. No commentary.
   Start directly with "name:" — the first line of the YAML.
2. Include ALL required top-level fields listed in the schema.
3. Do NOT invent any fields not in the schema. Do NOT rename any required fields.
4. Every step must have ALL required step fields.
5. All success_conditions must use structured {{left, op, right}} format.
6. All transition conditions must use structured {{left, op, right, go_to, reason}} format.
7. Contracts must be split into machine_validated and declarative_guarantees.
8. Step names must be semantic — minimum 3 words, no banned terms.
9. step_type determines LLM usage: llm and critic make calls, local does not.
   Do NOT include a makes_llm_call field.
10. Use "__final_output__" for the last step's input_source when it needs the best output.
    Never use "best_available".
{critic_instruction}

SKILL METADATA:
- Skill ID: {skill_id}
- Display Name: {skill_name}
- Family: {family}
- Domain: {domain}
- Tag: {tag}
- Skill Type: {skill_type}
- Default Routing Alias: {default_alias}
- Author: Core88
- Created: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}
"""

    user_msg = f"""Generate the complete skill.yaml for this skill:

CONCEPT: {concept}

{f'STEP HINTS: {step_hints}' if step_hints else 'Design appropriate steps based on the concept.'}

Remember: output ONLY the raw YAML content starting with "name:". No fences, no explanation."""

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_msg},
    ]

    content, error = call_resolved(messages, context, max_tokens=6000)
    if error:
        content, error = call_openai(messages, model="gpt-5.4-mini", max_tokens=6000)
    if error:
        return None, error

    # Fix 2: Strip any accidental fences from output
    content = strip_yaml_fences(content)

    return {"output": content}, None


def step_3_critic(inputs, context):
    """Fix 1 + Fix 4: Two-layer validation — deterministic then LLM."""
    yaml_text = context.get("improved_yaml", context.get("generated_yaml",
                context.get("step_2_output", "")))
    if isinstance(yaml_text, dict):
        yaml_text = str(yaml_text)
    if not yaml_text:
        return None, "No YAML to validate"

    parsed_input = context.get("step_1_output", {})
    expected_id = parsed_input.get("skill_id", "")
    expected_tag = parsed_input.get("tag", "")
    expected_type = parsed_input.get("skill_type", "")
    has_critic = parsed_input.get("has_critic_loop", False)

    # ── Layer 1: Deterministic validation ─────────────────────────────────
    # Fix 2: Strip fences before parsing
    cleaned = strip_yaml_fences(yaml_text)
    det_issues, parsed, parse_ok = deterministic_validate(cleaned)

    if not parse_ok:
        # YAML parse failure — hard-fail with very low score
        return {"output": {
            "quality_score": 1,
            "structural_score": 0,
            "naming_score": 0,
            "completeness_score": 0,
            "consistency_score": 0,
            "deterministic_issues": det_issues,
            "llm_feedback": "YAML failed to parse — cannot evaluate further",
            "feedback": f"CRITICAL: {det_issues[0]}. Fix the YAML syntax first.",
        }}, None

    # Additional deterministic checks against expected values
    if parsed and expected_id and parsed.get("name") != expected_id:
        det_issues.append(
            f"name field '{parsed.get('name')}' does not match expected skill_id '{expected_id}'")
    if parsed and expected_tag and parsed.get("tag") != expected_tag:
        det_issues.append(
            f"tag '{parsed.get('tag')}' does not match expected '{expected_tag}'")
    if parsed and expected_type and parsed.get("skill_type") != expected_type:
        det_issues.append(
            f"skill_type '{parsed.get('skill_type')}' does not match expected '{expected_type}'")
    if has_critic and parsed:
        cl = parsed.get("critic_loop", {})
        if not cl or not cl.get("enabled"):
            det_issues.append("has_critic_loop is true but critic_loop is missing or not enabled")
        if not parsed.get("final_output"):
            det_issues.append("has_critic_loop is true but final_output block is missing")

    det_penalty = len(det_issues)  # Each issue reduces max possible score

    # ── Layer 2: LLM quality evaluation ───────────────────────────────────
    system = """You are a strict skill.yaml schema v2 validator. You receive a generated
skill.yaml and evaluate its QUALITY (not just structure — the deterministic
validator already checked structure).

Score these dimensions (each 0-10):

- naming_score: Are step names semantic, descriptive, and professional?
  At least 3 words each? No generic or banned terms?

- completeness_score: Does the spec cover all aspects of the skill concept?
  Are descriptions thorough? Are inputs/outputs well-defined? Are
  success_conditions meaningful (not just "not_empty" everywhere)?

- consistency_score: Do step types match their purpose? Do transitions
  make logical sense? Does the routing alias match the tag? Are
  composable declarations reasonable?

Respond with JSON ONLY — no markdown, no backticks, no explanation:
{"naming_score": N, "completeness_score": N, "consistency_score": N, "llm_feedback": "Specific actionable notes"}"""

    user = f"""GENERATED SKILL.YAML:
{cleaned[:4000]}

SKILL CONCEPT: {parsed_input.get('concept', 'Unknown')}

Evaluate quality. Focus on naming, completeness, and consistency."""

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    content, error = call_resolved(messages, context, max_tokens=1500)
    if error:
        content, error = call_openai(messages, model="gpt-5.4-mini", max_tokens=1500)

    # Parse LLM response
    llm_scores = {"naming_score": 5, "completeness_score": 5,
                  "consistency_score": 5, "llm_feedback": ""}
    if not error and content:
        try:
            llm_cleaned = content.strip()
            if llm_cleaned.startswith("```"):
                llm_cleaned = re.sub(r'^```(?:json)?\s*', '', llm_cleaned)
                llm_cleaned = re.sub(r'\s*```$', '', llm_cleaned)
            llm_scores = json.loads(llm_cleaned)
        except (json.JSONDecodeError, TypeError):
            llm_scores["llm_feedback"] = content

    # ── Combine scores ────────────────────────────────────────────────────
    # Deterministic: 10 minus 2 per issue, floor at 0
    structural_score = max(0, 10 - (det_penalty * 2))

    naming = llm_scores.get("naming_score", 5)
    completeness = llm_scores.get("completeness_score", 5)
    consistency = llm_scores.get("consistency_score", 5)

    # Final quality_score: min of all dimensions
    # Structural issues dominate — a YAML with forbidden fields can't score high
    quality_score = min(structural_score, naming, completeness, consistency)

    # Build combined feedback
    feedback_parts = []
    if det_issues:
        feedback_parts.append(
            f"STRUCTURAL ISSUES ({len(det_issues)}): " +
            " | ".join(det_issues))
    llm_fb = llm_scores.get("llm_feedback", "")
    if llm_fb:
        feedback_parts.append(f"QUALITY NOTES: {llm_fb}")

    return {"output": {
        "quality_score": quality_score,
        "structural_score": structural_score,
        "naming_score": naming,
        "completeness_score": completeness,
        "consistency_score": consistency,
        "deterministic_issues": det_issues,
        "llm_feedback": llm_fb,
        "feedback": " || ".join(feedback_parts) if feedback_parts else "All checks passed",
    }}, None


def step_4_llm(inputs, context):
    """Fix schema violations based on critic feedback."""
    parsed_input = context.get("step_1_output", {})
    concept = parsed_input.get("concept", "")

    yaml_text = context.get("improved_yaml", context.get("generated_yaml",
                context.get("step_2_output", "")))
    if isinstance(yaml_text, dict):
        yaml_text = str(yaml_text)

    critic = context.get("step_3_output", {})
    if isinstance(critic, str):
        try:
            critic = json.loads(critic)
        except (json.JSONDecodeError, TypeError):
            critic = {"feedback": critic}

    feedback = critic.get("feedback", "No specific feedback")
    det_issues = critic.get("deterministic_issues", [])
    structural = critic.get("structural_score", "?")
    naming = critic.get("naming_score", "?")
    completeness = critic.get("completeness_score", "?")
    consistency = critic.get("consistency_score", "?")

    det_section = ""
    if det_issues:
        det_section = "\nCRITICAL STRUCTURAL ISSUES TO FIX:\n" + "\n".join(
            f"  - {issue}" for issue in det_issues)

    system = f"""You are fixing a skill.yaml that has schema v2 violations.

{SCHEMA_V2_REFERENCE}

FIX RULES:
1. Output ONLY the corrected YAML. No markdown fences. No explanations.
   Start directly with "name:" — the first line of the YAML.
2. Fix ALL structural issues listed below first — these are critical.
3. Then address quality feedback on naming, completeness, consistency.
4. Do NOT invent any fields not in the schema. Do NOT rename required fields.
5. Preserve the overall structure and intent of the original YAML.
{det_section}"""

    user = f"""CURRENT YAML WITH VIOLATIONS:
{strip_yaml_fences(yaml_text)}

CRITIC FEEDBACK: {feedback}
SCORES: structural={structural}/10 | naming={naming}/10 | completeness={completeness}/10 | consistency={consistency}/10

SKILL CONCEPT (for reference): {concept}

Fix all issues and output ONLY the corrected raw YAML starting with "name:"."""

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    content, error = call_resolved(messages, context, max_tokens=6000)
    if error:
        content, error = call_openai(messages, model="gpt-5.4-mini", max_tokens=6000)
    if error:
        return None, error

    # Fix 2: Strip any accidental fences
    content = strip_yaml_fences(content)

    return {"output": content}, None


def _select_best_output(context):
    """Latest surviving candidate after critic loop.
    Uses 'latest' policy — the most recent non-empty candidate wins.
    Per-candidate scoring deferred to a future runner upgrade."""
    candidates = [
        {"key": "generated_yaml"},
        {"key": "improved_yaml"},
    ]

    # Latest policy: last non-empty candidate in order
    for cand in reversed(candidates):
        val = context.get(cand["key"], "")
        if val and isinstance(val, str) and val.strip():
            return val

    for key in ("improved_yaml", "generated_yaml", "step_2_output"):
        v = context.get(key, "")
        if v and isinstance(v, str):
            return v

    return context.get("generated_yaml", "")


def step_5_write(inputs, context):
    """Full deterministic validation gate — hard-fail if any issues remain."""
    best = _select_best_output(context)
    if isinstance(best, dict):
        best = str(best)

    if not best or not best.strip():
        return None, "No YAML output to write"

    cleaned = strip_yaml_fences(best)
    det_issues, parsed, parse_ok = deterministic_validate(cleaned)

    if not parse_ok:
        return None, f"YAML INTEGRITY FAILURE: {det_issues[0]}"

    if det_issues:
        summary = "; ".join(det_issues[:5])
        count = len(det_issues)
        return None, f"SCHEMA INTEGRITY FAILURE — {count} issue(s) in final output: {summary}"

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
