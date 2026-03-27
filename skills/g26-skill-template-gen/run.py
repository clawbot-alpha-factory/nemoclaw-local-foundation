#!/usr/bin/env python3
"""
NemoClaw Skill: g26-skill-template-gen
Skill Template Generator v1.0.0
F26 | G | internal | executor
Schema v2 | Runner v4.0+

Generates architecture-aligned first-draft run.py from a skill.yaml.
Follows established reference patterns exactly. Does not invent new
runtime conventions. Human review still required before deployment.
"""

import argparse
import json
import os
import re
import sys
import tempfile
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


def call_openai(messages, model="gpt-5.4-mini", max_tokens=20000):
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, SystemMessage
    env = load_env()
    key = env.get("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
    if not key: return None, "OPENAI_API_KEY not found"
    llm = ChatOpenAI(model=model, api_key=key, max_tokens=max_tokens, temperature=0.2)
    lc = [SystemMessage(content=m["content"]) if m["role"] == "system" else HumanMessage(content=m["content"]) for m in messages]
    return llm.invoke(lc).content, None


def call_anthropic(messages, model="claude-sonnet-4-6", max_tokens=20000):
    from langchain_anthropic import ChatAnthropic
    from langchain_core.messages import HumanMessage, SystemMessage
    env = load_env()
    key = env.get("ANTHROPIC_API_KEY", os.environ.get("ANTHROPIC_API_KEY", ""))
    if not key: return None, "ANTHROPIC_API_KEY not found"
    llm = ChatAnthropic(model=model, api_key=key, max_tokens=max_tokens, temperature=0.2)
    lc = [SystemMessage(content=m["content"]) if m["role"] == "system" else HumanMessage(content=m["content"]) for m in messages]
    return llm.invoke(lc).content, None


def call_google(messages, model="gemini-2.5-flash", max_tokens=20000):
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.messages import HumanMessage, SystemMessage
    env = load_env()
    key = env.get("GOOGLE_API_KEY", os.environ.get("GOOGLE_API_KEY", ""))
    if not key: return None, "GOOGLE_API_KEY not found"
    llm = ChatGoogleGenerativeAI(model=model, google_api_key=key, max_tokens=max_tokens)
    lc = [SystemMessage(content=m["content"]) if m["role"] == "system" else HumanMessage(content=m["content"]) for m in messages]
    return llm.invoke(lc).content, None


def call_resolved(messages, context, max_tokens=20000):
    m = context.get("resolved_model", "")
    p = context.get("resolved_provider", "anthropic")
    if p == "google": return call_google(messages, model=m or "gemini-2.5-flash", max_tokens=max_tokens)
    if p == "openai": return call_openai(messages, model=m or "gpt-5.4-mini", max_tokens=max_tokens)
    return call_anthropic(messages, model=m or "claude-sonnet-4-6", max_tokens=max_tokens)


# ── Code Fence Stripping ──────────────────────────────────────────────────────
def strip_code_fences(text):
    """Strip markdown code fences from Python output."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r'^```(?:python|py)?\s*\n?', '', text)
        text = re.sub(r'\n?\s*```\s*$', '', text)
    return text.strip()


# ── Deterministic Code Validation ─────────────────────────────────────────────
def deterministic_validate_code(code, step_classifications):
    """Validate generated run.py against architectural rules.
    Returns (issues: list[str], compile_ok: bool)."""
    issues = []

    # Layer 1: Python compile
    cleaned = strip_code_fences(code)
    try:
        compile(cleaned, "<generated_run_py>", "exec")
    except SyntaxError as e:
        return [f"PYTHON SYNTAX ERROR: line {e.lineno}: {e.msg}"], False

    # Layer 2: STEP_HANDLERS coverage
    handler_match = re.search(r'STEP_HANDLERS\s*=\s*\{([^}]+)\}', cleaned, re.DOTALL)
    if not handler_match:
        issues.append("Missing STEP_HANDLERS dict")
    else:
        handler_block = handler_match.group(1)
        expected_ids = {s["step_id"] for s in step_classifications}
        for sid in expected_ids:
            if f'"{sid}"' not in handler_block and f"'{sid}'" not in handler_block:
                issues.append(f"STEP_HANDLERS missing entry for '{sid}'")

    # Layer 3: Handler function definitions
    defined_functions = set(re.findall(r'^def\s+(step_\w+)\s*\(', cleaned, re.MULTILINE))
    for sc in step_classifications:
        sid = sc["step_id"]
        # Expected function pattern: step_N_type or just step_N
        expected_patterns = [
            f"{sid}_local", f"{sid}_llm", f"{sid}_critic", f"{sid}_write",
            sid,  # bare step_id as function name
        ]
        found = any(p in defined_functions for p in expected_patterns)
        if not found:
            # Check if any function references this step in STEP_HANDLERS
            handler_refs = re.findall(
                rf'["\']' + re.escape(sid) + rf'["\']:\s*(\w+)', cleaned)
            if handler_refs:
                for ref in handler_refs:
                    if ref not in defined_functions and ref not in dir(__builtins__):
                        issues.append(
                            f"STEP_HANDLERS references '{ref}' for '{sid}' "
                            f"but function is not defined")
            else:
                issues.append(f"No handler function found for '{sid}'")

    # Layer 4: LLM/critic steps must use call_resolved
    for sc in step_classifications:
        sid = sc["step_id"]
        if sc["calls_llm"]:
            # Find the handler function body
            pattern = rf'def\s+\w*{re.escape(sid)}\w*\s*\([^)]*\).*?(?=\ndef\s|\nSTEP_HANDLERS|\Z)'
            fn_match = re.search(pattern, cleaned, re.DOTALL)
            if fn_match:
                fn_body = fn_match.group()
                if "call_resolved" not in fn_body:
                    issues.append(
                        f"LLM/critic step '{sid}' handler does not call "
                        f"call_resolved() — must use routing system")

    # Layer 5: Local steps must NOT use call_resolved
    llm_call_patterns = ["call_resolved", "call_openai", "call_anthropic", "call_google"]
    for sc in step_classifications:
        sid = sc["step_id"]
        if not sc["calls_llm"]:
            pattern = rf'def\s+\w*{re.escape(sid)}\w*\s*\([^)]*\).*?(?=\ndef\s|\nSTEP_HANDLERS|\Z)'
            fn_match = re.search(pattern, cleaned, re.DOTALL)
            if fn_match:
                fn_body = fn_match.group()
                for lp in llm_call_patterns:
                    if lp in fn_body:
                        issues.append(
                            f"Local step '{sid}' handler calls {lp}() — "
                            f"local steps must not make LLM calls")

    # Layer 6: Critic steps should return structured JSON with quality_score
    for sc in step_classifications:
        sid = sc["step_id"]
        if sc["step_type"] == "critic":
            pattern = rf'def\s+\w*{re.escape(sid)}\w*\s*\([^)]*\).*?(?=\ndef\s|\nSTEP_HANDLERS|\Z)'
            fn_match = re.search(pattern, cleaned, re.DOTALL)
            if fn_match:
                fn_body = fn_match.group()
                if "quality_score" not in fn_body:
                    issues.append(
                        f"Critic step '{sid}' handler does not reference "
                        f"'quality_score' — critic must return structured scoring")

    # Layer 7: Required imports
    required_imports = {"json", "argparse", "os", "sys"}
    for imp in required_imports:
        if f"import {imp}" not in cleaned and f"from {imp}" not in cleaned:
            issues.append(f"Missing required import: {imp}")

    # Layer 8: __main__ block
    if 'if __name__ == "__main__"' not in cleaned and "if __name__ == '__main__'" not in cleaned:
        issues.append("Missing __main__ block")
    else:
        if "--step" not in cleaned:
            issues.append("__main__ missing --step argument")
        if "--input" not in cleaned:
            issues.append("__main__ missing --input argument")

    # Layer 9: Required function presence
    required_functions = {"load_env", "call_resolved"}
    for fn in required_functions:
        if f"def {fn}" not in cleaned:
            issues.append(f"Missing required function: {fn}()")

    return issues, True


# ── Step Handlers ─────────────────────────────────────────────────────────────

def step_1_local(inputs, context):
    """Parse skill.yaml and classify step implementation requirements."""
    yaml_text = inputs.get("skill_yaml", "").strip()
    if not yaml_text or len(yaml_text) < 200:
        return None, "skill_yaml input too short (minimum 200 characters)"

    # Strip fences if present
    if yaml_text.startswith("```"):
        yaml_text = re.sub(r'^```(?:ya?ml)?\s*\n?', '', yaml_text)
        yaml_text = re.sub(r'\n?\s*```\s*$', '', yaml_text)

    try:
        parsed = yaml.safe_load(yaml_text)
    except yaml.YAMLError as e:
        return None, f"skill.yaml parse failed: {str(e)[:200]}"

    if not isinstance(parsed, dict):
        return None, "skill.yaml did not produce a dict"

    skill_id = parsed.get("name", "")
    skill_name = parsed.get("display_name", skill_id)
    tag = parsed.get("tag", "internal")
    skill_type = parsed.get("skill_type", "executor")
    version = parsed.get("version", "1.0.0")
    description = parsed.get("description", "")
    execution_role = parsed.get("execution_role", "")

    steps = parsed.get("steps", [])
    if not steps:
        return None, "skill.yaml has no steps"

    # Deep classification per step
    step_classifications = []
    step_ids = [s.get("id", "") for s in steps if isinstance(s, dict)]
    last_step_id = step_ids[-1] if step_ids else ""

    cl = parsed.get("critic_loop", {})
    has_critic_loop = isinstance(cl, dict) and cl.get("enabled", False)
    critic_step_id = cl.get("critic_step", "") if has_critic_loop else ""
    improve_step_id = cl.get("improve_step", "") if has_critic_loop else ""

    ref_pattern = inputs.get("reference_pattern", "executor")
    det_check_type = inputs.get("deterministic_check_type", "none")

    for step in steps:
        if not isinstance(step, dict):
            continue
        sid = step.get("id", "")
        stype = step.get("step_type", "local")
        sname = step.get("name", "")
        sdesc = step.get("description", "")
        is_final = (sid == last_step_id)
        calls_llm = stype in ("llm", "critic")

        # Classify handler type
        if stype == "critic":
            handler_type = "llm_critic"
        elif stype == "llm":
            handler_type = "llm_generation"
        elif is_final:
            handler_type = "artifact_write"
        else:
            handler_type = "pure_transform"

        # Classify output format
        if stype == "critic":
            output_format = "structured_json"
        elif is_final:
            output_format = "signal_only"
        else:
            output_format = "string"

        # Does this step need deterministic checks?
        needs_det = False
        if det_check_type != "none":
            if stype == "critic":
                needs_det = True
            elif is_final:
                needs_det = True

        step_classifications.append({
            "step_id": sid,
            "step_type": stype,
            "step_name": sname,
            "step_description": sdesc,
            "handler_type": handler_type,
            "output_format": output_format,
            "output_key": step.get("output_key", sid + "_output"),
            "needs_deterministic_check": needs_det,
            "is_final_step": is_final,
            "calls_llm": calls_llm,
            "task_class": step.get("task_class", "general_short"),
        })

    # Skill-level outputs
    skill_inputs = parsed.get("inputs", [])
    skill_outputs = parsed.get("outputs", [])
    contracts = parsed.get("contracts", {})

    result = {
        "skill_id": skill_id,
        "skill_name": skill_name,
        "version": version,
        "description": description,
        "tag": tag,
        "skill_type": skill_type,
        "execution_role": execution_role,
        "has_critic_loop": has_critic_loop,
        "critic_loop_config": cl if has_critic_loop else {},
        "deterministic_check_type": det_check_type,
        "reference_pattern": ref_pattern,
        "step_classifications": step_classifications,
        "skill_inputs": skill_inputs,
        "skill_outputs": skill_outputs,
        "contracts": contracts,
        "raw_yaml": yaml_text,
    }

    return {"output": result}, None


# ── Reference Architecture for Step 2 ─────────────────────────────────────────
REFERENCE_ARCHITECTURE = """
=== NEMOCLAW RUN.PY REFERENCE ARCHITECTURE ===

Every run.py MUST follow this exact structure. Do NOT invent alternatives.

1. MODULE DOCSTRING — skill ID, version, family, domain, tag, type, schema, runner

2. IMPORTS — only standard libs + yaml + langchain providers as needed:
   import argparse, json, os, re, sys
   from datetime import datetime, timezone
   (import yaml only if the skill processes YAML)

3. load_env() — EXACT COPY from reference:
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

4. LLM CALL FUNCTIONS — EXACT PATTERN from reference (only include if skill has LLM steps):
   def call_openai(messages, model="gpt-5.4-mini", max_tokens=4000): ...
   def call_anthropic(messages, model="claude-sonnet-4-6", max_tokens=4000): ...
   def call_google(messages, model="gemini-2.5-flash", max_tokens=4000): ...
   def call_resolved(messages, context, max_tokens=4000): ...

   Each uses langchain imports INSIDE the function (lazy import pattern).
   call_resolved dispatches based on context["resolved_provider"].

   CRITICAL RETURN FORMAT — ALL call_* functions return a TUPLE: (content, error)
     Success: return llm.invoke(lc).content, None
     Failure: return None, "error message"

   Callers MUST unpack the tuple:
     content, error = call_resolved(messages, context, max_tokens=6000)
     if error:
         return None, error

   NEVER write: result = call_resolved(...)  # WRONG — misses error handling

   CRITICAL MESSAGE FORMAT — Messages MUST be list of dicts, NOT tuples:
     messages = [
         {"role": "system", "content": system_prompt},
         {"role": "user", "content": user_prompt},
     ]
   NEVER use: [("system", "..."), ("human", "...")]  # WRONG format

   LangChain conversion inside each call_* function:
     from langchain_core.messages import HumanMessage, SystemMessage
     lc = [SystemMessage(content=m["content"]) if m["role"] == "system"
           else HumanMessage(content=m["content"]) for m in messages]

5. DETERMINISTIC CHECK FUNCTIONS (if applicable) — domain-specific:
   - numeric: extract_numeric_tokens(), check_numeric_preservation()
   - structural: check paragraph/heading/list preservation
   - schema: validate JSON/YAML output structure
   - custom: placeholder for manual implementation

6. STEP HANDLER FUNCTIONS — one per step:
   def step_N_type(inputs, context):
       '''Docstring matching step name from skill.yaml.'''
       # ... implementation ...
       return {{"output": value}}, None    # success
       return None, "error message"         # failure

   RULES for handlers:
   - Take (inputs, context) as arguments — ALWAYS
   - Return (result_dict, None) on success — result_dict MUST have "output" key
   - Return (None, error_string) on failure
   - LLM steps: build messages as LIST OF DICTS, then:
       content, error = call_resolved(messages, context, max_tokens=N)
       if error:
           content, error = call_openai(messages, model="gpt-5.4-mini", max_tokens=N)
       if error:
           return None, error
     The fallback to call_openai is the standard resilience pattern.
   - Critic steps: return {{"output": {{"quality_score": N, ...}}}}
     Scoring: quality_score = min(structural_score, llm_dim1, llm_dim2) — NEVER weighted avg
   - Local steps: NEVER call call_resolved or any LLM function
   - Final step: return {{"output": "artifact_written"}} — runner handles file writing

   CONTEXT ACCESS:
   - Previous step output: context.get("output_key_from_previous_step", "")
   - Resolved input: context.get("_resolved_input", "")
   - Step 1 output: context.get("step_1_output", {{}})
   - Inputs: inputs.get("field_name", "")
   - Resolved model: context.get("resolved_model", "")
   - Resolved provider: context.get("resolved_provider", "")

7. STEP_HANDLERS DICT — maps every step_id to its handler function:
   STEP_HANDLERS = {{
       "step_1": step_1_local,
       "step_2": step_2_llm,
       ...
   }}

8. __main__ BLOCK — EXACT PATTERN:
   if __name__ == "__main__":
       parser = argparse.ArgumentParser()
       parser.add_argument("--step", required=True)
       parser.add_argument("--input", required=True)
       a = parser.parse_args()
       with open(a.input) as f:
           spec = json.load(f)
       h = STEP_HANDLERS.get(spec["step_id"])
       if not h:
           print(json.dumps({{"error": f"Unknown step: {{spec['step_id']}}"}}}))
           sys.exit(1)
       result, error = h(spec["inputs"], spec["context"])
       if error:
           print(json.dumps({{"error": error}}))
           sys.exit(1)
       print(json.dumps(result))



=== ESTABLISHED CODE CONVENTIONS (from 17 production skills) ===

EXTRACT_SECTION FUNCTION (for skills that parse markdown output):
  def extract_section(text, heading_keywords):
      for kw in heading_keywords:
          pattern = re.compile(
              rf'(?:^|\n)##\s[^\n]*{re.escape(kw)}[^\n]*\n(.*?)(?=\n##\s[^#]|\Z)',
              re.IGNORECASE | re.DOTALL)
          m = pattern.search(text)
          if m: return m.group(1).strip()
      return ""
  Uses ##\s (H2 only). NEVER ##? (matches H1). Preserves H3 subsections inside.

TOKEN BUDGET PATTERN (for skills with depth/length parameter):
  TOKEN_BUDGET = {"short": 4000, "standard": 8000, "long": 12000}
  Use the parameter value to select max_tokens for call_resolved().

SCORING PATTERN (critic steps):
  quality_score = min(structural_score, llm_dim1, llm_dim2)
  NEVER use weighted average. min() ensures no dimension masks another.

LLM CALL PATTERN (every LLM/critic step):
  messages = [
      {"role": "system", "content": system_prompt},
      {"role": "user", "content": user_prompt},
  ]
  content, error = call_resolved(messages, context, max_tokens=6000)
  if error:
      content, error = call_openai(messages, model="gpt-5.4-mini", max_tokens=6000)
  if error:
      return None, error
  ALWAYS use dict messages. ALWAYS unpack tuple. ALWAYS fallback to openai.

CRITIC JSON PARSING PATTERN:
  Strip markdown fences before parsing LLM JSON response:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
        cleaned = re.sub(r'\s*```$', '', cleaned)
    scores = json.loads(cleaned)

STEP 5 RETURN:
  return {"output": "artifact_written"}, None
  The runner handles file writing. Step 5 only validates and signals.

CONTEXT ACCESS — CRITICAL RULES:
  Step 1 output: context.get("step_1_output", {})
  Step 2 output: context.get("<step_2_output_key>", "")  — use the EXACT output_key from skill.yaml
  Step 3 output: context.get("step_3_output", {})
  Improved output: context.get("<step_4_output_key>", context.get("<step_2_output_key>", ""))

  CRITICAL: The context key MUST match the output_key in skill.yaml EXACTLY.
  If skill.yaml says output_key: generated_scope, the code MUST use context.get("generated_scope")
  If skill.yaml says output_key: generated_validation, the code MUST use context.get("generated_validation")
  NEVER use generic names like step_2_output or step_4_output — read the actual output_key values.

  Pattern for step_3 (critic) getting step_2's output:
    output_key_from_yaml = "<whatever step_2's output_key is>"
    text = context.get("improved_<noun>", context.get("<output_key_from_yaml>", ""))

  Pattern for step_5 getting best output:
    improved = context.get("<step_4_output_key>", "")
    generated = context.get("<step_2_output_key>", "")
    final = improved if improved else generated

=== CRITICAL: CODE COMPLETENESS RULES ===

Your code MUST always end with these two blocks — they are NOT optional:

1. STEP_HANDLERS dict mapping every step_id to its handler function
2. __main__ block with argparse, JSON load, handler dispatch, and sys.exit

If your code does not end with these, the skill WILL fail validation.
Write the handler implementations first, then ALWAYS finish with:

STEP_HANDLERS = {
    "step_1": step_1_local,
    "step_2": step_2_llm,
    ...map every step...
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

Budget your code to leave room for these blocks. If you are running long,
SHORTEN the handler implementations rather than omitting STEP_HANDLERS or __main__.

=== ABSOLUTELY FORBIDDEN ===
- Inventing helper functions not in the reference architecture
- Creating new context keys beyond what skill.yaml declares
- Alternate envelope or artifact writing (runner owns this)
- Custom state management or persistence
- New import patterns or utility layers
- Abstract base classes or inheritance hierarchies
- Decorator patterns on step handlers
- Global mutable state beyond constants
- Using result = call_resolved(...) — MUST use content, error = call_resolved(...)
- Using tuple messages like ("system", "prompt") — MUST use {"role": "system", "content": "prompt"}
- Using weighted average for quality_score — MUST use min()
- Omitting fallback call_openai after call_resolved failure
- Using context.get("step_2_output") or context.get("step_4_output") — MUST use the actual output_key from skill.yaml
- Setting cached: true on step_3 or step_4 in critic loops — caching breaks loop counter, causes infinite loops
"""


def step_2_llm(inputs, context):
    """Generate architecture-aligned run.py implementation."""
    classification = context.get("step_1_output", context.get("_resolved_input", {}))
    if not classification or not isinstance(classification, dict):
        return None, "No classification from step 1"

    skill_id = classification.get("skill_id", "")
    skill_name = classification.get("skill_name", "")
    version = classification.get("version", "1.0.0")
    tag = classification.get("tag", "internal")
    skill_type = classification.get("skill_type", "executor")
    description = classification.get("description", "")
    execution_role = classification.get("execution_role", "")
    has_critic = classification.get("has_critic_loop", False)
    det_type = classification.get("deterministic_check_type", "none")
    step_classes = classification.get("step_classifications", [])
    skill_inputs = classification.get("skill_inputs", [])
    contracts = classification.get("contracts", {})
    raw_yaml = classification.get("raw_yaml", "")

    # Build step summary for the prompt
    # Build output_key map for context access rules
    output_key_map = {}
    for sc in step_classes:
        output_key_map[sc['step_id']] = sc.get('output_key', sc['step_id'] + '_output')

    step_summary = []
    for sc in step_classes:
        ok = sc.get('output_key', sc['step_id'] + '_output')
        step_summary.append(
            f"  {sc['step_id']}: type={sc['step_type']}, handler={sc['handler_type']}, "
            f"output_key={ok}, calls_llm={sc['calls_llm']}, "
            f"is_final={sc['is_final_step']}\n"
            f"    name: {sc['step_name']}\n"
            f"    desc: {sc['step_description'][:200]}")
    step_block = "\n".join(step_summary)

    # Build output_key instruction for context access
    ok_instruction = "\nCONTEXT KEY MAP (use these EXACT keys in context.get()):\n"
    for sid, ok in output_key_map.items():
        ok_instruction += f"  {sid} -> context.get(\"{ok}\")\n"
    ok_instruction += "NEVER use step_2_output or step_4_output — use the exact keys above.\n" 

    # Input fields summary
    input_summary = "\n".join(
        f"  - {inp.get('name', '?')} ({inp.get('type', 'string')}, "
        f"{'required' if inp.get('required') else 'optional'}): {inp.get('description', '')[:100]}"
        for inp in skill_inputs)

    det_instruction = ""
    if det_type == "numeric":
        det_instruction = """
DETERMINISTIC CHECKS REQUIRED: numeric
Generate extract_numeric_tokens() and check_numeric_preservation() functions
following the F35 Tone Calibrator pattern. These extract currency values,
percentages, dates, and numbers from text and verify they are preserved
exactly in the output. The critic step should run this check BEFORE the
LLM evaluation and hard-cap scores on violation. The final step should
hard-fail if numeric integrity is violated."""
    elif det_type == "structural":
        det_instruction = """
DETERMINISTIC CHECKS REQUIRED: structural
Generate functions to check paragraph count, heading preservation, bullet/list
structure, and CTA position preservation between input and output text."""
    elif det_type == "schema":
        det_instruction = """
DETERMINISTIC CHECKS REQUIRED: schema
Generate functions to validate that the output is valid JSON or YAML with
required fields present. Parse deterministically before LLM evaluation."""
    elif det_type == "custom":
        det_instruction = """
DETERMINISTIC CHECKS REQUIRED: custom
Generate placeholder functions with clear TODO markers for manual implementation
of domain-specific deterministic validation."""

    system = f"""{REFERENCE_ARCHITECTURE}

You are generating a run.py for this skill:

SKILL ID: {skill_id}
DISPLAY NAME: {skill_name}
VERSION: {version}
TAG: {tag}
SKILL TYPE: {skill_type}
HAS CRITIC LOOP: {has_critic}

DESCRIPTION: {description}

EXECUTION ROLE: {execution_role}

STEP CLASSIFICATIONS:
{step_block}

INPUT FIELDS:
{input_summary}
{det_instruction}

GENERATION RULES:
1. Output ONLY valid Python code. No markdown fences. No explanations.
   Start directly with the shebang line: #!/usr/bin/env python3
2. Follow the reference architecture EXACTLY — do not invent new patterns.
3. Every step_id in the classification MUST have a handler function.
4. LLM steps MUST use call_resolved(). Local steps MUST NOT.
5. Critic steps MUST return structured JSON with quality_score.
6. Final step MUST return {{"output": "artifact_written"}}.
7. Write meaningful, tailored prompts for LLM steps — not generic stubs.
8. Use the execution_role as the system prompt foundation for LLM steps.
"""

    user_msg = f"""Generate the complete run.py for skill '{skill_id}'.
{ok_instruction}

SKILL.YAML for reference:
{raw_yaml[:4000]}

Output ONLY the raw Python code starting with #!/usr/bin/env python3"""

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_msg},
    ]

    content, error = call_resolved(messages, context, max_tokens=20000)
    if error:
        content, error = call_openai(messages, model="gpt-5.4-mini", max_tokens=20000)
    if error:
        return None, error

    content = strip_code_fences(content)
    return {"output": content}, None


def step_3_critic(inputs, context):
    """Two-layer validation: deterministic then LLM."""
    code = context.get("improved_code", context.get("generated_code",
           context.get("step_2_output", "")))
    if isinstance(code, dict):
        code = str(code)
    if not code:
        return None, "No code to validate"

    classification = context.get("step_1_output", {})
    step_classes = classification.get("step_classifications", [])

    # ── Layer 1: Deterministic validation ─────────────────────────────────
    cleaned = strip_code_fences(code)
    det_issues, compile_ok = deterministic_validate_code(cleaned, step_classes)

    if not compile_ok:
        return {"output": {
            "quality_score": 1,
            "structural_score": 0,
            "prompt_quality_score": 0,
            "completeness_score": 0,
            "deterministic_issues": det_issues,
            "llm_feedback": "Python compilation failed — cannot evaluate further",
            "feedback": f"CRITICAL: {det_issues[0]}. Fix syntax first.",
        }}, None

    det_penalty = len(det_issues)
    structural_score = max(0, 10 - (det_penalty * 2))

    # ── Layer 2: LLM quality evaluation ───────────────────────────────────
    system = """You are a strict NemoClaw run.py code reviewer. You receive generated
Python code for a skill and evaluate its QUALITY beyond structural correctness.

Score these dimensions (each 0-10):

- prompt_quality_score: For LLM steps, are the system prompts specific,
  well-structured, and tailored to the skill's purpose? Do they provide
  clear instructions? Do they include relevant constraints?

- completeness_score: Does every handler have meaningful implementation?
  Are edge cases handled? Is input validation present? Are error messages
  descriptive?

Respond with JSON ONLY — no markdown, no backticks, no explanation:
{"prompt_quality_score": N, "completeness_score": N, "llm_feedback": "Specific actionable notes"}"""

    user = f"""GENERATED RUN.PY:
{cleaned[:6000]}

SKILL DESCRIPTION: {classification.get('description', 'Unknown')}

Evaluate prompt quality and implementation completeness."""

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    content, error = call_resolved(messages, context, max_tokens=1500)
    if error:
        content, error = call_openai(messages, model="gpt-5.4-mini", max_tokens=1500)

    llm_scores = {"prompt_quality_score": 5, "completeness_score": 5, "llm_feedback": ""}
    if not error and content:
        try:
            llm_cleaned = content.strip()
            if llm_cleaned.startswith("```"):
                llm_cleaned = re.sub(r'^```(?:json)?\s*', '', llm_cleaned)
                llm_cleaned = re.sub(r'\s*```$', '', llm_cleaned)
            llm_scores = json.loads(llm_cleaned)
        except (json.JSONDecodeError, TypeError):
            llm_scores["llm_feedback"] = content

    prompt_q = llm_scores.get("prompt_quality_score", 5)
    completeness = llm_scores.get("completeness_score", 5)
    quality_score = min(structural_score, prompt_q, completeness)

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
        "prompt_quality_score": prompt_q,
        "completeness_score": completeness,
        "deterministic_issues": det_issues,
        "llm_feedback": llm_fb,
        "feedback": " || ".join(feedback_parts) if feedback_parts else "All checks passed",
    }}, None


def step_4_llm(inputs, context):
    """Fix code issues based on critic feedback."""
    classification = context.get("step_1_output", {})
    raw_yaml = classification.get("raw_yaml", "")

    code = context.get("improved_code", context.get("generated_code",
           context.get("step_2_output", "")))
    if isinstance(code, dict):
        code = str(code)

    critic = context.get("step_3_output", {})
    if isinstance(critic, str):
        try:
            critic = json.loads(critic)
        except (json.JSONDecodeError, TypeError):
            critic = {"feedback": critic}

    feedback = critic.get("feedback", "No specific feedback")
    det_issues = critic.get("deterministic_issues", [])
    structural = critic.get("structural_score", "?")
    prompt_q = critic.get("prompt_quality_score", "?")
    completeness = critic.get("completeness_score", "?")

    det_section = ""
    if det_issues:
        det_section = "\nCRITICAL STRUCTURAL ISSUES TO FIX:\n" + "\n".join(
            f"  - {issue}" for issue in det_issues)

    system = f"""{REFERENCE_ARCHITECTURE}

You are fixing a run.py that has violations.

FIX RULES:
1. Output ONLY the corrected Python code. No markdown fences. No explanations.
   Start directly with #!/usr/bin/env python3
2. Fix ALL structural issues first — these are critical.
3. Then address quality feedback on prompts and completeness.
4. Do NOT invent new patterns. Follow the reference architecture exactly.
5. Preserve the overall structure and intent of the original code.
{det_section}"""

    user = f"""CURRENT CODE WITH VIOLATIONS:
{strip_code_fences(code)}

CRITIC FEEDBACK: {feedback}
SCORES: structural={structural}/10 | prompt_quality={prompt_q}/10 | completeness={completeness}/10

SKILL.YAML (for reference):
{raw_yaml[:3000]}

Fix all issues and output ONLY the corrected raw Python starting with #!/usr/bin/env python3"""

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    content, error = call_resolved(messages, context, max_tokens=20000)
    if error:
        content, error = call_openai(messages, model="gpt-5.4-mini", max_tokens=20000)
    if error:
        return None, error

    content = strip_code_fences(content)
    return {"output": content}, None


def _select_best_output(context):
    """Latest surviving candidate after critic loop."""
    for key in ("improved_code", "generated_code", "step_2_output"):
        v = context.get(key, "")
        if v and isinstance(v, str) and v.strip():
            return v
    return context.get("generated_code", "")


def step_5_write(inputs, context):
    """Full validation gate — hard-fail on any structural issue."""
    best = _select_best_output(context)
    if isinstance(best, dict):
        best = str(best)

    if not best or not best.strip():
        return None, "No code output to write"

    cleaned = strip_code_fences(best)
    classification = context.get("step_1_output", {})
    step_classes = classification.get("step_classifications", [])

    det_issues, compile_ok = deterministic_validate_code(cleaned, step_classes)

    if not compile_ok:
        return None, f"PYTHON COMPILE FAILURE: {det_issues[0]}"

    if det_issues:
        summary = "; ".join(det_issues[:5])
        count = len(det_issues)
        return None, f"CODE INTEGRITY FAILURE — {count} issue(s) in final output: {summary}"

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
