#!/usr/bin/env python3
"""
NemoClaw Skill Runner v4.0 — LangGraph + SqliteSaver
Phase 13: Skill Engine Upgrade.

Implements skill.yaml Schema v2:
- step_type dispatch (llm/critic → LLM call, local → no call)
- Transition engine with structured conditions (left/op/right)
- Critic loop support with loop counters
- Rich context: workflow_id, budget_state, step_history, execution_role
- Per-step metrics logged to skill-metrics.jsonl
- JSON envelope on completion (success and failure)
- --input-from for skill chaining with envelope validation
- success_conditions (required pass conditions per step)
- Failure escalation: retry → fallback → halt
- Final output selection (highest_quality, latest, specific)
- Contract validation (machine_validated)
- v1 backward compatibility via adapter
"""

import argparse
import json
import os
import subprocess
import sys
import time
import shutil
import uuid
from datetime import datetime, timezone
from typing import TypedDict, Annotated
import operator

import yaml
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver

SKILLS_DIR     = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR    = os.path.join(os.path.dirname(SKILLS_DIR), "scripts")
REPO_BASE      = os.path.dirname(SKILLS_DIR)
RUNNER_VERSION = "4.0.0"
CHECKPOINT_DB  = os.path.expanduser("~/.nemoclaw/checkpoints/langgraph.db")
METRICS_LOG    = os.path.expanduser("~/.nemoclaw/logs/skill-metrics.jsonl")
SPEND_FILE     = os.path.expanduser("~/.nemoclaw/logs/provider-spend.json")


# ── Shared State Schema ───────────────────────────────────────────────────────
class SkillState(TypedDict):
    skill_name:       str
    workflow_id:      str
    inputs:           dict
    context:          dict
    completed_steps:  Annotated[list, operator.add]
    step_history:     Annotated[list, operator.add]
    loop_counters:    dict
    artifact_path:    str
    error:            str
    status:           str


# ── v1 Compatibility Adapter ──────────────────────────────────────────────────
def adapt_v1_skill(skill):
    """Normalize v1 skill.yaml into v2 structure at load time."""
    if skill.get("schema_version", 1) >= 2:
        return skill

    print("  [compat] v1 skill — running in compatibility mode")

    skill.setdefault("skill_type", "executor")
    skill.setdefault("schema_version", 1)
    skill.setdefault("max_loop_iterations", 3)
    skill.setdefault("context_requirements", ["workflow_id", "budget_state"])
    skill.setdefault("execution_role", "")
    skill.setdefault("observability", {"log_level": "standard", "track_cost": True,
                                        "track_latency": True})
    skill.setdefault("contracts", {})
    skill.setdefault("final_output", None)
    skill.setdefault("critic_loop", {"enabled": False})

    for step in skill.get("steps", []):
        # Derive step_type from makes_llm_call (v1 field)
        if "step_type" not in step:
            step["step_type"] = "llm" if step.get("makes_llm_call", False) else "local"

        # Normalize failure block
        if "failure" not in step or isinstance(step.get("failure"), str):
            step["failure"] = {
                "success_conditions": [],
                "strategy": "halt",
                "retry_count": 0,
                "fallback_step": None,
                "escalation_message": f"Step {step['id']} failed",
            }

        # Normalize transition — sequential order
        if "transition" not in step:
            step["transition"] = {"default": None}

    # Wire sequential transitions for v1
    step_ids = [s["id"] for s in skill.get("steps", [])]
    for i, step in enumerate(skill["steps"]):
        if step["transition"].get("default") is None:
            step["transition"]["default"] = step_ids[i + 1] if i < len(step_ids) - 1 else "__end__"

    return skill


# ── Condition Evaluator ───────────────────────────────────────────────────────
def resolve_path(obj, path):
    """Resolve a dotted path. Check flat key first, then nested."""
    # Flat key check first (e.g., "rewritten_text.length" as literal key)
    if isinstance(obj, dict) and path in obj:
        return obj[path], True
    # Then try nested resolution
    parts = str(path).split(".")
    cur = obj
    for p in parts:
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
        else:
            return None, False
    return cur, True


def _try_numeric(val):
    if isinstance(val, (int, float)):
        return val, True
    try:
        return float(str(val)), True
    except (ValueError, TypeError):
        return val, False


def evaluate_condition(cond, context):
    """Evaluate a single {left, op, right} condition. Returns True if satisfied."""
    left_path = cond.get("left", "")
    oper = cond.get("op", "==")
    right = cond.get("right")

    left_val, found = resolve_path(context, left_path)
    if not found:
        return False

    if oper == "not_empty":
        if left_val is None:
            return False
        if isinstance(left_val, str) and left_val == "":
            return False
        if isinstance(left_val, (list, dict)) and len(left_val) == 0:
            return False
        return True

    if oper == "contains":
        if isinstance(left_val, str):
            return str(right) in left_val
        if isinstance(left_val, list):
            return right in left_val
        return False

    if oper in (">", ">=", "<", "<="):
        ln, lok = _try_numeric(left_val)
        rn, rok = _try_numeric(right)
        if not lok or not rok:
            return False
        if oper == ">":  return ln > rn
        if oper == ">=": return ln >= rn
        if oper == "<":  return ln < rn
        if oper == "<=": return ln <= rn

    if oper == "==":
        return str(left_val) == str(right) if not isinstance(left_val, type(right)) else left_val == right
    if oper == "!=":
        return str(left_val) != str(right) if not isinstance(left_val, type(right)) else left_val != right

    return False


def check_success_conditions(conditions, context):
    """All conditions must pass. Returns (passed, first_failure_msg)."""
    for c in (conditions or []):
        if not evaluate_condition(c, context):
            return False, f"Condition failed: {c.get('left','')} {c.get('op','')} {c.get('right','')}"
    return True, None


def evaluate_transition(transition, context):
    """Evaluate transition block. Returns next step_id or __end__."""
    for cond in transition.get("conditions", []):
        if evaluate_condition(cond, context):
            return cond.get("go_to", transition.get("default", "__end__"))
    return transition.get("default", "__end__")


# ── Context / Budget / Metrics ────────────────────────────────────────────────
def build_budget_state():
    if not os.path.exists(SPEND_FILE):
        return {}
    try:
        with open(SPEND_FILE) as f:
            spend = json.load(f)
        out = {}
        for prov, data in spend.items():
            cum = data.get("cumulative_spend_usd", 0)
            out[prov] = {"spend": round(cum, 4), "remaining": round(10.0 - cum, 4),
                         "pct_used": round(cum / 10.0, 4)}
        return out
    except Exception:
        return {}


def build_rich_context(skill, wf_id, inputs, prev_skills=None):
    return {
        "workflow_id": wf_id,
        "budget_state": build_budget_state(),
        "step_history": [],
        "execution_role": skill.get("execution_role", ""),
        "agent_id": skill.get("agent_id", ""),  # For browser autonomy layer
        "resolved_model": "",
        "resolved_provider": "",
        "previous_skills": prev_skills or [],
        "loop_counters": {},
    }


def log_step_metric(skill_id, wf_id, step, status, latency_ms,
                    cost=0, provider="", model="", quality=None,
                    iteration=1, attempt=1, fallback=False, parent_wf=None):
    os.makedirs(os.path.dirname(METRICS_LOG), exist_ok=True)
    rec = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": wf_id, "parent_workflow_id": parent_wf,
        "skill_id": skill_id,
        "step_id": step["id"], "step_name": step.get("name", step["id"]),
        "step_type": step.get("step_type", "local"),
        "step_iteration": iteration, "attempt_number": attempt,
        "status": status, "latency_ms": latency_ms,
        "estimated_cost_usd": cost, "provider": provider, "model": model,
        "quality_score": quality, "fallback_used": fallback,
    }
    with open(METRICS_LOG, "a") as f:
        f.write(json.dumps(rec) + "\n")


# ── Envelope Writer ───────────────────────────────────────────────────────────
def _primary_output_key(skill, context):
    """Find the best output key for the envelope primary field."""
    fo = skill.get("final_output")
    if fo and fo.get("fallback"):
        return fo["fallback"]
    for k in ("validated_brief", "structured_brief", "result",
              "improved_text", "rewritten_text"):
        if k in context and context[k]:
            return k
    return "result"


def write_envelope(skill, wf_id, state, cost, latency_ms, llm_count,
                   critic_loops, quality, prov_breakdown):
    storage = os.path.join(REPO_BASE, skill["artifacts"]["storage_location"])
    os.makedirs(storage, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    fname = f"{skill['name']}_{wf_id}_{ts}_envelope.json"
    fpath = os.path.join(storage, fname)

    ctx = state.get("context", {})
    mc = skill.get("contracts", {}).get("machine_validated", {})
    cr = {}
    if mc:
        primary = str(ctx.get(_primary_output_key(skill, ctx), ""))
        q = mc.get("quality", {})
        sla = mc.get("sla", {})
        cr = {
            "output_format_met": True,
            "min_length_met": len(primary) >= q.get("min_length", 0),
            "min_quality_met": (quality >= q.get("min_quality_score", 0)
                                if quality is not None else True),
            "sla_time_met": (latency_ms / 1000 <= sla["max_execution_seconds"]
                             if "max_execution_seconds" in sla else True),
            "sla_cost_met": (cost <= sla["max_cost_usd"]
                             if "max_cost_usd" in sla else True),
        }

    env = {
        "schema_version": 2,
        "skill_id": skill["name"],
        "skill_version": skill.get("version", "1.0.0"),
        "skill_type": skill.get("skill_type", "executor"),
        "thread_id": wf_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": state.get("status", "complete"),
        "error": state.get("error") or None,
        "inputs": state.get("inputs", {}),
        "outputs": {
            "primary": str(ctx.get(_primary_output_key(skill, ctx), ""))[:5000],
            "sections": {},
            "artifact_path": state.get("artifact_path", ""),
        },
        "metrics": {
            "run_id": wf_id, "parent_workflow_id": None,
            "total_cost_usd": round(cost, 6),
            "total_latency_ms": latency_ms,
            "total_steps": len(state.get("completed_steps", [])),
            "llm_steps": llm_count,
            "critic_loops": critic_loops,
            "final_quality_score": quality,
            "provider_breakdown": prov_breakdown,
        },
        "contracts": {
            "machine_validated": cr,
            "declarative_guarantees": skill.get("contracts", {}).get(
                "declarative_guarantees", []),
        },
        "composable": skill.get("composable", {}),
    }
    with open(fpath, "w") as f:
        json.dump(env, f, indent=2)
    return fpath


def write_error_envelope(skill, wf_id, error_msg, cost, failed_step, steps_done):
    storage = os.path.join(REPO_BASE, skill["artifacts"]["storage_location"])
    os.makedirs(storage, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    fpath = os.path.join(storage, f"{skill['name']}_{wf_id}_{ts}_envelope.json")
    env = {
        "schema_version": 2, "skill_id": skill["name"],
        "status": "failed", "error": error_msg,
        "metrics": {"run_id": wf_id, "total_cost_usd": round(cost, 6),
                    "failed_at_step": failed_step,
                    "steps_completed": steps_done},
    }
    with open(fpath, "w") as f:
        json.dump(env, f, indent=2)
    return fpath


# ── Final Output Selector ─────────────────────────────────────────────────────
def select_final_output(skill, context):
    fo = skill.get("final_output")
    if not fo:
        for k in ("validated_brief", "structured_brief", "result"):
            if k in context and context[k]:
                return context[k]
        return ""

    policy = fo.get("select", "latest")
    candidates = fo.get("candidates", [])
    fallback_key = fo.get("fallback", "")

    if policy == "specific" or not candidates:
        return context.get(fallback_key, "")

    if policy == "latest":
        for cand in reversed(candidates):
            v = context.get(cand["key"], "")
            if v:
                return v
        return context.get(fallback_key, "")

    if policy == "highest_quality":
        best_val, best_score = None, -1
        for cand in candidates:
            v = context.get(cand["key"], "")
            if not v:
                continue
            sp = cand.get("score_from", "")
            if sp:
                score, found = resolve_path(context, sp)
                if found and score is not None:
                    try:
                        sn = float(score)
                    except (ValueError, TypeError):
                        continue
                    if sn > best_score:
                        best_score, best_val = sn, v
        return best_val if best_val is not None else context.get(fallback_key, "")

    return context.get(fallback_key, "")


# ── Upstream Envelope Loader ──────────────────────────────────────────────────
def load_upstream_envelope(path):
    if not os.path.exists(path):
        print(f"ERROR: Upstream envelope not found: {path}")
        sys.exit(1)
    with open(path) as f:
        env = json.load(f)
    if env.get("error") is not None:
        print(f"ERROR: Upstream skill failed — cannot chain from failed envelope.")
        print(f"  Skill: {env.get('skill_id', '?')}  Error: {env['error']}")
        sys.exit(1)
    return {
        "skill_id": env.get("skill_id", "unknown"),
        "output_type": env.get("composable", {}).get("output_type", ""),
        "status": env.get("status", "unknown"),
        "artifact_path": env.get("outputs", {}).get("artifact_path", ""),
        "primary_output_preview": str(env.get("outputs", {}).get("primary", ""))[:500],
        "quality_score": env.get("metrics", {}).get("final_quality_score"),
        "timestamp": env.get("timestamp", ""),
    }


# ── Existing Helpers (preserved from v3) ──────────────────────────────────────
def load_skill_yaml(skill_dir):
    with open(os.path.join(skill_dir, "skill.yaml")) as f:
        return yaml.safe_load(f)

def call_budget_enforcer(task_class):
    enforcer = os.path.join(SCRIPTS_DIR, "budget-enforcer.py")
    result = subprocess.run(
        [sys.executable, enforcer, "--task-class", task_class],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"Budget enforcer failed: {result.stderr.strip()}")
    data = json.loads(result.stdout)
    print(f"    [budget] alias={data['alias']} model={data['model']} "
          f"cost=${data['estimated_cost_usd']} remaining=${data['budget_remaining_usd']}")
    return data

def call_run_py(skill_dir, step_id, inputs, context):
    run_path = os.path.join(skill_dir, "run.py")
    spec = {"step_id": step_id, "inputs": inputs, "context": context}
    tmp = f"/tmp/nemoclaw_step_{step_id}.json"
    with open(tmp, "w") as f:
        json.dump(spec, f)
    result = subprocess.run(
        [sys.executable, run_path, "--step", step_id, "--input", tmp],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return None, result.stderr.strip() or result.stdout.strip()
    try:
        return json.loads(result.stdout), None
    except json.JSONDecodeError:
        return {"output": result.stdout.strip()}, None

def write_artifact(skill, workflow_id, content):
    storage = os.path.join(REPO_BASE, skill["artifacts"]["storage_location"])
    os.makedirs(storage, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    pattern = skill["artifacts"]["filename_pattern"]
    filename = (pattern
        .replace("{workflow_id}", workflow_id)
        .replace("{timestamp}", ts)
        .replace("{skill_name}", skill["name"]))
    filepath = os.path.join(storage, filename)
    with open(filepath, "w") as f:
        f.write(content)
    return filepath

def validate_inputs(skill, inputs):
    errors = []
    for field in skill.get("inputs", []):
        name = field["name"]
        required = field.get("required", True)
        value = inputs.get(name)
        if required and not value:
            errors.append(f"Missing required input: {name}")
            continue
        if not value:
            inputs[name] = field.get("default", "")
            continue
        rules = field.get("validation", {})
        if "min_length" in rules and len(str(value)) < rules["min_length"]:
            errors.append(f"Input '{name}' too short")
        if "max_length" in rules and len(str(value)) > rules["max_length"]:
            errors.append(f"Input '{name}' too long")
        if "allowed_values" in rules and str(value) not in [str(v) for v in rules["allowed_values"]]:
            errors.append(f"Input '{name}' must be one of: {rules['allowed_values']}")
    return errors, inputs

def validate_output_v1(skill, output_text):
    errors = []
    for rule in skill.get("validation", {}).get("output", []):
        r = rule["rule"]
        if "at least" in r and "characters" in r:
            min_len = int([x for x in r.split() if x.isdigit()][0])
            if len(output_text) < min_len:
                errors.append(f"Output too short: {len(output_text)} chars")
        if "contain" in r and "section" in r:
            section = r.split("contain ")[-1].replace(" section", "").strip()
            if section.lower() not in output_text.lower():
                errors.append(f"Missing section: {section}")
    return errors


def resolve_input_source(step, skill, inputs, context):
    """Resolve input_source from skill.yaml — replaces hardcoded prev step lookup."""
    src = step.get("input_source", "")

    if src.startswith("inputs."):
        field = src.split(".", 1)[1]
        return inputs.get(field, "")

    if src == "__final_output__":
        return select_final_output(skill, context)

    if "." in src:
        # e.g. "step_1.output" → look up step_1's output_key in context
        parts = src.split(".")
        base = parts[0]
        # Find the step with this id and get its output_key
        for s in skill.get("steps", []):
            if s["id"] == base:
                okey = s.get("output_key", base)
                if okey in context:
                    return context[okey]
                break
        # Direct path resolution as fallback
        val, found = resolve_path(context, src)
        if found:
            return val

    # Direct key lookup
    if src in context:
        return context[src]

    # v1 fallback: step_{N-1}_output pattern
    step_num = step["id"].replace("step_", "")
    try:
        prev_num = int(step_num) - 1
        if prev_num > 0:
            for key in (f"step_{prev_num}_output", "plan", "validated_brief", "structured_brief"):
                if key in context and context[key]:
                    return context[key]
    except ValueError:
        pass

    return ""


# ── Node Factory ──────────────────────────────────────────────────────────────
def make_node(skill, skill_dir, step):
    step_id     = step["id"]
    step_type   = step.get("step_type", "local")
    task_class  = step.get("task_class", "general_short")
    task_domain = step.get("task_domain", None)
    idm         = step.get("idempotency", {})
    failure     = step.get("failure", {})
    is_llm      = step_type in ("llm", "critic")

    def node_fn(state: SkillState) -> SkillState:
        context = state["context"].copy()
        inputs  = state["inputs"]
        counters = state.get("loop_counters", {}).copy()

        # ── Fix 7: Global loop guard ─────────────────────────────────────
        max_total = skill.get("max_loop_iterations", 3) * len(skill["steps"])
        total_executed = len(state.get("completed_steps", []))

        # Bail out if skill already failed from a previous step
        if state.get("status") == "failed":
            return {"completed_steps": [], "step_history": []}
        if total_executed > max_total:
            return {"status": "failed",
                    "error": f"Loop guard: {total_executed} steps exceeded max {max_total}",
                    "completed_steps": [], "step_history": []}

        # Idempotency
        if step_id in state["completed_steps"]:
            if idm.get("never_auto_rerun", False):
                print(f"  [skip] {step_id} — never_auto_rerun")
                return {"completed_steps": [], "step_history": []}
            if idm.get("cached", False):
                print(f"  [cached] {step_id}")
                return {"completed_steps": [], "step_history": []}
            if not idm.get("rerunnable", True):
                print(f"  [skip] {step_id} — not rerunnable")
                return {"completed_steps": [], "step_history": []}

        print(f"\n  [node] {step_id}: {step['name']}")
        t0 = time.time()

        # Approval gate
        if step.get("requires_human_approval", False):
            ans = input(f"  [approval] {step_id} requires approval. Proceed? (yes/no): ").strip().lower()
            if ans != "yes":
                return {"status": "paused_approval", "error": f"Approval declined at {step_id}",
                        "completed_steps": [], "step_history": []}

        # Budget enforcement — llm and critic step types only
        cost_usd, provider, model = 0, "", ""
        if is_llm:
            try:
                budget = call_budget_enforcer(task_class)
                context["last_budget"] = budget
                context["resolved_model"] = budget.get("model", "")
                context["resolved_provider"] = budget.get("provider", "")
                cost_usd = budget.get("estimated_cost_usd", 0)
                provider = budget.get("provider", "")
                model = budget.get("model", "")
            except RuntimeError as e:
                return {"status": "failed", "error": str(e),
                        "completed_steps": [], "step_history": []}

        # ── Chain routing: pass task_domain to run.py via context ─────────
        if task_domain:
            context["_task_domain"] = task_domain
            context["_task_class"] = task_class

        # ── Fix 1: Resolve input_source from skill.yaml ──────────────────
        resolved_input = resolve_input_source(step, skill, inputs, context)
        if resolved_input:
            context["_resolved_input"] = resolved_input

        # Execute with retry support
        max_retries = failure.get("retry_count", 0) if failure.get("strategy") == "retry" else 0
        output, error = None, None

        for attempt in range(1 + max_retries):
            if attempt > 0:
                print(f"    [retry] {step_id} attempt {attempt + 1}/{1 + max_retries}")

            output, error = call_run_py(skill_dir, step_id, inputs, context)
            if error or not output:
                if attempt < max_retries:
                    continue
                break

            # Check success_conditions
            out_key = step.get("output_key", step_id)
            out_val = output.get("output", "")
            test_ctx = {**context, out_key: out_val}
            if isinstance(out_val, str):
                test_ctx[f"{out_key}.length"] = len(out_val)
            elif isinstance(out_val, dict):
                # Flatten dict keys for condition checks
                for dk, dv in out_val.items():
                    test_ctx[f"{out_key}.{dk}"] = dv

            passed, fail_msg = check_success_conditions(
                failure.get("success_conditions", []), test_ctx)
            if passed:
                error = None
                break
            else:
                error = fail_msg
                if attempt < max_retries:
                    continue
                break

        latency_ms = int((time.time() - t0) * 1000)

        # Handle failure
        if error or not output:
            err_msg = f"Step {step_id}: {error}" if error else f"Step {step_id}: empty output"
            log_step_metric(skill["name"], state["workflow_id"], step, "failed",
                           latency_ms, cost_usd, provider, model, attempt=1 + max_retries)

            # ── Fix 3: Fallback uses _force_next_step ─────────────────────
            fb = failure.get("fallback_step")
            if fb and failure.get("strategy") in ("fallback", "retry"):
                print(f"    [fallback] {step_id} → {fb}")
                esc = failure.get("escalation_message", err_msg)
                print(f"    [escalation] {esc}")
                context["_force_next_step"] = fb
                return {"context": context, "completed_steps": [step_id],
                        "step_history": [{"step_id": step_id, "status": "fallback",
                                          "step_type": step_type,
                                          "latency_ms": latency_ms, "cost_usd": cost_usd}],
                        "status": "running", "error": ""}

            esc = failure.get("escalation_message", err_msg)
            print(f"    [halt] {esc}")
            return {"status": "failed", "error": err_msg,
                    "completed_steps": [], "step_history": [
                        {"step_id": step_id, "status": "failed",
                         "step_type": step_type,
                         "latency_ms": latency_ms, "cost_usd": cost_usd}]}

        # ── Step succeeded ────────────────────────────────────────────────
        out_key = step.get("output_key", step_id)
        out_val = output.get("output", output.get(out_key, ""))

        # Update context with output
        new_ctx = {**context}
        new_ctx.pop("_resolved_input", None)
        new_ctx.pop("_force_next_step", None)
        new_ctx[out_key] = out_val
        if "validated_brief" in output:
            new_ctx["validated_brief"] = output["validated_brief"]

        # ── Fix 5: Quality score — single method via resolve_path ─────────
        quality = None
        cl = skill.get("critic_loop", {})
        if step_type == "critic":
            # Parse JSON output if string
            if isinstance(out_val, str):
                try:
                    parsed = json.loads(out_val)
                    if isinstance(parsed, dict):
                        new_ctx[out_key] = parsed
                        out_val = parsed
                except (json.JSONDecodeError, TypeError):
                    pass
            # Extract score via score_field path
            if cl.get("enabled") and cl.get("score_field"):
                score_val, found = resolve_path(
                    {**new_ctx, out_key: out_val}, cl["score_field"])
                if found and score_val is not None:
                    try:
                        quality = float(score_val)
                    except (ValueError, TypeError):
                        pass
            # Direct fallback for critic output
            if quality is None and isinstance(out_val, dict):
                quality = out_val.get("quality_score")

            # ── DeepEval augmentation (ecosystem wiring) ──────────────
            # Run quick_score alongside critic score, take min (L-012)
            if quality is not None:
                try:
                    from lib.eval_harness import quick_score
                    gen_key = cl.get("generator_step", "")
                    gen_text = str(new_ctx.get(gen_key, ""))
                    if gen_text and len(gen_text) > 50:
                        ds = quick_score(gen_text, str(state.get("inputs", "")))
                        if ds < quality:
                            print(f"  [deepeval] score={ds:.1f} < critic={quality:.1f}, using min")
                            quality = min(quality, ds)
                except ImportError:
                    pass  # deepeval not installed, skip
                except Exception:
                    pass  # never break critic loop on eval failure

        # ── Fix 4: Increment loop counter after CRITIC, not improve step ──
        if cl.get("enabled") and step_id == cl.get("critic_step"):
            cn = cl.get("counter_name", "critic_loop")
            # Only increment when critic says quality is below threshold
            if quality is not None:
                try:
                    if float(quality) < cl.get("acceptance_score", 10):
                        counters[cn] = counters.get(cn, 0) + 1
                except (ValueError, TypeError):
                    counters[cn] = counters.get(cn, 0) + 1
        new_ctx["loop_counters"] = counters

        # ── Fix 2: Final step = transition resolves to __end__ ────────────
        transition = step.get("transition", {})
        next_resolved = evaluate_transition(transition, new_ctx)
        is_final = (next_resolved == "__end__" or next_resolved == END)

        # Also check critic loop override
        if cl.get("enabled") and step_id == cl.get("critic_step"):
            if quality is not None and quality >= cl.get("acceptance_score", 10):
                is_final = False  # Goes to final step, not END directly
            elif counters.get(cl.get("counter_name", "critic_loop"), 0) >= cl.get("max_improvements", 5):
                is_final = False  # Goes to final step, not END directly

        # Artifact write for final step
        artifact_path = state.get("artifact_path", "")
        if is_final:
            content = select_final_output(skill, new_ctx)
            if content and content != "artifact_written":
                # ── Post-output validation (ecosystem wiring) ──────────────
                try:
                    from lib.routing import validate_output as _validate
                    is_outbound = skill.get("outbound", False)
                    _text, _warnings = _validate(
                        content if isinstance(content, str) else str(content),
                        min_length=50,
                        check_pii=is_outbound,
                        check_safety=is_outbound,
                    )
                    for w in _warnings:
                        print(f"  [validate] {w}")
                except Exception:
                    pass  # Never block artifact write on validation failure

                artifact_path = write_artifact(skill, state["workflow_id"], content)
                print(f"  [artifact] Written to: {artifact_path}")

                # Accumulate metrics for envelope
                all_hist = list(state.get("step_history", [])) + [
                    {"step_id": step_id, "step_type": step_type,
                     "latency_ms": latency_ms, "cost_usd": cost_usd}]
                tc = sum(h.get("cost_usd", 0) for h in all_hist)
                tl = sum(h.get("latency_ms", 0) for h in all_hist)
                lc = sum(1 for h in all_hist if h.get("step_type") in ("llm", "critic"))
                cl_count = counters.get(cl.get("counter_name", "critic_loop"), 0) if cl.get("enabled") else 0

                # ── Fix 5: Quality via resolve_path only ──────────────────
                q = quality
                if q is None and cl.get("score_field"):
                    v, f2 = resolve_path(new_ctx, cl["score_field"])
                    if f2 and isinstance(v, (int, float)):
                        q = v

                ep = write_envelope(skill, state["workflow_id"],
                    {**state, "context": new_ctx, "artifact_path": artifact_path,
                     "status": "complete", "completed_steps":
                     state.get("completed_steps", []) + [step_id]},
                    tc, tl, lc, cl_count, q, {})
                print(f"  [envelope] Written to: {ep}")

        log_step_metric(skill["name"], state["workflow_id"], step, "success",
                       latency_ms, cost_usd, provider, model, quality)
        print(f"  [done] {step_id}")

        return {
            "context": new_ctx, "completed_steps": [step_id],
            "step_history": [{"step_id": step_id, "status": "success",
                              "step_type": step_type,
                              "latency_ms": latency_ms, "cost_usd": cost_usd,
                              "output_preview": str(out_val)[:100]}],
            "loop_counters": counters,
            "artifact_path": artifact_path,
            "status": "running", "error": "",
        }

    node_fn.__name__ = step_id
    return node_fn


# ── Transition Router ─────────────────────────────────────────────────────────
def make_router(skill, step):
    step_id = step["id"]
    transition = step.get("transition", {})
    cl = skill.get("critic_loop", {})

    def router(state: SkillState) -> str:
        ctx = state.get("context", {})

        # Bail to END if skill has failed
        if state.get("status") == "failed":
            return "__end__"

        # Fix 3: Direct fallback routing via _force_next_step
        forced = ctx.get("_force_next_step")
        if forced:
            return forced

        # Critic loop logic
        if cl.get("enabled") and step_id == cl.get("critic_step"):
            sp = cl.get("score_field", "")
            score, found = resolve_path(ctx, sp)
            acc = cl.get("acceptance_score", 10)
            cn = cl.get("counter_name", "critic_loop")
            count = ctx.get("loop_counters", {}).get(cn, 0)
            mx = cl.get("max_improvements", 5)

            if found and score is not None:
                try:
                    if float(score) >= acc:
                        return cl.get("fallback_final_step", END)
                except (ValueError, TypeError):
                    pass
            if count >= mx:
                return cl.get("fallback_final_step", END)
            return cl.get("improve_step", transition.get("default", END))

        # Standard transition evaluation
        nxt = evaluate_transition(transition, ctx)
        return nxt if nxt != "__end__" else END

    router.__name__ = f"router_{step_id}"
    return router


# ── Graph Builder ─────────────────────────────────────────────────────────────
def build_graph(skill, skill_dir, checkpointer):
    steps    = skill["steps"]
    step_ids = [s["id"] for s in steps]
    step_set = set(step_ids)

    graph = StateGraph(SkillState)
    for step in steps:
        graph.add_node(step["id"], make_node(skill, skill_dir, step))

    for step in steps:
        tr = step.get("transition", {})
        conds = tr.get("conditions", [])
        cl = skill.get("critic_loop", {})
        has_cl = cl.get("enabled") and step["id"] == cl.get("critic_step")
        default = tr.get("default", "__end__")
        has_fb = step.get("failure", {}).get("fallback_step") in step_set

        needs_conditional = bool(conds) or has_cl or has_fb or (default in step_set and default != step_ids[-1] if step["id"] != step_ids[-1] else False)

        # For v1 linear skills OR simple sequential v2: use plain edges
        if not needs_conditional and not conds and not has_cl:
            if default == "__end__" or step["id"] == step_ids[-1]:
                graph.add_edge(step["id"], END)
            elif default in step_set:
                graph.add_edge(step["id"], default)
            else:
                idx = step_ids.index(step["id"])
                if idx < len(step_ids) - 1:
                    graph.add_edge(step["id"], step_ids[idx + 1])
                else:
                    graph.add_edge(step["id"], END)
        else:
            # Conditional edges
            dests = set()
            for c in conds:
                gt = c.get("go_to")
                if gt and gt in step_set:
                    dests.add(gt)
            if default in step_set:
                dests.add(default)
            if has_cl:
                for k in ("improve_step", "fallback_final_step"):
                    v = cl.get(k)
                    if v and v in step_set:
                        dests.add(v)
            fb = step.get("failure", {}).get("fallback_step")
            if fb and fb in step_set:
                dests.add(fb)

            dest_map = {d: d for d in dests}
            dest_map[END] = END

            graph.add_conditional_edges(step["id"], make_router(skill, step), dest_map)

    graph.set_entry_point(step_ids[0])
    return graph.compile(checkpointer=checkpointer)


# ── Main ──────────────────────────────────────────────────────────────────────
def run_skill(skill_name, inputs, thread_id=None, resume=False, input_from=None):
    skill_dir = os.path.join(SKILLS_DIR, skill_name)
    if not os.path.exists(os.path.join(skill_dir, "skill.yaml")):
        print(f"ERROR: Skill not found: {skill_name}")
        sys.exit(1)

    skill = load_skill_yaml(skill_dir)
    skill = adapt_v1_skill(skill)

    errors, inputs = validate_inputs(skill, inputs)
    if errors:
        print("ERROR: Input validation failed:\n  " + "\n  ".join(errors))
        sys.exit(1)

    prev_skills = []
    if input_from:
        prev_skills = [load_upstream_envelope(input_from)]

    if not thread_id:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        thread_id = f"skill-{skill_name}-{ts}-{str(uuid.uuid4())[:8]}"

    os.makedirs(os.path.dirname(CHECKPOINT_DB), exist_ok=True)

    display = skill.get("display_name", skill["name"])
    ver = skill.get("version", "1.0.0")
    print(f"\n{'Resuming' if resume else 'Starting'} skill: {display} v{ver}")
    print(f"Thread ID: {thread_id}")

    config = {"configurable": {"thread_id": thread_id}}

    # Phase 6.1: Backup checkpoint DB before every run
    if os.path.exists(CHECKPOINT_DB):
        shutil.copy2(CHECKPOINT_DB, CHECKPOINT_DB + ".bak")

    with SqliteSaver.from_conn_string(CHECKPOINT_DB) as checkpointer:
        app = build_graph(skill, skill_dir, checkpointer)

        if resume:
            print(f"Resuming from last checkpoint in thread: {thread_id}")
            final_state = app.invoke(None, config=config)
        else:
            initial_state: SkillState = {
                "skill_name":      skill_name,
                "workflow_id":     thread_id,
                "inputs":          inputs,
                "context":         build_rich_context(skill, thread_id, inputs, prev_skills),
                "completed_steps": [],
                "step_history":    [],
                "loop_counters":   {},
                "artifact_path":   "",
                "error":           "",
                "status":          "running",
            }
            final_state = app.invoke(initial_state, config=config)

    if final_state.get("status") == "failed":
        err = final_state.get("error", "Unknown error")
        print(f"\nERROR: Skill failed — {err}")
        write_error_envelope(skill, thread_id, err, 0,
            err.split(":")[0].strip() if ":" in err else "unknown",
            len(final_state.get("completed_steps", [])))
        print(f"Resume with: --thread-id {thread_id} --resume")
        sys.exit(1)

    # v1 output validation
    if skill.get("schema_version", 1) < 2:
        brief = final_state["context"].get("validated_brief",
                final_state["context"].get("structured_brief", ""))
        val_errors = validate_output_v1(skill, brief)
        if val_errors:
            print("ERROR: Output validation failed:\n  " + "\n  ".join(val_errors))
            sys.exit(1)

    print(f"\nSkill complete: {display}")
    print(f"Thread ID: {thread_id}")
    if final_state.get("artifact_path"):
        print(f"Output: {final_state['artifact_path']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NemoClaw Skill Runner v4.0")
    parser.add_argument("--skill",      required=True)
    parser.add_argument("--input",      action="append", nargs=2, metavar=("KEY", "VALUE"))
    parser.add_argument("--thread-id",  help="Thread ID for resume")
    parser.add_argument("--resume",     action="store_true")
    parser.add_argument("--input-from", help="Path to upstream envelope JSON for chaining")
    args = parser.parse_args()

    inputs = {k: v for k, v in (args.input or [])}
    run_skill(args.skill, inputs, thread_id=args.thread_id,
              resume=args.resume, input_from=args.input_from)
