#!/usr/bin/env python3
"""
NemoClaw Skill Runner v1.0.0
Shared runner for all Skills. Loads skill.yaml, validates inputs,
executes steps with checkpointing, budget enforcement, and artifact storage.
"""

import argparse
import json
import os
import sys
import subprocess
from datetime import datetime, timezone

import yaml

SKILLS_DIR    = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR   = os.path.join(os.path.dirname(SKILLS_DIR), "scripts")
REPO_BASE     = os.path.dirname(SKILLS_DIR)
RUNNER_VERSION = "1.0.0"

sys.path.insert(0, SCRIPTS_DIR)
import checkpoint_utils as cp

def load_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f)

def check_versions(skill):
    sv = skill.get("schema_version", 1)
    if sv != 1:
        die(f"Unsupported schema_version: {sv}. This runner supports schema_version 1 only.")

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
            errors.append(f"Input '{name}' too short (min {rules['min_length']} chars)")
        if "max_length" in rules and len(str(value)) > rules["max_length"]:
            errors.append(f"Input '{name}' too long (max {rules['max_length']} chars)")
        if "allowed_values" in rules and value not in rules["allowed_values"]:
            errors.append(f"Input '{name}' must be one of: {rules['allowed_values']}")
        if "must_exist" in rules and rules["must_exist"]:
            if not os.path.exists(value):
                errors.append(f"Input '{name}' file not found: {value}")
    if errors:
        die("Input validation failed:\n  " + "\n  ".join(errors))
    return inputs

def validate_output(skill, output_text):
    rules = skill.get("validation", {}).get("output", [])
    errors = []
    for rule in rules:
        r = rule["rule"]
        if "at least" in r and "characters" in r:
            min_len = int([x for x in r.split() if x.isdigit()][0])
            if len(output_text) < min_len:
                errors.append(f"Output too short — needs {min_len} chars, got {len(output_text)}")
        if "contain" in r and "section" in r:
            section = r.split("contain ")[-1].replace(" section", "").strip()
            if section not in output_text:
                errors.append(f"Output missing required section: {section}")
    return errors

def call_budget_enforcer(task_class):
    enforcer = os.path.join(SCRIPTS_DIR, "budget-enforcer.py")
    result = subprocess.run(
        [sys.executable, enforcer, "--task-class", task_class],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        die(f"Budget enforcer failed: {result.stderr}")
    data = json.loads(result.stdout)
    print(f"  [budget] alias={data['alias']} model={data['model']} cost=${data['estimated_cost_usd']} remaining=${data['budget_remaining_usd']}")
    return data

def call_run_py(skill_dir, step, inputs, context):
    run_path = os.path.join(skill_dir, "run.py")
    spec = {"step_id": step["id"], "inputs": inputs, "context": context}
    tmp = "/tmp/nemoclaw_step_input.json"
    with open(tmp, "w") as f:
        json.dump(spec, f)
    result = subprocess.run(
        [sys.executable, run_path, "--step", step["id"], "--input", tmp],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return None, result.stderr.strip()
    try:
        return json.loads(result.stdout), None
    except json.JSONDecodeError:
        return {"output": result.stdout.strip()}, None

def write_artifact(skill, workflow_id, content):
    artifacts = skill.get("artifacts", {})
    storage = os.path.join(REPO_BASE, artifacts.get("storage_location", "skills/outputs/"))
    os.makedirs(storage, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = artifacts.get("filename_pattern", "output_{workflow_id}_{timestamp}.md")
    filename = filename.replace("{workflow_id}", workflow_id).replace("{timestamp}", ts).replace("{skill_name}", skill["name"])
    filepath = os.path.join(storage, filename)
    with open(filepath, "w") as f:
        f.write(content)
    return filepath

def die(msg):
    print(f"\nERROR: {msg}")
    sys.exit(1)

def run_skill(skill_name, inputs, workflow_id=None, resume=False):
    skill_dir  = os.path.join(SKILLS_DIR, skill_name)
    yaml_path  = os.path.join(skill_dir, "skill.yaml")
    if not os.path.exists(yaml_path):
        die(f"Skill not found: {skill_name}")

    skill = load_yaml(yaml_path)
    check_versions(skill)
    inputs = validate_inputs(skill, inputs)

    steps = skill.get("steps", [])
    step_ids = [s["id"] for s in steps]

    if resume and workflow_id:
        checkpoint, err = cp.resume(workflow_id)
        if err:
            die(f"Cannot resume: {err}")
        print(f"\nResuming workflow: {workflow_id}")
        print(f"Resuming from step: {checkpoint['resume_point']['step']}")
    else:
        workflow_id = cp.generate_workflow_id(f"skill-{skill_name}")
        checkpoint = cp.create(workflow_id, skill_name, step_ids)
        print(f"\nStarting skill: {skill['name']} v{skill['version']}")
        print(f"Workflow ID: {workflow_id}")

    context = {}
    artifact_path = None

    for step in steps:
        sid = step["id"]

        if cp.is_step_done(workflow_id, sid):
            idm = step.get("idempotency", {})
            if idm.get("never_auto_rerun", False):
                print(f"  [skip] {sid} — never_auto_rerun, already complete")
                continue
            if idm.get("cached", False):
                print(f"  [cached] {sid} — using prior output")
                continue
            print(f"  [skip] {sid} — already completed")
            continue

        if step.get("requires_human_approval", False):
            print(f"\n  [approval required] {sid}: {step['name']}")
            ans = input("  Approve this step? (yes/no): ").strip().lower()
            if ans != "yes":
                cp.pause(workflow_id, "paused_manual", f"User declined approval for {sid}")
                print(f"Workflow paused at {sid}. Resume with --resume --workflow-id {workflow_id}")
                return

        print(f"\n  [step] {sid}: {step['name']}")

        if step.get("task_class") and sid != "step_5":
            budget = call_budget_enforcer(step["task_class"])
            context["last_budget"] = budget

        output, error = call_run_py(skill_dir, step, inputs, context)

        if error or not output:
            cp.pause(workflow_id, "paused_manual", f"Step {sid} failed: {error}")
            die(f"Step {sid} failed: {error}")

        if sid == "step_5":
            content = context.get("validated_brief", context.get("structured_brief", ""))
            artifact_path = write_artifact(skill, workflow_id, content)
            output = {"brief_file": artifact_path}
            print(f"  [artifact] Written to: {artifact_path}")

        output_key = step.get("output_key", sid)
        context[output_key] = output.get("output", output.get(output_key, ""))

        cp.complete_step(workflow_id, sid, files_created=[artifact_path] if artifact_path else [])
        print(f"  [done] {sid}")

    val_errors = validate_output(skill, context.get("validated_brief", context.get("structured_brief", "")))
    if val_errors:
        cp.pause(workflow_id, "paused_manual", "Output validation failed")
        die("Output validation failed:\n  " + "\n  ".join(val_errors))

    print(f"\nSkill complete: {skill['name']}")
    print(f"Workflow ID: {workflow_id}")
    if artifact_path:
        print(f"Output: {artifact_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NemoClaw Skill Runner v1.0.0")
    parser.add_argument("--skill", required=True, help="Skill name (directory under skills/)")
    parser.add_argument("--input", action="append", nargs=2, metavar=("KEY", "VALUE"), help="Input key value pairs")
    parser.add_argument("--workflow-id", help="Workflow ID for resume")
    parser.add_argument("--resume", action="store_true", help="Resume from last checkpoint")
    args = parser.parse_args()

    inputs = {k: v for k, v in (args.input or [])}
    run_skill(args.skill, inputs, workflow_id=args.workflow_id, resume=args.resume)
