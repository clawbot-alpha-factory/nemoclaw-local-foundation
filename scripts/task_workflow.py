#!/usr/bin/env python3
"""
NemoClaw Task Workflow — 5-Phase Goal Execution

Takes a high-level goal and runs it through:
  Phase 1: BRAINSTORM — agent generates 3 approaches via LLM
  Phase 2: PLAN — pick best approach, decompose into steps
  Phase 3: EXECUTE — run each step, create files/deliverables
  Phase 4: VALIDATE — check outputs, run quality gate
  Phase 5: DOCUMENT — write logs, reasoning, save to project

Usage:
  python3 scripts/task_workflow.py --goal "Build a competitive analysis report" --agent content_lead
  python3 scripts/task_workflow.py --goal "..." --agent strategy_lead --project proj_abc123
  python3 scripts/task_workflow.py --goal "..." --agent content_lead --dry-run
"""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO = Path.home() / "nemoclaw-local-foundation"
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from lib.routing import call_llm
from lib.structured_logging import get_logger

log = get_logger("nemoclaw.task_workflow")

WORKFLOW_DIR = Path.home() / ".nemoclaw" / "task-workflows"

# ═══════════════════════════════════════════════════════════════════════════════
# WORKFLOW RESULT
# ═══════════════════════════════════════════════════════════════════════════════

class WorkflowResult:
    """Tracks state across all 5 phases."""

    def __init__(self, goal, agent_id, project_id=None):
        self.workflow_id = f"tw_{uuid.uuid4().hex[:8]}"
        self.goal = goal
        self.agent_id = agent_id
        self.project_id = project_id
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.completed_at = None
        self.status = "brainstorm"  # brainstorm | plan | execute | validate | document | complete | failed
        self.error = None

        # Phase outputs
        self.approaches = []       # Phase 1: 3 brainstormed approaches
        self.selected_approach = None
        self.plan = None           # Phase 2: TaskPlan dict
        self.plan_source = None    # "template:<name>" or "llm"
        self.task_results = []     # Phase 3: per-task execution results
        self.gate_results = []     # Phase 4: quality gate results
        self.log_path = None       # Phase 5: documentation path

        # Metrics
        self.phase_timings = {}
        self.total_cost = 0.0

    def to_dict(self):
        return {
            "workflow_id": self.workflow_id,
            "goal": self.goal,
            "agent_id": self.agent_id,
            "project_id": self.project_id,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "status": self.status,
            "error": self.error,
            "approaches": self.approaches,
            "selected_approach": self.selected_approach,
            "plan": self.plan,
            "plan_source": self.plan_source,
            "task_results": self.task_results,
            "gate_results": self.gate_results,
            "log_path": self.log_path,
            "phase_timings": self.phase_timings,
            "total_cost": self.total_cost,
        }

    def save(self):
        WORKFLOW_DIR.mkdir(parents=True, exist_ok=True)
        path = WORKFLOW_DIR / f"{self.workflow_id}.json"
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        return str(path)


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1: BRAINSTORM
# ═══════════════════════════════════════════════════════════════════════════════

def _phase_brainstorm(result):
    """Generate 3 approaches to achieve the goal via LLM."""
    log.info("Phase 1: BRAINSTORM", workflow_id=result.workflow_id, goal=result.goal)

    messages = [
        {"role": "system", "content": (
            "You are a strategic planner for a multi-agent AI company. "
            "Given a goal, propose exactly 3 distinct approaches to achieve it. "
            "For each approach provide:\n"
            "- title: short name\n"
            "- description: 2-3 sentence summary\n"
            "- skills_needed: list of skill types required\n"
            "- estimated_steps: number of execution steps\n"
            "- risk: low/medium/high\n"
            "- rationale: why this approach works\n\n"
            "Return valid JSON: {\"approaches\": [...]}"
        )},
        {"role": "user", "content": (
            f"Goal: {result.goal}\n"
            f"Agent: {result.agent_id}\n"
            f"Generate 3 approaches."
        )},
    ]

    text, err = call_llm(messages, task_class="complex_reasoning", max_tokens=3000)
    if err:
        result.error = f"Brainstorm LLM failed: {err}"
        result.status = "failed"
        return result

    try:
        # Extract JSON from response (handle markdown fences)
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        parsed = json.loads(cleaned)
        result.approaches = parsed.get("approaches", [])[:3]
    except (json.JSONDecodeError, KeyError) as e:
        log.warning("Failed to parse brainstorm JSON, using raw text", error=str(e))
        result.approaches = [{"title": "Single approach", "description": text[:500], "risk": "medium"}]

    if not result.approaches:
        result.error = "Brainstorm produced no approaches"
        result.status = "failed"
        return result

    log.info("Brainstorm complete", approaches=len(result.approaches))
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2: PLAN
# ═══════════════════════════════════════════════════════════════════════════════

def _phase_plan(result):
    """Select best approach and decompose into executable steps."""
    log.info("Phase 2: PLAN", workflow_id=result.workflow_id)

    # Pick the best approach via LLM critique
    approaches_text = json.dumps(result.approaches, indent=2)
    messages = [
        {"role": "system", "content": (
            "You are evaluating approaches to a goal. "
            "Pick the single best approach by weighing feasibility, risk, and quality. "
            "Return JSON: {\"selected_index\": N, \"rationale\": \"...\"}"
        )},
        {"role": "user", "content": (
            f"Goal: {result.goal}\n\nApproaches:\n{approaches_text}\n\n"
            "Which approach (0-indexed) is best?"
        )},
    ]

    text, err = call_llm(messages, task_class="moderate", max_tokens=500)
    if err:
        # Fallback: pick first approach
        log.warning("Selection LLM failed, defaulting to approach 0", error=err)
        selected_idx = 0
    else:
        try:
            cleaned = text.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            parsed = json.loads(cleaned)
            selected_idx = min(parsed.get("selected_index", 0), len(result.approaches) - 1)
        except (json.JSONDecodeError, KeyError):
            selected_idx = 0

    result.selected_approach = result.approaches[selected_idx]
    log.info("Selected approach", index=selected_idx, title=result.selected_approach.get("title"))

    # Decompose via task_decomposer
    from task_decomposer import decompose

    enriched_goal = (
        f"{result.goal}\n\n"
        f"Approach: {result.selected_approach.get('title', '')}\n"
        f"Description: {result.selected_approach.get('description', '')}"
    )
    plan, source, decompose_err = decompose(enriched_goal)

    if decompose_err:
        result.error = f"Decomposition failed: {decompose_err}"
        result.status = "failed"
        return result

    result.plan = plan.to_dict()
    result.plan_source = source
    log.info("Plan ready", tasks=len(plan.tasks), source=source,
             cost=plan.total_estimated_cost)
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 3: EXECUTE
# ═══════════════════════════════════════════════════════════════════════════════

def _phase_execute(result, dry_run=False):
    """Run each task in dependency order."""
    log.info("Phase 3: EXECUTE", workflow_id=result.workflow_id, dry_run=dry_run)

    from task_decomposer import TaskPlan, execute_task

    plan = TaskPlan.from_dict(result.plan)
    plan.status = "executing"

    if dry_run:
        log.info("Dry run — skipping execution", tasks=len(plan.tasks))
        result.task_results = [
            {"task_id": t["id"], "title": t["title"], "status": "skipped (dry-run)"}
            for t in plan.tasks
        ]
        return result

    waves = plan.get_parallel_groups()

    for wave_idx, wave in enumerate(waves, 1):
        log.info("Executing wave", wave=wave_idx, tasks=len(wave))

        for task in wave:
            task["status"] = "running"
            task["started_at"] = datetime.now(timezone.utc).isoformat()

            success, envelope_path, err = execute_task(task)

            task["completed_at"] = datetime.now(timezone.utc).isoformat()

            if success:
                task["status"] = "complete"
                task["result_envelope"] = envelope_path
            else:
                task["status"] = "failed"
                task["error"] = err
                log.warning("Task failed", task_id=task["id"], error=err)

            result.task_results.append({
                "task_id": task["id"],
                "title": task["title"],
                "skill": task.get("skill"),
                "status": task["status"],
                "envelope_path": envelope_path,
                "error": err,
            })

    # Update plan in result
    result.plan = plan.to_dict()

    failed = [t for t in result.task_results if t["status"] == "failed"]
    if failed:
        log.warning("Some tasks failed", failed=len(failed), total=len(result.task_results))

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 4: VALIDATE
# ═══════════════════════════════════════════════════════════════════════════════

def _phase_validate(result):
    """Run quality gate on all outputs."""
    log.info("Phase 4: VALIDATE", workflow_id=result.workflow_id)

    from quality_gate import QualityGate

    gate = QualityGate()
    all_passed = True

    for task_res in result.task_results:
        if task_res["status"] != "complete" or not task_res.get("envelope_path"):
            continue

        # Read the artifact from the envelope
        try:
            with open(task_res["envelope_path"]) as f:
                envelope = json.load(f)
            artifact_path = envelope.get("artifact_path")
            if artifact_path and Path(artifact_path).exists():
                content = Path(artifact_path).read_text()
            else:
                # Use the last step output
                outputs = envelope.get("outputs", {})
                content = str(outputs.get("artifact_path") or outputs.get(
                    list(outputs.keys())[-1] if outputs else "", ""))
        except Exception as e:
            log.warning("Cannot read envelope for validation", path=task_res["envelope_path"], error=str(e))
            continue

        if not content or len(content.strip()) < 10:
            continue

        gate_result = gate.validate(
            content=content,
            agent_id=result.agent_id,
            output_type=_infer_output_type(task_res.get("skill", "")),
            skill_id=task_res.get("skill"),
            output_id=task_res["task_id"],
        )

        result.gate_results.append({
            "task_id": task_res["task_id"],
            "passed": gate_result.passed,
            "verdict": gate_result.verdict,
            "critical_failures": gate_result.critical_failures,
            "score": getattr(gate_result, "score", None),
        })

        if not gate_result.passed:
            all_passed = False
            log.warning("Quality gate failed", task_id=task_res["task_id"],
                        verdict=gate_result.verdict)

    log.info("Validation complete", all_passed=all_passed, checked=len(result.gate_results))
    return result


def _infer_output_type(skill_id):
    """Map skill ID prefix to quality gate output type."""
    if not skill_id:
        return "general"
    prefix = skill_id.split("-")[0] if "-" in skill_id else skill_id
    mapping = {
        "a": "architecture",
        "b": "code",
        "cnt": "creative",
        "k": "research",
        "f": "product_spec",
        "biz": "analysis",
        "doc": "documentation",
    }
    for key, val in mapping.items():
        if prefix.startswith(key):
            return val
    return "general"


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 5: DOCUMENT
# ═══════════════════════════════════════════════════════════════════════════════

def _phase_document(result):
    """Write workflow log, reasoning trace, and link to project."""
    log.info("Phase 5: DOCUMENT", workflow_id=result.workflow_id)

    from decision_log import DecisionLog

    # Log the workflow decision
    dl = DecisionLog()
    dec_id, _warnings = dl.propose(
        owner=result.agent_id,
        title=f"Task workflow: {result.goal[:80]}",
        context=f"Executed via create_task_workflow with approach: "
                f"{result.selected_approach.get('title', 'unknown') if result.selected_approach else 'none'}",
        source_type="workflow",
        source_workflow=result.workflow_id,
    )

    # Mark as decided
    failed = [t for t in result.task_results if t["status"] == "failed"]
    gate_failed = [g for g in result.gate_results if not g["passed"]]

    if not failed and not gate_failed:
        dl.decide(dec_id, "Workflow completed successfully",
                  rationale=f"{len(result.task_results)} tasks executed, all gates passed")
    else:
        dl.decide(dec_id, "Workflow completed with issues",
                  rationale=f"{len(failed)} tasks failed, {len(gate_failed)} gates failed")

    # Save workflow result
    result.completed_at = datetime.now(timezone.utc).isoformat()
    result.status = "complete"
    result.log_path = result.save()

    log.info("Workflow documented", log_path=result.log_path, decision_id=dec_id)
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def create_task_workflow(goal, agent_id, project_id=None, dry_run=False):
    """Execute the full 5-phase task workflow.

    Phase 1: BRAINSTORM — agent generates 3 approaches via LLM
    Phase 2: PLAN — pick best approach, decompose into steps
    Phase 3: EXECUTE — run each step, create files/deliverables
    Phase 4: VALIDATE — check outputs, run quality gate
    Phase 5: DOCUMENT — write logs, reasoning, save to project

    Args:
        goal: High-level objective string.
        agent_id: Agent responsible for this workflow.
        project_id: Optional project to link results to.
        dry_run: If True, skip actual skill execution.

    Returns:
        WorkflowResult with all phase outputs.
    """
    import time

    result = WorkflowResult(goal, agent_id, project_id)
    log.info("Starting task workflow", workflow_id=result.workflow_id,
             goal=goal, agent_id=agent_id, project_id=project_id)

    phases = [
        ("brainstorm", _phase_brainstorm),
        ("plan", _phase_plan),
        ("execute", lambda r: _phase_execute(r, dry_run=dry_run)),
        ("validate", _phase_validate),
        ("document", _phase_document),
    ]

    for phase_name, phase_fn in phases:
        t0 = time.time()
        result.status = phase_name

        try:
            result = phase_fn(result)
        except Exception as e:
            log.error("Phase failed", phase=phase_name, error=str(e))
            result.error = f"Phase {phase_name} error: {e}"
            result.status = "failed"
            result.save()
            return result

        elapsed = round(time.time() - t0, 2)
        result.phase_timings[phase_name] = elapsed

        if result.status == "failed":
            log.error("Workflow aborted", phase=phase_name, error=result.error)
            result.save()
            return result

    # Calculate total cost from plan
    if result.plan:
        result.total_cost = result.plan.get("total_actual_cost", 0) or result.plan.get(
            "total_estimated_cost", 0)

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="NemoClaw 5-Phase Task Workflow")
    parser.add_argument("--goal", required=True, help="High-level goal to achieve")
    parser.add_argument("--agent", required=True, help="Agent ID (e.g. content_lead, strategy_lead)")
    parser.add_argument("--project", default=None, help="Project ID to link results to")
    parser.add_argument("--dry-run", action="store_true", help="Skip actual skill execution")
    args = parser.parse_args()

    result = create_task_workflow(
        goal=args.goal,
        agent_id=args.agent,
        project_id=args.project,
        dry_run=args.dry_run,
    )

    print()
    print("=" * 60)
    print(f"  Task Workflow: {result.workflow_id}")
    print(f"  Goal: {result.goal}")
    print(f"  Agent: {result.agent_id}")
    print(f"  Status: {result.status}")
    print(f"  Approaches: {len(result.approaches)}")

    if result.selected_approach:
        print(f"  Selected: {result.selected_approach.get('title', '?')}")

    if result.plan:
        print(f"  Plan: {len(result.plan.get('tasks', []))} tasks (source: {result.plan_source})")

    if result.task_results:
        ok = sum(1 for t in result.task_results if t["status"] == "complete")
        fail = sum(1 for t in result.task_results if t["status"] == "failed")
        print(f"  Execution: {ok} passed, {fail} failed")

    if result.gate_results:
        gated = sum(1 for g in result.gate_results if g["passed"])
        print(f"  Quality: {gated}/{len(result.gate_results)} passed")

    if result.phase_timings:
        total = sum(result.phase_timings.values())
        print(f"  Timing: {total:.1f}s total")
        for phase, secs in result.phase_timings.items():
            print(f"    {phase}: {secs:.1f}s")

    if result.error:
        print(f"  Error: {result.error}")

    if result.log_path:
        print(f"  Log: {result.log_path}")

    print("=" * 60)

    return 0 if result.status == "complete" else 1


if __name__ == "__main__":
    sys.exit(main())
