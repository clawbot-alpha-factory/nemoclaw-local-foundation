#!/usr/bin/env python3
"""
NemoClaw Skill Runner v2.0 — LangGraph Edition
Phase 6: Rewritten as LangGraph graph. No OpenShell dependency.
Nodes map to skill steps. Shared state carries context between nodes.
Budget enforcer wired into each node. Checkpoint system integrated.
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from typing import TypedDict, Any

import yaml
from langgraph.graph import StateGraph, END

SKILLS_DIR  = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.join(os.path.dirname(SKILLS_DIR), "scripts")
REPO_BASE   = os.path.dirname(SKILLS_DIR)
RUNNER_VERSION = "2.0.0"

sys.path.insert(0, SCRIPTS_DIR)
import checkpoint_utils as cp


# ── Shared State Schema ───────────────────────────────────────────────────────
class SkillState(TypedDict):
    skill_name:       str
    workflow_id:      str
    inputs:           dict
    context:          dict
    current_step:     str
    completed_steps:  list
    artifact_path:    str
    error:            str
    status:           str


# ── Helpers ───────────────────────────────────────────────────────────────────
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
    return errors, inputs

def validate_output(skill, output_text):
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


# ── Node Factory ──────────────────────────────────────────────────────────────
def make_node(skill, skill_dir, step):
    """Create a LangGraph node function for a skill step."""
    step_id    = step["id"]
    task_class = step.get("task_class", "general_short")
    idm        = step.get("idempotency", {})

    def node_fn(state: SkillState) -> SkillState:
        wf_id   = state["workflow_id"]
        context = state["context"].copy()
        inputs  = state["inputs"]

        # Idempotency check
        if step_id in state["completed_steps"]:
            if idm.get("never_auto_rerun", False):
                print(f"  [skip] {step_id} — never_auto_rerun, already complete")
                return state
            if idm.get("cached", False):
                print(f"  [cached] {step_id} — using prior output")
                return state
            print(f"  [skip] {step_id} — already completed")
            return state

        print(f"\n  [node] {step_id}: {step['name']}")

        # Approval gate
        if step.get("requires_human_approval", False):
            ans = input(f"  [approval] {step_id} requires approval. Proceed? (yes/no): ").strip().lower()
            if ans != "yes":
                cp.pause(wf_id, "paused_manual", f"User declined {step_id}")
                return {**state, "status": "paused_manual", "error": f"Approval declined at {step_id}"}

        # Budget enforcement (skip for artifact write step)
        if step_id != "step_5":
            try:
                budget = call_budget_enforcer(task_class)
                context["last_budget"] = budget
            except RuntimeError as e:
                return {**state, "status": "failed", "error": str(e)}

        # Execute step
        output, error = call_run_py(skill_dir, step_id, inputs, context)

        if error or not output:
            cp.pause(wf_id, "paused_manual", f"Step {step_id} failed: {error}")
            return {**state, "status": "failed", "error": f"Step {step_id}: {error}"}

        # Handle artifact write
        artifact_path = state.get("artifact_path", "")
        if step_id == "step_5":
            content = context.get("validated_brief", context.get("structured_brief", ""))
            artifact_path = write_artifact(skill, wf_id, content)
            output = {"brief_file": artifact_path}
            print(f"  [artifact] Written to: {artifact_path}")

        # Update context with step output
        output_key = step.get("output_key", step_id)
        new_context = {**context}
        new_context[output_key] = output.get("output", output.get(output_key, ""))
        if "validated_brief" in output:
            new_context["validated_brief"] = output["validated_brief"]

        # Mark step complete in checkpoint
        completed = list(state["completed_steps"]) + [step_id]
        cp.complete_step(wf_id, step_id,
                         files_created=[artifact_path] if artifact_path else [])
        print(f"  [done] {step_id}")

        return {
            **state,
            "context":         new_context,
            "completed_steps": completed,
            "current_step":    step_id,
            "artifact_path":   artifact_path,
            "status":          "running",
            "error":           "",
        }

    node_fn.__name__ = step_id
    return node_fn


# ── Graph Builder ─────────────────────────────────────────────────────────────
def build_graph(skill, skill_dir):
    """Build LangGraph StateGraph from skill.yaml step definitions."""
    steps    = skill["steps"]
    step_ids = [s["id"] for s in steps]

    graph = StateGraph(SkillState)

    # Add one node per step
    for step in steps:
        node_fn = make_node(skill, skill_dir, step)
        graph.add_node(step["id"], node_fn)

    # Linear edges: step_1 → step_2 → ... → END
    for i, step_id in enumerate(step_ids):
        if i < len(step_ids) - 1:
            graph.add_edge(step_id, step_ids[i + 1])
        else:
            graph.add_edge(step_id, END)

    graph.set_entry_point(step_ids[0])
    return graph.compile()


# ── Main ──────────────────────────────────────────────────────────────────────
def run_skill(skill_name, inputs, workflow_id=None, resume=False):
    skill_dir = os.path.join(SKILLS_DIR, skill_name)
    if not os.path.exists(os.path.join(skill_dir, "skill.yaml")):
        print(f"ERROR: Skill not found: {skill_name}")
        sys.exit(1)

    skill = load_skill_yaml(skill_dir)

    # Validate inputs
    errors, inputs = validate_inputs(skill, inputs)
    if errors:
        print("ERROR: Input validation failed:\n  " + "\n  ".join(errors))
        sys.exit(1)

    steps    = skill["steps"]
    step_ids = [s["id"] for s in steps]

    # Checkpoint setup
    if resume and workflow_id:
        checkpoint, err = cp.resume(workflow_id)
        if err:
            print(f"ERROR: Cannot resume: {err}")
            sys.exit(1)
        completed_steps = checkpoint["completed_steps"]
        print(f"\nResuming workflow: {workflow_id}")
        print(f"Resuming from: {checkpoint['resume_point']['step']}")
    else:
        workflow_id     = cp.generate_workflow_id(f"skill-{skill_name}")
        checkpoint      = cp.create(workflow_id, skill_name, step_ids)
        completed_steps = []
        print(f"\nStarting skill: {skill['name']} v{skill['version']}")
        print(f"Workflow ID: {workflow_id}")

    # Build and run graph
    app = build_graph(skill, skill_dir)

    initial_state: SkillState = {
        "skill_name":      skill_name,
        "workflow_id":     workflow_id,
        "inputs":          inputs,
        "context":         {},
        "current_step":    step_ids[0],
        "completed_steps": completed_steps,
        "artifact_path":   "",
        "error":           "",
        "status":          "running",
    }

    final_state = app.invoke(initial_state)

    if final_state["status"] == "failed":
        print(f"\nERROR: Skill failed — {final_state['error']}")
        sys.exit(1)

    # Final output validation
    brief = final_state["context"].get("validated_brief",
            final_state["context"].get("structured_brief", ""))
    val_errors = validate_output(skill, brief)
    if val_errors:
        print("ERROR: Output validation failed:\n  " + "\n  ".join(val_errors))
        sys.exit(1)

    print(f"\nSkill complete: {skill['name']}")
    print(f"Workflow ID: {workflow_id}")
    if final_state["artifact_path"]:
        print(f"Output: {final_state['artifact_path']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NemoClaw Skill Runner v2.0 — LangGraph")
    parser.add_argument("--skill",       required=True)
    parser.add_argument("--input",       action="append", nargs=2,
                        metavar=("KEY", "VALUE"))
    parser.add_argument("--workflow-id", help="Workflow ID for resume")
    parser.add_argument("--resume",      action="store_true")
    args = parser.parse_args()

    inputs = {k: v for k, v in (args.input or [])}
    run_skill(args.skill, inputs, workflow_id=args.workflow_id, resume=args.resume)
