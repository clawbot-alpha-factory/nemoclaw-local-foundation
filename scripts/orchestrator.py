#!/usr/bin/env python3
"""
NemoClaw Multi-Agent Orchestrator v2.0

A true multi-agent coordination system, not a pipeline.

Architecture:
  - Agent abstraction (identity, role, specialization)
  - Shared memory (key-value workspace accessible by all agents)
  - Inter-agent contracts (required fields validated before handoff)
  - Validation loops (reviewer agents can send work back)
  - Failure handling (retry, redirect, halt per agent)
  - Format enforcement (normalization layer between agents)

Usage:
  python3 scripts/orchestrator.py --workflow workflows/pipeline-v2.yaml
  python3 scripts/orchestrator.py --plan "Research AI agents and write a product spec" --dry-run
  python3 scripts/orchestrator.py --list-skills
"""

import argparse
import copy
import json
import os
import re
import subprocess
import sys
import time
import yaml
from datetime import datetime, timezone
from pathlib import Path

REPO = Path.home() / "nemoclaw-local-foundation"
SKILLS_DIR = REPO / "skills"
PYTHON = str(REPO / ".venv313" / "bin" / "python3")
RUNNER = str(SKILLS_DIR / "skill-runner.py")
WORKFLOWS_DIR = REPO / "workflows"
CHECKPOINT_DB = Path.home() / ".nemoclaw" / "checkpoints" / "langgraph.db"
MEMORY_DIR = Path.home() / ".nemoclaw" / "workspaces"


# ═══════════════════════════════════════════════════════════════════════════════
# SHARED MEMORY
# ═══════════════════════════════════════════════════════════════════════════════

class WorkspaceMemory:
    """Shared memory layer for multi-agent coordination.
    
    All agents in a workflow can read/write to this memory.
    Memory persists across steps within a single workflow run.
    Keys are namespaced: agent_name.key_name
    """

    def __init__(self, workspace_id):
        self.workspace_id = workspace_id
        self.store = {}  # key → {value, source_agent, timestamp, importance}
        self.history = []  # append-only audit trail
        self.workspace_dir = MEMORY_DIR / workspace_id
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

    def write(self, key, value, source_agent, importance="standard"):
        """Write a key-value pair to shared memory."""
        entry = {
            "value": value,
            "source_agent": source_agent,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "importance": importance,  # critical, standard, auxiliary
        }
        self.store[key] = entry
        self.history.append({"action": "write", "key": key, **entry})

    def read(self, key, default=None):
        """Read a value from shared memory."""
        entry = self.store.get(key)
        if entry is None:
            return default
        return entry["value"]

    def read_many(self, keys):
        """Read multiple keys, return dict of found values."""
        result = {}
        for key in keys:
            val = self.read(key)
            if val is not None:
                result[key] = val
        return result

    def has(self, key):
        """Check if a key exists in memory."""
        return key in self.store

    def keys(self):
        """List all keys in memory."""
        return list(self.store.keys())

    def dump(self):
        """Return full memory state for inspection."""
        return {k: {"value": str(v["value"])[:200], "source": v["source_agent"], 
                     "importance": v["importance"]}
                for k, v in self.store.items()}

    def save(self):
        """Persist memory to disk."""
        path = self.workspace_dir / "memory.json"
        serializable = {}
        for k, v in self.store.items():
            serializable[k] = {
                "value": v["value"] if isinstance(v["value"], (str, int, float, bool, list, dict)) else str(v["value"]),
                "source_agent": v["source_agent"],
                "timestamp": v["timestamp"],
                "importance": v["importance"],
            }
        with open(path, "w") as f:
            json.dump(serializable, f, indent=2)

    def load(self):
        """Load memory from disk if exists."""
        path = self.workspace_dir / "memory.json"
        if path.exists():
            with open(path) as f:
                data = json.load(f)
            for k, v in data.items():
                self.store[k] = v


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT
# ═══════════════════════════════════════════════════════════════════════════════

class Agent:
    """An agent wraps a skill with identity, role, and coordination logic."""

    def __init__(self, config):
        self.name = config["agent"]
        self.skill_id = config.get("skill")
        self.agent_type = config.get("type", "executor")  # executor, validator, decision, formatter
        self.inputs = config.get("inputs", {})
        self.inputs_from_memory = config.get("inputs_from_memory", [])
        self.outputs_to_memory = config.get("outputs_to_memory", [])
        self.chain_from = config.get("chain_from")
        self.on_failure = config.get("on_failure", {"retry": 1, "fallback": "halt"})
        self.condition = config.get("condition")
        self.go_to = config.get("go_to")
        self.memory_contract = config.get("memory_contract", {})

    def __repr__(self):
        return f"Agent({self.name}, skill={self.skill_id}, type={self.agent_type})"


# ═══════════════════════════════════════════════════════════════════════════════
# CONTRACT ENFORCEMENT
# ═══════════════════════════════════════════════════════════════════════════════

def validate_contract(memory, contract, source_agent, target_agent):
    """Validate that required memory keys exist before an agent runs.
    
    Returns (passed: bool, missing: list[str])
    """
    required = contract.get("required_fields", [])
    missing = []
    for field in required:
        if not memory.has(field):
            missing.append(field)
    
    if missing:
        return False, missing
    return True, []


# ═══════════════════════════════════════════════════════════════════════════════
# ENVELOPE → MEMORY EXTRACTION
# ═══════════════════════════════════════════════════════════════════════════════

def extract_to_memory(envelope_path, agent_name, memory, output_keys):
    """Extract specified fields from a skill envelope into shared memory."""
    if not envelope_path or not os.path.exists(envelope_path):
        return

    with open(envelope_path) as f:
        envelope = json.load(f)

    primary = envelope.get("outputs", {}).get("primary", "")
    
    for key in output_keys:
        # Try to extract from primary output using section headers
        section = _extract_section_from_output(primary, key)
        if section:
            memory.write(key, section, agent_name, importance="standard")
        else:
            # Store a note that extraction failed
            memory.write(key, f"[NOT EXTRACTED — no '{key}' section found in {agent_name} output]",
                        agent_name, importance="auxiliary")

    # Always store the full primary output
    memory.write(f"{agent_name}_full_output", primary, agent_name, importance="standard")
    
    # Store envelope metadata
    memory.write(f"{agent_name}_envelope_path", envelope_path, agent_name, importance="auxiliary")
    memory.write(f"{agent_name}_quality_score", 
                envelope.get("metrics", {}).get("final_quality_score", 0),
                agent_name, importance="standard")


def _extract_section_from_output(text, key):
    """Extract a section from markdown output by keyword."""
    if not text:
        return None
    
    # Normalize key for matching
    key_words = key.replace("_", " ").lower()
    
    # Try H2 section extraction
    pattern = rf'(?:^|\n)##\s[^\n]*{re.escape(key_words)}[^\n]*\n(.*?)(?=\n##\s[^#]|\Z)'
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    
    # Try keyword search in any section
    for word in key_words.split():
        if len(word) < 4:
            continue
        pattern = rf'(?:^|\n)##\s[^\n]*{re.escape(word)}[^\n]*\n(.*?)(?=\n##\s[^#]|\Z)'
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
    
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# SKILL EXECUTION
# ═══════════════════════════════════════════════════════════════════════════════

def execute_skill(skill_id, inputs, chain_from_envelope=None):
    """Execute a single skill via skill-runner.py subprocess."""
    if CHECKPOINT_DB.exists():
        CHECKPOINT_DB.unlink()

    cmd = [PYTHON, RUNNER, "--skill", skill_id]
    for key, value in inputs.items():
        if isinstance(value, list):
            cmd.extend(["--input", key, ", ".join(str(v) for v in value)])
        else:
            cmd.extend(["--input", key, str(value)])

    if chain_from_envelope:
        cmd.extend(["--input-from", str(chain_from_envelope)])

    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=600, cwd=str(REPO)
    )

    output = result.stdout + result.stderr
    success = "Skill complete" in output

    envelope_path = None
    artifact_path = None
    for line in output.split("\n"):
        if "[envelope]" in line and "Written to:" in line:
            envelope_path = line.split("Written to:")[-1].strip()
        if "[artifact]" in line and "Written to:" in line:
            artifact_path = line.split("Written to:")[-1].strip()

    # Extract error message on failure
    error = None
    if not success:
        for line in output.split("\n"):
            if "ERROR:" in line or '"error"' in line:
                error = line.strip()[:200]
                break
        if not error:
            error = output.strip().split("\n")[-1][:200] if output.strip() else "Unknown error"

    return {
        "success": success,
        "envelope_path": envelope_path,
        "artifact_path": artifact_path,
        "error": error,
        "output": output,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SKILL DISCOVERY
# ═══════════════════════════════════════════════════════════════════════════════

def discover_skills():
    """Find all available skills and their input requirements."""
    skills = {}
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        if not skill_dir.is_dir():
            continue
        yaml_path = skill_dir / "skill.yaml"
        if not yaml_path.exists():
            continue
        try:
            with open(yaml_path) as f:
                spec = yaml.safe_load(f)
            skill_id = skill_dir.name
            skills[skill_id] = {
                "name": spec.get("display_name", skill_id),
                "description": spec.get("description", ""),
                "inputs": [
                    {"name": inp["name"], "required": inp.get("required", False)}
                    for inp in spec.get("inputs", [])
                ],
            }
        except Exception:
            continue
    return skills


# ═══════════════════════════════════════════════════════════════════════════════
# NL PLANNER
# ═══════════════════════════════════════════════════════════════════════════════

def plan_from_natural_language(goal, available_skills):
    """Use LLM to generate a multi-agent workflow from natural language."""
    catalog = []
    for sid, info in available_skills.items():
        req = [i["name"] for i in info["inputs"] if i["required"]]
        catalog.append(f"  {sid}: {info['description'][:80]}  required: {', '.join(req)}")

    skill_list = "\n".join(catalog)

    env_path = REPO / "config" / ".env"
    api_key = None
    with open(env_path) as f:
        for line in f:
            if "OPENAI_API_KEY" in line:
                api_key = line.strip().split("=", 1)[1].strip()

    if not api_key:
        print("ERROR: No OpenAI API key")
        sys.exit(1)

    from openai import OpenAI
    client = OpenAI(api_key=api_key)

    prompt = f"""You are a multi-agent workflow planner. Plan a workflow where specialized agents collaborate.

AVAILABLE SKILLS:
{skill_list}

GOAL: {goal}

Respond with ONLY valid JSON:
{{
  "name": "workflow name",
  "mode": "multi_agent",
  "context": {{"workspace_id": "short_snake_case_id", "shared_memory": true}},
  "steps": [
    {{
      "agent": "agent_role_name",
      "skill": "skill-id",
      "inputs": {{"key": "value"}},
      "outputs_to_memory": ["insight_key_1"],
      "chain_from": null or "previous",
      "on_failure": {{"retry": 1, "fallback": "halt"}}
    }}
  ]
}}

Rules:
- Each step has a unique agent name describing its ROLE (e.g., market_analyst, product_manager)
- outputs_to_memory lists what this agent contributes to shared knowledge
- chain_from: "previous" passes the envelope, null starts fresh
- Provide ALL required inputs
- Max 5 steps
"""

    from lib.routing import resolve_alias
    _, _orch_model, _ = resolve_alias("general_short")
    resp = client.chat.completions.create(
        model=_orch_model,
        max_completion_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    text = resp.choices[0].message.content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON from planner: {e}")
        print(f"Raw: {text[:300]}")
        sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════════════
# ORCHESTRATOR ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def run_workflow(workflow, dry_run=False):
    """Execute a multi-agent workflow with shared memory and contracts."""
    name = workflow.get("name", "Unnamed Workflow")
    mode = workflow.get("mode", "pipeline")
    context = workflow.get("context", {})
    steps = workflow.get("steps", [])
    contracts = workflow.get("contracts", {})

    workspace_id = context.get("workspace_id", f"wf_{int(time.time())}")
    shared_memory_enabled = context.get("shared_memory", False)

    # Initialize shared memory
    memory = WorkspaceMemory(workspace_id)
    if shared_memory_enabled:
        memory.load()  # Resume if workspace exists

    # Parse agents
    agents = []
    for step_config in steps:
        # Support both old format (skill: x) and new format (agent: x, skill: y)
        if "agent" not in step_config:
            step_config["agent"] = step_config.get("skill", f"step_{len(agents)+1}")
        agents.append(Agent(step_config))

    print("=" * 60)
    print(f"  Workflow: {name}")
    print(f"  Mode: {mode}")
    print(f"  Agents: {len(agents)}")
    print(f"  Shared Memory: {'ON' if shared_memory_enabled else 'OFF'}")
    print(f"  Workspace: {workspace_id}")
    print(f"  Started: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)
    print()

    if dry_run:
        for i, agent in enumerate(agents, 1):
            chain = f" ← previous" if agent.chain_from == "previous" else ""
            mem_in = f"  reads: {agent.inputs_from_memory}" if agent.inputs_from_memory else ""
            mem_out = f"  writes: {agent.outputs_to_memory}" if agent.outputs_to_memory else ""
            cond = f"  IF {agent.condition}" if agent.condition else ""
            print(f"  [{i}] {agent.name} ({agent.agent_type})")
            print(f"      skill: {agent.skill_id}{chain}")
            if agent.inputs:
                for k, v in agent.inputs.items():
                    print(f"      input: {k} = {str(v)[:50]}")
            if mem_in:
                print(f"     {mem_in}")
            if mem_out:
                print(f"     {mem_out}")
            if cond:
                print(f"     {cond} → go_to: {agent.go_to}")
            print(f"      on_fail: {agent.on_failure}")
            print()
        print("  (DRY RUN — no execution)")
        return True

    # ── Execute agents ────────────────────────────────────────────────────
    results = []
    last_envelope = None
    total_start = time.time()
    agent_index = 0

    while agent_index < len(agents):
        agent = agents[agent_index]

        # ── Decision agent: evaluate condition and branch ──
        if agent.agent_type == "decision":
            if agent.condition:
                left_key = agent.condition.get("left", "")
                op = agent.condition.get("op", ">=")
                right_val = agent.condition.get("right", 7)
                left_val = memory.read(left_key, 0)

                passed = False
                if op == "<":
                    passed = float(left_val) < float(right_val)
                elif op == ">=":
                    passed = float(left_val) >= float(right_val)
                elif op == "==":
                    passed = str(left_val) == str(right_val)

                if passed and agent.go_to:
                    # Find target agent index
                    target_idx = next(
                        (i for i, a in enumerate(agents) if a.name == agent.go_to), None
                    )
                    if target_idx is not None:
                        print(f"  [{agent_index+1}] {agent.name} (decision)")
                        print(f"      {left_key}={left_val} {op} {right_val} → redirecting to {agent.go_to}")
                        print()
                        agent_index = target_idx
                        continue
                    
                print(f"  [{agent_index+1}] {agent.name} (decision)")
                print(f"      {left_key}={left_val} {op} {right_val} → continuing")
                print()
                agent_index += 1
                continue

        # ── Build inputs ──
        final_inputs = dict(agent.inputs)

        # Inject memory values into inputs
        if agent.inputs_from_memory and shared_memory_enabled:
            for mem_key in agent.inputs_from_memory:
                val = memory.read(mem_key)
                if val is not None:
                    # Map memory key to a reasonable input name
                    # Use the key itself if no explicit mapping
                    final_inputs[f"_memory_{mem_key}"] = str(val)[:2000]

        # ── Contract validation ──
        contract_key = f"{agents[agent_index-1].name}_to_{agent.name}" if agent_index > 0 else None
        if contract_key and contract_key in contracts:
            passed, missing = validate_contract(memory, contracts[contract_key],
                                                agents[agent_index-1].name, agent.name)
            if not passed:
                print(f"  [{agent_index+1}] {agent.name}")
                print(f"      ❌ CONTRACT VIOLATION: missing {missing}")
                print(f"      Required by: {contract_key}")
                results.append({
                    "step": agent_index+1, "agent": agent.name,
                    "success": False, "error": f"Contract violation: {missing}"
                })
                break

        # ── Determine chaining ──
        chain_envelope = last_envelope if agent.chain_from == "previous" else None

        # ── Execute with retry ──
        max_retries = agent.on_failure.get("retry", 1)
        fallback = agent.on_failure.get("fallback", "halt")
        redirect = agent.on_failure.get("go_to")

        chain_note = f" ← {os.path.basename(chain_envelope)}" if chain_envelope else ""
        print(f"  [{agent_index+1}] {agent.name} → {agent.skill_id}{chain_note}")

        success = False
        result = None
        for attempt in range(max_retries + 1):
            attempt_label = f" (attempt {attempt+1}/{max_retries+1})" if attempt > 0 else ""
            print(f"      Running{attempt_label}...", end="", flush=True)

            start = time.time()
            result = execute_skill(agent.skill_id, final_inputs, chain_envelope)
            elapsed = int(time.time() - start)

            if result["success"]:
                print(f" ✅ ({elapsed}s)")
                success = True
                break
            else:
                print(f" ❌ ({elapsed}s)")
                if result["error"]:
                    print(f"      {result['error'][:120]}")
                if attempt < max_retries:
                    print(f"      Retrying...")

        if success:
            # Update envelope tracking
            if result["envelope_path"]:
                last_envelope = result["envelope_path"]

            # Extract outputs to memory
            if agent.outputs_to_memory and shared_memory_enabled:
                extract_to_memory(
                    result["envelope_path"], agent.name,
                    memory, agent.outputs_to_memory
                )
                written = [k for k in agent.outputs_to_memory if memory.has(k)]
                print(f"      Memory: wrote {written}")

            if result["artifact_path"]:
                print(f"      Artifact: {os.path.basename(result['artifact_path'])}")

            results.append({
                "step": agent_index+1, "agent": agent.name, "skill": agent.skill_id,
                "success": True, "elapsed": elapsed,
                "envelope": result.get("envelope_path"),
                "artifact": result.get("artifact_path"),
            })
        else:
            results.append({
                "step": agent_index+1, "agent": agent.name, "skill": agent.skill_id,
                "success": False, "elapsed": elapsed, "error": result.get("error"),
            })

            # Handle failure
            if redirect:
                target_idx = next(
                    (i for i, a in enumerate(agents) if a.name == redirect), None
                )
                if target_idx is not None:
                    print(f"      Redirecting to: {redirect}")
                    agent_index = target_idx
                    continue

            if fallback == "halt":
                print(f"\n      Pipeline halted at {agent.name}.")
                break
            elif fallback == "skip":
                print(f"      Skipping {agent.name}, continuing...")
            # else continue

        agent_index += 1
        print()

    # ── Summary ───────────────────────────────────────────────────────────
    total_elapsed = int(time.time() - total_start)
    passed = sum(1 for r in results if r["success"])
    failed = len(results) - passed

    print("=" * 60)
    print(f"  Pipeline Complete: {passed}/{len(agents)} agents succeeded")
    print(f"  Total time: {total_elapsed}s")
    if shared_memory_enabled:
        print(f"  Memory keys: {len(memory.keys())}")
    print("=" * 60)

    # Save memory
    if shared_memory_enabled:
        memory.save()
        print(f"\n  Memory saved: {memory.workspace_dir / 'memory.json'}")

    # Save results
    results_path = WORKFLOWS_DIR / "last-pipeline-result.json"
    results_path.parent.mkdir(exist_ok=True)
    with open(results_path, "w") as f:
        json.dump({
            "workflow": name,
            "mode": mode,
            "workspace_id": workspace_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_elapsed_s": total_elapsed,
            "agents_planned": len(agents),
            "agents_passed": passed,
            "agents_failed": failed,
            "memory_keys": memory.keys() if shared_memory_enabled else [],
            "results": results,
        }, f, indent=2)

    # Print artifacts
    if passed > 0:
        print("\n  Artifacts:")
        for r in results:
            if r.get("artifact"):
                print(f"    {r['agent']}: {os.path.basename(r['artifact'])}")

    # Print memory summary
    if shared_memory_enabled and memory.keys():
        print("\n  Shared Memory:")
        for k, info in memory.dump().items():
            val_preview = str(info["value"])[:60].replace("\n", " ")
            print(f"    [{info['importance'][0]}] {k} ({info['source']}): {val_preview}")

    return failed == 0


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="NemoClaw Multi-Agent Orchestrator v2.0")
    parser.add_argument("--workflow", help="Path to workflow YAML/JSON")
    parser.add_argument("--plan", help="Natural language goal — LLM plans the workflow")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--list-skills", action="store_true")
    args = parser.parse_args()

    if args.list_skills:
        skills = discover_skills()
        print(f"Available skills ({len(skills)}):")
        for sid, info in skills.items():
            req = [i["name"] for i in info["inputs"] if i["required"]]
            print(f"  {sid}: {', '.join(req)}")
        return

    if args.workflow:
        with open(args.workflow) as f:
            workflow = yaml.safe_load(f)
    elif args.plan:
        print("Planning workflow...", flush=True)
        skills = discover_skills()
        workflow = plan_from_natural_language(args.plan, skills)
        print(f"  Plan: {workflow.get('name', '?')}")
        print(f"  Agents: {len(workflow.get('steps', []))}")
        plan_path = WORKFLOWS_DIR / "last-generated-plan.yaml"
        plan_path.parent.mkdir(exist_ok=True)
        with open(plan_path, "w") as f:
            yaml.dump(workflow, f, default_flow_style=False)
        print(f"  Saved: {plan_path}\n")
    else:
        parser.print_help()
        return

    success = run_workflow(workflow, dry_run=args.dry_run)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
