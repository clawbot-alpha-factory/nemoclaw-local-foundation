#!/usr/bin/env python3
"""
NemoClaw Skill Template Generator v2.0.0
Phase 13 — Generates v2 skill.yaml, run.py, README.md boilerplate.

Enforces: zero-padded families, step_type (no makes_llm_call),
success_conditions, transitions, critic_loop, observability,
contracts, semantic step naming.

Usage:
    python3 scripts/new-skill.py \\
      --id h35-tone-calibrator \\
      --name "Tone Calibrator" \\
      --family 35 --domain H --tag customer-facing \\
      --skill-type transformer \\
      --step-names "Parse input and analyze tone,Rewrite text in target tone,Evaluate tone quality,Improve based on feedback,Validate and write artifact" \\
      --llm-steps "2,3,4" --critic-steps "3"
"""

import argparse
import os
import re
import sys
from datetime import datetime, timezone

REPO_BASE  = os.path.expanduser("~/nemoclaw-local-foundation")
SKILLS_DIR = os.path.join(REPO_BASE, "skills")

TAG_DEFAULTS = {
    "internal":        {"llm": "moderate",          "non_llm": "general_short"},
    "customer-facing": {"llm": "premium",           "non_llm": "general_short"},
    "dual-use":        {"llm": "complex_reasoning", "non_llm": "general_short"},
}

BANNED = [
    r"(?i)\btodo\b", r"(?i)\bllm step\b", r"(?i)\bprocessing step\b",
    r"(?i)\bprocess input\b", r"(?i)\bhandle data\b", r"(?i)\bdo work\b",
    r"(?i)\brun model\b", r"(?i)^step \d+$",
]


def parse_set(s, total):
    if not s: return set()
    try:
        out = set()
        for x in s.split(","):
            n = int(x.strip())
            if n < 1 or n > total: return None
            out.add(n)
        return out
    except ValueError:
        return None


def validate(args, names, llm, critic):
    errs = []
    if not args.id or len(args.id) < 5:
        errs.append("--id must be ≥5 chars")
    if args.id and args.id[0].upper() not in "ABCDEFGHIJKL":
        errs.append(f"--id domain '{args.id[0]}' not a-l")
    if not args.family or len(args.family) != 2 or not args.family.isdigit():
        errs.append("--family must be zero-padded 2 digits")
    if args.domain.upper() not in "ABCDEFGHIJKL":
        errs.append("--domain must be A-L")
    if len(names) < 2:
        errs.append("Need ≥2 step names")
    if llm is None:
        errs.append("--llm-steps invalid")
    if critic is None:
        errs.append("--critic-steps invalid")
    if critic and llm and not critic.issubset(llm):
        errs.append("--critic-steps must be subset of --llm-steps")
    for i, nm in enumerate(names, 1):
        for pat in BANNED:
            if re.search(pat, nm):
                errs.append(f"Step {i} '{nm}' matches banned pattern")
        if len(nm.split()) < 3:
            errs.append(f"Step {i} '{nm}' needs ≥3 words (verb + object + context)")
    if os.path.exists(os.path.join(SKILLS_DIR, args.id)):
        errs.append(f"skills/{args.id}/ already exists")
    return errs


# ── YAML Generator ────────────────────────────────────────────────────────────
def gen_yaml(args, names, llm, critic):
    tc = TAG_DEFAULTS[args.tag]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    n = len(names)
    L = []

    # Identity
    L += [f"name: {args.id}", f"version: 1.0.0",
          f'display_name: "{args.name}"',
          f"description: >", f"  TODO: Describe what {args.name} does (min 20 chars).",
          f"author: Core88", f"created: {now}", ""]

    # Classification
    L += [f"family: F{args.family}", f"domain: {args.domain.upper()}",
          f"tag: {args.tag}", f"skill_type: {args.skill_type}", ""]

    # Compat
    L += ["schema_version: 2", 'runner_version_required: ">=4.0.0"',
          'routing_system_version_required: ">=3.0.0"',
          "max_loop_iterations: 3", ""]

    # Context
    L += ["context_requirements:", "  - workflow_id", "  - budget_state",
          "  - step_history", "",
          "execution_role: >",
          "  TODO: Define the agent persona for this skill.", ""]

    # Inputs
    L += ["inputs:", "  - name: input_text", "    type: string",
          "    required: true", '    description: "TODO: primary input"',
          "    validation:", "      min_length: 10", "      max_length: 10000", ""]

    # Outputs
    L += ["outputs:", "  - name: result", "    type: string",
          '    description: "TODO: primary output"',
          "  - name: result_file", "    type: file_path",
          "    description: Path to artifact",
          "  - name: envelope_file", "    type: file_path",
          "    description: Path to JSON envelope", ""]

    # Artifacts
    L += ["artifacts:",
          f"  storage_location: skills/{args.id}/outputs/",
          f'  filename_pattern: "{args.id}_{{workflow_id}}_{{timestamp}}.md"',
          f'  envelope_pattern: "{args.id}_{{workflow_id}}_{{timestamp}}_envelope.json"',
          "  format: markdown", "  committed_to_repo: false",
          "  gitignored: true", ""]

    # Steps
    L.append("steps:")
    for i in range(1, n + 1):
        is_critic = i in critic
        is_llm = i in llm and not is_critic
        is_last = i == n
        st = "critic" if is_critic else ("llm" if is_llm else "local")
        task = tc["llm"] if st in ("llm", "critic") else tc["non_llm"]
        okey = "artifact_path" if is_last else f"step_{i}_output"
        isrc = "inputs.input_text" if i == 1 else ("__final_output__" if is_last else f"step_{i-1}.output")

        L += [f"  - id: step_{i}", f'    name: "{names[i-1]}"',
              f"    step_type: {st}", f"    task_class: {task}",
              f'    description: "TODO: what step {i} does"',
              f"    input_source: {isrc}", f"    output_key: {okey}",
              "    idempotency:",
              f"      rerunnable: {'false' if is_last else 'true'}",
              f"      cached: {'true' if st in ('llm','critic') else 'false'}",
              f"      never_auto_rerun: {'true' if is_last else 'false'}",
              "    requires_human_approval: false",
              "    failure:", "      success_conditions:",
              f'        - left: "{okey}"', '          op: "not_empty"',
              "          right: true"]
        if st in ("llm", "critic") and not is_last:
            L += [f'        - left: "{okey}.length"', '          op: ">="',
                  "          right: 50"]
        L += [f"      strategy: {'retry' if st in ('llm','critic') else 'halt'}",
              f"      retry_count: {2 if st in ('llm','critic') else 0}",
              "      fallback_step: null",
              f'      escalation_message: "TODO: failure message for step {i}"']

        # Transition
        if is_last:
            L += ["    transition:", "      default: __end__", ""]
        else:
            L += ["    transition:", f"      default: step_{i+1}", ""]

    # Final output
    llm_keys = [f"step_{i}_output" for i in sorted(llm) if i < n]
    if llm_keys:
        L += ["final_output:", "  select: latest", "  candidates:"]
        for k in llm_keys:
            sn = k.split("_")[1]
            L += [f"    - key: {k}", f"      from_step: step_{sn}",
                  "      score_from: null"]
        L += [f"  fallback: {llm_keys[0]}", ""]

    # Critic loop
    if critic:
        cs = min(critic)
        gen_cands = [s for s in llm if s < cs and s not in critic]
        gs = max(gen_cands) if gen_cands else cs - 1
        imp_cands = [s for s in llm if s > cs and s not in critic]
        imp = min(imp_cands) if imp_cands else cs + 1
        L += ["critic_loop:", "  enabled: true",
              f"  generator_step: step_{gs}", f"  critic_step: step_{cs}",
              f"  improve_step: step_{imp}",
              f"  score_field: step_{cs}_output.quality_score",
              "  acceptance_score: 7", "  max_improvements: 2",
              "  counter_name: critic_loop",
              f"  fallback_final_step: step_{n}", ""]
    else:
        L += ["critic_loop:", "  enabled: false", ""]

    # Observability
    L += ["observability:", "  log_level: detailed", "  track_cost: true",
          "  track_latency: true", "  track_tokens: true",
          f"  track_quality: {'true' if critic else 'false'}",
          '  metrics_file: "~/.nemoclaw/logs/skill-metrics.jsonl"', ""]

    # Contracts
    L += ["contracts:", "  machine_validated:", "    output_format: markdown",
          "    required_fields:", "      - result",
          "    quality:", "      min_length: 100", "      max_length: 50000"]
    if critic:
        L.append("      min_quality_score: 7")
    L += ["    sla:", "      max_execution_seconds: 120",
          "      max_cost_usd: 0.15",
          "  declarative_guarantees:",
          '    - "TODO: Define quality guarantees"', ""]

    # Approval
    sl = ", ".join(f"step_{i}" for i in range(1, n + 1))
    L += ["approval_boundaries:", f"  safe_steps: [{sl}]",
          "  approval_gated_steps: []",
          "  blocked_external_effect_steps: []",
          "  notes: >", "    TODO: Update if any step has external effects.", ""]

    # Routing
    L += ["routing:", f"  default_alias: {tc['llm']}",
          "  allow_override: false", ""]

    # Composable
    L += ["composable:", '  output_type: "TODO: define output type"',
          "  can_feed_into: []", "  accepts_input_from: []"]

    return "\n".join(L) + "\n"


# ── run.py Generator ──────────────────────────────────────────────────────────
def gen_run(args, names, llm, critic):
    n = len(names)
    L = ['#!/usr/bin/env python3', '"""',
         f'NemoClaw Skill: {args.id}', f'{args.name}',
         f'F{args.family} | {args.domain.upper()} | {args.tag} | {args.skill_type}',
         'Schema v2 | Runner v4.0+', '"""', '',
         'import argparse, json, os, sys',
         'from datetime import datetime, timezone', '', '',
         'def load_env():',
         '    p = os.path.expanduser("~/nemoclaw-local-foundation/config/.env")',
         '    k = {}',
         '    if os.path.exists(p):',
         '        with open(p) as f:',
         '            for ln in f:',
         '                ln = ln.strip()',
         '                if "=" in ln and not ln.startswith("#"):',
         '                    a, b = ln.split("=", 1)',
         '                    k[a.strip()] = b.strip()',
         '    return k', '', '',
         'def call_openai(messages, model="gpt-5.4-mini", max_tokens=4000):',
         '    from langchain_openai import ChatOpenAI',
         '    from langchain_core.messages import HumanMessage, SystemMessage',
         '    env = load_env()',
         '    key = env.get("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", ""))',
         '    if not key: return None, "OPENAI_API_KEY not found"',
         '    llm = ChatOpenAI(model=model, api_key=key, max_tokens=max_tokens, temperature=0.3)',
         '    lc = [SystemMessage(content=m["content"]) if m["role"] == "system" else HumanMessage(content=m["content"]) for m in messages]',
         '    return llm.invoke(lc).content, None', '', '',
         'def call_anthropic(messages, model="claude-sonnet-4-6", max_tokens=4000):',
         '    from langchain_anthropic import ChatAnthropic',
         '    from langchain_core.messages import HumanMessage, SystemMessage',
         '    env = load_env()',
         '    key = env.get("ANTHROPIC_API_KEY", os.environ.get("ANTHROPIC_API_KEY", ""))',
         '    if not key: return None, "ANTHROPIC_API_KEY not found"',
         '    llm = ChatAnthropic(model=model, api_key=key, max_tokens=max_tokens, temperature=0.3)',
         '    lc = [SystemMessage(content=m["content"]) if m["role"] == "system" else HumanMessage(content=m["content"]) for m in messages]',
         '    return llm.invoke(lc).content, None', '', '',
         'def call_google(messages, model="gemini-2.5-flash", max_tokens=4000):',
         '    from langchain_google_genai import ChatGoogleGenerativeAI',
         '    from langchain_core.messages import HumanMessage, SystemMessage',
         '    env = load_env()',
         '    key = env.get("GOOGLE_API_KEY", os.environ.get("GOOGLE_API_KEY", ""))',
         '    if not key: return None, "GOOGLE_API_KEY not found"',
         '    llm = ChatGoogleGenerativeAI(model=model, google_api_key=key, max_tokens=max_tokens)',
         '    lc = [SystemMessage(content=m["content"]) if m["role"] == "system" else HumanMessage(content=m["content"]) for m in messages]',
         '    return llm.invoke(lc).content, None', '', '',
         'def call_resolved(messages, context, max_tokens=4000):',
         '    m = context.get("resolved_model", "")',
         '    p = context.get("resolved_provider", "anthropic")',
         '    if p == "google": return call_google(messages, model=m or "gemini-2.5-flash", max_tokens=max_tokens)',
         '    if p == "openai": return call_openai(messages, model=m or "gpt-5.4-mini", max_tokens=max_tokens)',
         '    return call_anthropic(messages, model=m or "claude-sonnet-4-6", max_tokens=max_tokens)',
         '', '']

    for i in range(1, n + 1):
        is_critic = i in critic
        is_llm = i in llm and not is_critic
        is_last = i == n
        sn = names[i - 1]

        if is_last:
            L += [f'def step_{i}_write(inputs, context):',
                  f'    """Artifact writing handled by skill-runner.py v4.0."""',
                  f'    return {{"output": "artifact_written"}}, None', '', '']
        elif is_critic:
            L += [f'def step_{i}_critic(inputs, context):',
                  f'    """{sn}"""',
                  f'    prev = context.get("step_{i-1}_output", "")',
                  f'    if not prev: return None, "No input from step_{i-1}"',
                  f'    role = context.get("execution_role", "You are a quality evaluator.")',
                  f'    messages = [',
                  f'        {{"role": "system", "content": f"{{role}}\\nEvaluate quality. Respond JSON only: {{\\\"quality_score\\\": N, \\\"feedback\\\": \\\"...\\\"}} where N is 0-10."}},',
                  f'        {{"role": "user", "content": f"Evaluate:\\n\\n{{prev}}"}},',
                  f'    ]',
                  f'    content, error = call_resolved(messages, context, 1000)',
                  f'    if error: content, error = call_openai(messages, model="gpt-5.4-mini", max_tokens=1000)',
                  f'    if error: return None, error',
                  f'    try:',
                  f'        return {{"output": json.loads(content)}}, None',
                  f'    except (json.JSONDecodeError, TypeError):',
                  f'        return {{"output": {{"quality_score": 5, "feedback": content}}}}, None',
                  '', '']
        elif is_llm:
            L += [f'def step_{i}_llm(inputs, context):',
                  f'    """{sn}"""']
            if i == 1:
                L += [f'    text = inputs.get("input_text", "").strip()',
                      f'    if not text or len(text) < 10: return None, "Input too short"',
                      f'    prev = text']
            else:
                L += [f'    prev = context.get("step_{i-1}_output", "")',
                      f'    if not prev: return None, "No input from step_{i-1}"']
            L += [f'    role = context.get("execution_role", "")',
                  f'    messages = [',
                  f'        {{"role": "system", "content": role or "TODO: system prompt for {sn}"}},',
                  f'        {{"role": "user", "content": f"{{prev}}\\n\\nTODO: user prompt for {sn}"}},',
                  f'    ]',
                  f'    content, error = call_resolved(messages, context, 4000)',
                  f'    if error: content, error = call_openai(messages, model="gpt-5.4-mini", max_tokens=4000)',
                  f'    if error: return None, error',
                  f'    return {{"output": content}}, None', '', '']
        else:
            L += [f'def step_{i}_local(inputs, context):',
                  f'    """{sn}"""']
            if i == 1:
                L += [f'    text = inputs.get("input_text", "").strip()',
                      f'    if not text or len(text) < 10: return None, "Input too short"',
                      f'    return {{"output": text}}, None']
            else:
                L += [f'    prev = context.get("step_{i-1}_output", "")',
                      f'    if not prev: return None, "No input from step_{i-1}"',
                      f'    # TODO: implement {sn}',
                      f'    return {{"output": prev}}, None']
            L += ['', '']

    # Handler map
    L.append('STEP_HANDLERS = {')
    for i in range(1, n + 1):
        is_critic = i in critic
        is_llm = i in llm and not is_critic
        is_last = i == n
        if is_last:     h = f'step_{i}_write'
        elif is_critic: h = f'step_{i}_critic'
        elif is_llm:    h = f'step_{i}_llm'
        else:           h = f'step_{i}_local'
        L.append(f'    "step_{i}": {h},')
    L += ['}', '', '',
          'if __name__ == "__main__":',
          '    parser = argparse.ArgumentParser()',
          '    parser.add_argument("--step", required=True)',
          '    parser.add_argument("--input", required=True)',
          '    a = parser.parse_args()',
          '    with open(a.input) as f: spec = json.load(f)',
          '    h = STEP_HANDLERS.get(spec["step_id"])',
          '    if not h:',
          "        print(json.dumps({\"error\": f\"Unknown step: {spec['step_id']}\"}))",
          '        sys.exit(1)',
          '    result, error = h(spec["inputs"], spec["context"])',
          '    if error:',
          '        print(json.dumps({"error": error}))',
          '        sys.exit(1)',
          '    print(json.dumps(result))']
    return "\n".join(L) + "\n"


# ── README Generator ──────────────────────────────────────────────────────────
def gen_readme(args, names, llm, critic):
    tc = TAG_DEFAULTS[args.tag]
    n = len(names)
    L = [f'# Skill: {args.id}', '',
         f'**Name:** {args.name}',
         f'**Version:** 1.0.0',
         f'**Family:** F{args.family} | **Domain:** {args.domain.upper()} | **Tag:** {args.tag}',
         f'**Type:** {args.skill_type} | **Schema:** v2 | **Runner:** v4.0+',
         f'**Status:** Boilerplate — implement prompts and test', '',
         '## What It Does', '',
         f'TODO: Describe what {args.name} does.', '',
         '## Usage', '', '```bash',
         '~/nemoclaw-local-foundation/.venv313/bin/python \\',
         '  ~/nemoclaw-local-foundation/skills/skill-runner.py \\',
         f'  --skill {args.id} \\',
         '  --input input_text "your input here"', '```', '',
         '## Steps', '',
         '| Step | Name | Type | Task Class |',
         '|---|---|---|---|']
    for i in range(1, n + 1):
        is_c = i in critic
        is_l = i in llm and not is_c
        st = "critic" if is_c else ("llm" if is_l else "local")
        tc_val = tc["llm"] if st in ("llm", "critic") else tc["non_llm"]
        L.append(f'| step_{i} | {names[i-1]} | {st} | {tc_val} |')
    L.append('')
    if critic:
        L += ['## Critic Loop', '',
              'Generate → evaluate → improve loop. Threshold: 8/10. Max improvements: 2.', '']
    L += ['## Resume', '', '```bash',
          '~/nemoclaw-local-foundation/.venv313/bin/python \\',
          '  ~/nemoclaw-local-foundation/skills/skill-runner.py \\',
          f'  --skill {args.id} --thread-id THREAD_ID --resume', '```', '',
          '## Docs', '',
          'See `docs/architecture/skill-yaml-schema-v2.md` and `docs/architecture/skill-build-plan.md`.']
    return "\n".join(L) + "\n"


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(description="NemoClaw Skill Template Generator v2.0")
    p.add_argument("--id", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--family", required=True)
    p.add_argument("--domain", required=True)
    p.add_argument("--tag", required=True, choices=list(TAG_DEFAULTS))
    p.add_argument("--skill-type", required=True,
                   choices=["executor", "planner", "evaluator", "transformer", "router"])
    p.add_argument("--step-names", required=True)
    p.add_argument("--llm-steps", default="")
    p.add_argument("--critic-steps", default="")
    args = p.parse_args()

    names = [n.strip() for n in args.step_names.split(",")]
    llm = parse_set(args.llm_steps, len(names))
    critic = parse_set(args.critic_steps, len(names)) if args.critic_steps else set()

    errs = validate(args, names, llm, critic)
    if errs:
        print("Validation errors:")
        for e in errs:
            print(f"  ✗ {e}")
        sys.exit(1)

    d = os.path.join(SKILLS_DIR, args.id)
    os.makedirs(os.path.join(d, "outputs"), exist_ok=True)

    for name, content in [
        ("skill.yaml", gen_yaml(args, names, llm, critic)),
        ("run.py",     gen_run(args, names, llm, critic)),
        ("README.md",  gen_readme(args, names, llm, critic)),
        ("outputs/.gitignore", "*\n!.gitignore\n"),
    ]:
        with open(os.path.join(d, name), "w") as f:
            f.write(content)
        print(f"  ✅ {name}")

    print(f"\nGenerated: skills/{args.id}/")
    print(f"  {args.name} | F{args.family} | {args.domain.upper()} | {args.tag} | {args.skill_type}")
    print(f"  {len(names)} steps: {len(llm)} LLM, {len(critic)} critic, {len(names)-len(llm)} local")
    print(f"\nNext: implement prompts in run.py → test → validate.py → commit")


if __name__ == "__main__":
    main()
