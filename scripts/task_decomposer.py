#!/usr/bin/env python3
"""
NemoClaw Task Decomposition & Execution Control v1.0 (MA-5)

Takes a high-level goal and produces an executable plan:
- Hybrid decomposition (templates for known patterns, LLM for novel goals)
- Atomic tasks assigned to agents via capability registry
- Dependency graph with topological execution order
- Cost estimation from routing config
- Parallel execution capped at 5 concurrent tasks
- Auto-execute for plans under $15, approval required above

Usage:
  python3 scripts/task_decomposer.py --decompose "Research AI agents and build a product spec"
  python3 scripts/task_decomposer.py --execute plan.json
  python3 scripts/task_decomposer.py --decompose "..." --dry-run
  python3 scripts/task_decomposer.py --templates
"""

import argparse
import concurrent.futures
import json
import os
import re
import subprocess
import sys
import time
import uuid
import yaml
from datetime import datetime, timezone
from pathlib import Path

REPO = Path.home() / "nemoclaw-local-foundation"
SKILLS_DIR = REPO / "skills"
PYTHON = str(REPO / ".venv313" / "bin" / "python3")
RUNNER = str(SKILLS_DIR / "skill-runner.py")
PLANS_DIR = Path.home() / ".nemoclaw" / "plans"
CHECKPOINT_DB = Path.home() / ".nemoclaw" / "checkpoints" / "langgraph.db"

AUTO_APPROVE_THRESHOLD_USD = 999999.0  # DISABLED — agents have full autonomy (2026-04-02)
MAX_CONCURRENT_TASKS = 5
DEFAULT_COST_PER_SKILL = 0.15  # conservative estimate


# ═══════════════════════════════════════════════════════════════════════════════
# TASK
# ═══════════════════════════════════════════════════════════════════════════════

def new_task(title, description, assigned_to, capability, skill, inputs,
             depends_on=None, priority=5, execution_mode="sequential",
             estimated_cost_usd=None):
    """Create a new task entry."""
    return {
        "id": f"task_{uuid.uuid4().hex[:6]}",
        "title": title,
        "description": description,
        "assigned_to": assigned_to,
        "capability": capability,
        "skill": skill,
        "inputs": inputs,
        "depends_on": depends_on or [],
        "blocks": [],
        "execution_mode": execution_mode,
        "priority": priority,
        "estimated_cost_usd": estimated_cost_usd or _estimate_skill_cost(skill),
        "estimated_duration_s": 300,
        "status": "pending",
        "result_envelope": None,
        "started_at": None,
        "completed_at": None,
        "error": None,
        "confidence": 0.0,
        "retry_policy": {"max_retries": 1, "fallback_agent": None},
        "retries_used": 0,
        "expected_outputs": [],
    }


def _estimate_skill_cost(skill_id):
    """Estimate cost for running a skill based on routing config and chain awareness.

    If the skill is tier 3/4 with a task_domain, the cost estimate accounts for
    multi-step chain routing (3-4 LLM calls per chain step).
    """
    try:
        rc_path = REPO / "config" / "routing" / "routing-config.yaml"
        with open(rc_path) as f:
            rcfg = yaml.safe_load(f)

        # Try to read skill's task_class from yaml
        skill_yaml = SKILLS_DIR / skill_id / "skill.yaml"
        if skill_yaml.exists():
            with open(skill_yaml) as f:
                spec = yaml.safe_load(f)
            steps = spec.get("steps", [])
            num_llm_steps = max(len(steps) - 1, 3)

            task_class = steps[0].get("task_class", "moderate") if steps else "moderate"
            alias = rcfg.get("routing_rules", {}).get(task_class, "cheap_openai")
            cost_per_call = rcfg.get("providers", {}).get(alias, {}).get("estimated_cost_per_call", 0.06)

            # Check if this skill uses chain routing (tier 3/4 with task_domain)
            tier = rcfg.get("tier_mapping", {}).get(task_class, 2)
            task_domain = _get_skill_domain(skill_id)
            if tier >= 3 and task_domain:
                # Chain routing: generation step gets chain-routed (3-4 API calls),
                # other steps (critic, improve) remain single calls.
                # Estimate: 1 chain + (num_llm_steps - 1) single calls
                chain_steps = 4 if tier >= 4 else 3
                chain_cost = cost_per_call * chain_steps  # one chained generation
                other_cost = cost_per_call * max(num_llm_steps - 1, 0)  # remaining single calls
                return round(chain_cost + other_cost, 3)

            return round(cost_per_call * num_llm_steps, 3)
    except Exception:
        pass
    return DEFAULT_COST_PER_SKILL


def _get_skill_domain(skill_id):
    """Look up task_domain from capability-registry.yaml."""
    try:
        reg_path = REPO / "config" / "agents" / "capability-registry.yaml"
        with open(reg_path) as f:
            reg = yaml.safe_load(f)
        return reg.get("skill_domains", {}).get(skill_id)
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# PLAN
# ═══════════════════════════════════════════════════════════════════════════════

class TaskPlan:
    """An executable plan of atomic tasks."""

    def __init__(self, goal, tasks=None, plan_id=None):
        self.plan_id = plan_id or f"plan_{uuid.uuid4().hex[:8]}"
        self.goal = goal
        self.tasks = tasks or []
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.status = "draft"  # draft | approved | executing | complete | failed
        self.total_estimated_cost = 0.0
        self.total_actual_cost = 0.0

        # Resolve blocks (reverse of depends_on)
        self._resolve_blocks()
        self._calculate_cost()

    def _resolve_blocks(self):
        """Build blocks[] from depends_on[] relationships."""
        id_map = {t["id"]: t for t in self.tasks}
        for t in self.tasks:
            t["blocks"] = []
        for t in self.tasks:
            for dep_id in t.get("depends_on", []):
                if dep_id in id_map:
                    if t["id"] not in id_map[dep_id]["blocks"]:
                        id_map[dep_id]["blocks"].append(t["id"])

    def _calculate_cost(self):
        self.total_estimated_cost = round(
            sum(t.get("estimated_cost_usd", 0) for t in self.tasks), 3
        )

    def get_ready_tasks(self):
        """Get tasks whose dependencies are all complete."""
        complete_ids = {t["id"] for t in self.tasks if t["status"] == "complete"}
        ready = []
        for t in self.tasks:
            if t["status"] != "pending":
                continue
            deps = set(t.get("depends_on", []))
            if deps.issubset(complete_ids):
                ready.append(t)
        return sorted(ready, key=lambda t: -t.get("priority", 5))

    def get_parallel_groups(self):
        """Group tasks into execution waves respecting dependencies.

        Returns list of lists — each inner list can run in parallel.
        """
        complete_ids = set()
        waves = []
        remaining = [t for t in self.tasks if t["status"] == "pending"]

        while remaining:
            wave = []
            for t in remaining:
                deps = set(t.get("depends_on", []))
                if deps.issubset(complete_ids):
                    wave.append(t)
            if not wave:
                # Deadlock — remaining tasks have unresolvable deps
                break
            waves.append(wave)
            complete_ids.update(t["id"] for t in wave)
            remaining = [t for t in remaining if t["id"] not in complete_ids]

        return waves

    def needs_approval(self):
        """Check if plan exceeds auto-approve threshold."""
        return self.total_estimated_cost > AUTO_APPROVE_THRESHOLD_USD

    def summary(self):
        """Print plan summary."""
        print(f"  Plan: {self.plan_id}")
        print(f"  Goal: {self.goal}")
        print(f"  Tasks: {len(self.tasks)}")
        print(f"  Estimated cost: ${self.total_estimated_cost:.2f}")
        print(f"  Needs approval: {'YES (>${:.0f})'.format(AUTO_APPROVE_THRESHOLD_USD) if self.needs_approval() else 'No (auto-execute)'}")
        print()

        waves = self.get_parallel_groups()
        for i, wave in enumerate(waves, 1):
            mode = "PARALLEL" if len(wave) > 1 else "SEQUENTIAL"
            print(f"  Wave {i} [{mode}]:")
            for t in wave:
                deps = f" ← {t['depends_on']}" if t['depends_on'] else ""
                print(f"    [{t['priority']}] {t['id']}: {t['title']}")
                print(f"        agent={t['assigned_to']} skill={t['skill']} cost=${t['estimated_cost_usd']:.3f}{deps}")

    def to_dict(self):
        return {
            "plan_id": self.plan_id,
            "goal": self.goal,
            "created_at": self.created_at,
            "status": self.status,
            "total_estimated_cost": self.total_estimated_cost,
            "total_actual_cost": self.total_actual_cost,
            "tasks": self.tasks,
        }

    @classmethod
    def from_dict(cls, data):
        plan = cls(data["goal"], data.get("tasks", []), data.get("plan_id"))
        plan.created_at = data.get("created_at", plan.created_at)
        plan.status = data.get("status", "draft")
        plan.total_actual_cost = data.get("total_actual_cost", 0)
        return plan

    def replan(self, failed_task_id=None):
        """Reset failed + downstream tasks to pending for re-execution."""
        reset = []
        if failed_task_id:
            for t in self.tasks:
                if t["id"] == failed_task_id:
                    t["status"] = "pending"
                    t["error"] = None
                    t["result_envelope"] = None
                    t["retries_used"] = 0
                    reset.append(t["id"])
                    break
            queue = [failed_task_id]
            while queue:
                current = queue.pop(0)
                for t in self.tasks:
                    if current in t.get("depends_on", []) and t["status"] in ("skipped", "failed"):
                        t["status"] = "pending"
                        t["error"] = None
                        reset.append(t["id"])
                        queue.append(t["id"])
        else:
            for t in self.tasks:
                if t["status"] in ("failed", "skipped"):
                    t["status"] = "pending"
                    t["error"] = None
                    t["retries_used"] = 0
                    reset.append(t["id"])
        self.status = "executing"
        self._resolve_blocks()
        return reset

    def save(self):
        PLANS_DIR.mkdir(parents=True, exist_ok=True)
        path = PLANS_DIR / f"{self.plan_id}.json"
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        return path


# ═══════════════════════════════════════════════════════════════════════════════
# TEMPLATES (known patterns)
# ═══════════════════════════════════════════════════════════════════════════════

TEMPLATES = {
    "market_to_product": {
        "description": "Research a market, write product requirements, define pricing",
        "triggers": ["market research.*product", "research.*requirements.*pricing",
                      "analyze market.*build product"],
        "tasks": [
            {"title": "Market Research", "capability": "market_research",
             "assigned_to": "strategy_lead", "skill": "e12-market-research-analyst",
             "input_map": {"research_topic": "topic", "industry_context": "context"},
             "priority": 9},
            {"title": "Product Requirements", "capability": "product_requirements",
             "assigned_to": "product_architect", "skill": "f09-product-req-writer",
             "input_map": {"product_idea": "topic", "target_audience": "audience",
                           "scope_level": "mvp"},
             "depends_on_idx": [0], "priority": 8},
            {"title": "Pricing Strategy", "capability": "pricing_strategy",
             "assigned_to": "growth_revenue_lead", "skill": "f09-pricing-strategist",
             "input_map": {"product_description": "topic", "target_market": "context",
                           "pricing_scope": "mvp"},
             "depends_on_idx": [1], "priority": 7},
        ]
    },
    "validate_and_scope": {
        "description": "Validate a business idea, then scope the MVP",
        "triggers": ["validate.*idea.*scope", "business idea.*mvp",
                      "validate.*mvp"],
        "tasks": [
            {"title": "Business Validation", "capability": "business_validation",
             "assigned_to": "strategy_lead", "skill": "j36-biz-idea-validator",
             "input_map": {"business_idea": "topic", "target_market": "context",
                           "competitive_landscape": "competitors"},
             "priority": 9},
            {"title": "MVP Scoping", "capability": "mvp_scoping",
             "assigned_to": "strategy_lead", "skill": "j36-mvp-scope-definer",
             "input_map": {"product_idea": "topic", "target_audience": "context",
                           "resource_constraints": "constraints", "timeline": "timeline"},
             "depends_on_idx": [0], "priority": 8},
        ]
    },
    "research_and_document": {
        "description": "Research a topic and write documentation",
        "triggers": ["research.*document", "analyze.*write.*doc",
                      "research.*knowledge base"],
        "tasks": [
            {"title": "Research", "capability": "market_research",
             "assigned_to": "strategy_lead", "skill": "e12-market-research-analyst",
             "input_map": {"research_topic": "topic", "industry_context": "context"},
             "priority": 9},
            {"title": "Documentation", "capability": "kb_article",
             "assigned_to": "narrative_content_lead", "skill": "e08-kb-article-writer",
             "input_map": {"topic": "topic", "article_type": "how-to",
                           "target_audience": "developer"},
             "depends_on_idx": [0], "priority": 7},
        ]
    },
    "full_product_pipeline": {
        "description": "End-to-end: research, requirements, architecture, scaffold, docs",
        "triggers": ["full product.*pipeline", "end.to.end.*product",
                      "research.*build.*document"],
        "tasks": [
            {"title": "Market Research", "capability": "market_research",
             "assigned_to": "strategy_lead", "skill": "e12-market-research-analyst",
             "input_map": {"research_topic": "topic", "industry_context": "context"},
             "priority": 10},
            {"title": "Competitive Analysis", "capability": "competitive_intelligence",
             "assigned_to": "strategy_lead", "skill": "e08-comp-intel-synth",
             "input_map": {"competitor_data": "competitors", "focus_company": "topic",
                           "industry_context": "context"},
             "priority": 9},
            {"title": "Product Requirements", "capability": "product_requirements",
             "assigned_to": "product_architect", "skill": "f09-product-req-writer",
             "input_map": {"product_idea": "topic", "target_audience": "audience",
                           "scope_level": "mvp"},
             "depends_on_idx": [0, 1], "priority": 8},
            {"title": "Architecture Spec", "capability": "architecture_spec",
             "assigned_to": "product_architect", "skill": "a01-arch-spec-writer",
             "input_map": {"subsystem_name": "topic", "subsystem_concept": "topic"},
             "depends_on_idx": [2], "priority": 7},
            {"title": "Project Scaffold", "capability": "scaffold_generation",
             "assigned_to": "engineering_lead", "skill": "b05-scaffold-gen",
             "input_map": {"project_type": "cli-tool", "language": "python",
                           "feature_requirements": "topic", "project_name": "project"},
             "depends_on_idx": [3], "priority": 6},
            {"title": "Pricing Strategy", "capability": "pricing_strategy",
             "assigned_to": "growth_revenue_lead", "skill": "f09-pricing-strategist",
             "input_map": {"product_description": "topic", "target_market": "context",
                           "pricing_scope": "mvp"},
             "depends_on_idx": [2], "priority": 6},
        ]
    },
}


def match_template(goal):
    """Find a matching template for the goal.

    Returns: (template_name, template) or (None, None)
    """
    goal_lower = goal.lower()
    for name, template in TEMPLATES.items():
        for trigger in template.get("triggers", []):
            if re.search(trigger, goal_lower, re.IGNORECASE):
                return name, template
    return None, None


def instantiate_template(template, goal, extra_inputs=None):
    """Create a TaskPlan from a template and goal."""
    extra = extra_inputs or {}

    # Extract likely topic/context from goal
    inferred = {
        "topic": goal,
        "context": extra.get("context", extra.get("target_market", goal)),
        "audience": extra.get("audience", "technical professionals"),
        "market": extra.get("market", goal),
        "idea": goal,
        "competitors": extra.get("competitors", extra.get("competitive_landscape", "Major existing players in the space")),
        "project": extra.get("project", "new-project"),
        "constraints": extra.get("constraints", extra.get("resource_constraints", "Small team, limited budget, 3-month runway")),
        "timeline": extra.get("timeline", "90 days from project kickoff to MVP launch"),
    }

    tasks = []
    task_ids = []

    for i, t_def in enumerate(template["tasks"]):
        # Map inputs
        inputs = {}
        for input_key, source_key in t_def.get("input_map", {}).items():
            inputs[input_key] = extra.get(input_key, inferred.get(source_key, goal))

        # Resolve dependencies
        depends_on = []
        for dep_idx in t_def.get("depends_on_idx", []):
            if dep_idx < len(task_ids):
                depends_on.append(task_ids[dep_idx])

        # Determine execution mode
        exec_mode = "parallel" if not depends_on else "sequential"

        task = new_task(
            title=t_def["title"],
            description=f"{t_def['title']} for: {goal[:80]}",
            assigned_to=t_def["assigned_to"],
            capability=t_def["capability"],
            skill=t_def["skill"],
            inputs=inputs,
            depends_on=depends_on,
            priority=t_def.get("priority", 5),
            execution_mode=exec_mode,
        )
        tasks.append(task)
        task_ids.append(task["id"])

    return TaskPlan(goal, tasks)


# ═══════════════════════════════════════════════════════════════════════════════
# LLM DECOMPOSITION (novel goals)
# ═══════════════════════════════════════════════════════════════════════════════

def decompose_with_llm(goal, extra_inputs=None):
    """Use LLM to decompose a novel goal into tasks."""

    # Load capability registry
    reg_path = REPO / "config" / "agents" / "capability-registry.yaml"
    with open(reg_path) as f:
        registry = yaml.safe_load(f)

    cap_list = []
    for cap_name, cap in registry.get("capabilities", {}).items():
        req = cap.get("requires_inputs", [])
        cap_list.append(f"  {cap_name}: agent={cap['owned_by']} skill={cap['skill']} inputs={req}")

    catalog = "\n".join(cap_list)

    # Get API key
    env_path = REPO / "config" / ".env"
    api_key = None
    with open(env_path) as f:
        for line in f:
            if "OPENAI_API_KEY" in line and "=" in line:
                api_key = line.strip().split("=", 1)[1].strip()

    # Use lib.routing.call_llm for provider-agnostic LLM calls
    import sys; sys.path.insert(0, str(REPO))
    from lib.routing import call_llm as _route_llm

    prompt = f"""You are a task decomposition engine. Break a goal into atomic tasks.

AVAILABLE CAPABILITIES:
{catalog}

GOAL: {goal}

Respond with ONLY valid JSON (no markdown, no backticks):
{{
  "tasks": [
    {{
      "title": "short task name",
      "description": "what this task does",
      "capability": "capability_name_from_list",
      "inputs": {{"input_name": "value"}},
      "depends_on_indices": [],
      "priority": 8
    }}
  ]
}}

Rules:
- Use ONLY capabilities from the list above
- Provide ALL required inputs for each capability
- depends_on_indices: list of task indices (0-based) that must complete first
- Independent tasks get empty depends_on_indices (can run in parallel)
- Maximum 8 tasks per plan
- Priority: 10=highest, 1=lowest
- Order tasks logically
"""

    text, err = _route_llm(
        [{"role": "user", "content": prompt}],
        task_class="general_short",
        max_tokens=2000,
    )
    if err or not text:
        return None, f"LLM decomposition failed: {err}"

    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        return None, f"LLM returned invalid JSON: {e}"

    # Build tasks
    reg_caps = registry.get("capabilities", {})
    tasks = []
    task_ids = []

    for i, t_def in enumerate(data.get("tasks", [])):
        cap_name = t_def.get("capability", "")
        cap = reg_caps.get(cap_name, {})

        depends_on = []
        for dep_idx in t_def.get("depends_on_indices", []):
            if dep_idx < len(task_ids):
                depends_on.append(task_ids[dep_idx])

        exec_mode = "parallel" if not depends_on else "sequential"

        task = new_task(
            title=t_def.get("title", f"Task {i+1}"),
            description=t_def.get("description", ""),
            assigned_to=cap.get("owned_by", "operations_lead"),
            capability=cap_name,
            skill=cap.get("skill", ""),
            inputs=t_def.get("inputs", {}),
            depends_on=depends_on,
            priority=t_def.get("priority", 5),
            execution_mode=exec_mode,
        )
        tasks.append(task)
        task_ids.append(task["id"])

    return TaskPlan(goal, tasks), None


# ═══════════════════════════════════════════════════════════════════════════════
# HYBRID DECOMPOSITION
# ═══════════════════════════════════════════════════════════════════════════════

def decompose(goal, extra_inputs=None):
    """Hybrid decomposition: template if matched, LLM otherwise.

    Returns: (TaskPlan, source: "template"|"llm", error)
    """
    # Try templates first
    name, template = match_template(goal)
    if template:
        plan = instantiate_template(template, goal, extra_inputs)
        return plan, f"template:{name}", None

    # Fall back to LLM
    plan, err = decompose_with_llm(goal, extra_inputs)
    if err:
        return None, "llm", err
    return plan, "llm", None


# ═══════════════════════════════════════════════════════════════════════════════
# EXECUTION ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def execute_task(task):
    """Execute a single task by running its skill.

    Returns: (success, envelope_path, error)
    """
    if not task.get("skill"):
        return False, None, f"No skill assigned to task {task['id']}"

    skill_dir = SKILLS_DIR / task["skill"]
    if not skill_dir.exists():
        return False, None, f"Skill directory not found: {task['skill']}"

    # Clear checkpoint for clean run
    if CHECKPOINT_DB.exists():
        CHECKPOINT_DB.unlink()

    cmd = [PYTHON, RUNNER, "--skill", task["skill"]]
    for key, value in task.get("inputs", {}).items():
        if isinstance(value, list):
            cmd.extend(["--input", key, ", ".join(str(v) for v in value)])
        else:
            cmd.extend(["--input", key, str(value)])

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=600, cwd=str(REPO)
        )
    except subprocess.TimeoutExpired:
        return False, None, f"Timeout (600s) on {task['skill']}"

    output = result.stdout + result.stderr
    success = "Skill complete" in output

    envelope_path = None
    for line in output.split("\n"):
        if "[envelope]" in line and "Written to:" in line:
            envelope_path = line.split("Written to:")[-1].strip()
            break

    error = None
    if not success:
        for line in output.split("\n"):
            if "ERROR:" in line or '"error"' in line:
                error = line.strip()[:200]
                break
        if not error:
            error = output.strip().split("\n")[-1][:200] if output.strip() else "Unknown error"

    return success, envelope_path, error


def execute_plan(plan, dry_run=False):
    """Execute a full task plan with parallel support.

    Respects dependencies, runs independent tasks in parallel (up to MAX_CONCURRENT),
    tracks cost, and reports progress.
    """
    print("=" * 60)
    print(f"  Executing Plan: {plan.plan_id}")
    print(f"  Goal: {plan.goal}")
    print(f"  Tasks: {len(plan.tasks)}")
    print(f"  Estimated cost: ${plan.total_estimated_cost:.2f}")
    print(f"  Max concurrent: {MAX_CONCURRENT_TASKS}")
    print("=" * 60)
    print()

    if plan.needs_approval() and not dry_run:
        print(f"  ⚠️  Plan exceeds ${AUTO_APPROVE_THRESHOLD_USD:.0f} threshold.")
        print(f"      Estimated: ${plan.total_estimated_cost:.2f}")
        print(f"      Approval required before execution.")
        plan.status = "needs_approval"
        plan.save()
        return False

    if dry_run:
        plan.summary()
        return True

    plan.status = "executing"
    total_start = time.time()
    task_results = {}

    waves = plan.get_parallel_groups()

    for wave_num, wave in enumerate(waves, 1):
        is_parallel = len(wave) > 1
        mode_label = f"PARALLEL ({len(wave)} tasks)" if is_parallel else "SEQUENTIAL"
        print(f"  Wave {wave_num} [{mode_label}]")

        if is_parallel and len(wave) > MAX_CONCURRENT_TASKS:
            # Split into sub-waves
            sub_waves = [wave[i:i+MAX_CONCURRENT_TASKS]
                        for i in range(0, len(wave), MAX_CONCURRENT_TASKS)]
        else:
            sub_waves = [wave]

        for sub_wave in sub_waves:
            if len(sub_wave) > 1:
                # Parallel execution
                with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENT_TASKS) as executor:
                    futures = {}
                    for task in sub_wave:
                        task["status"] = "running"
                        task["started_at"] = datetime.now(timezone.utc).isoformat()
                        print(f"    🔄 {task['id']}: {task['title']} ({task['assigned_to']})")
                        futures[executor.submit(execute_task, task)] = task

                    for future in concurrent.futures.as_completed(futures):
                        task = futures[future]
                        start_t = time.time()
                        try:
                            success, envelope, error = future.result()
                        except Exception as e:
                            success, envelope, error = False, None, str(e)[:200]

                        elapsed = int(time.time() - start_t)
                        if success:
                            task["status"] = "complete"
                            task["result_envelope"] = envelope
                            task["completed_at"] = datetime.now(timezone.utc).isoformat()
                            print(f"    ✅ {task['id']}: {task['title']} ({elapsed}s)")
                        else:
                            task["status"] = "failed"
                            task["error"] = error
                            task["completed_at"] = datetime.now(timezone.utc).isoformat()
                            print(f"    ❌ {task['id']}: {task['title']} ({elapsed}s)")
                            print(f"       {error[:100]}")

                        task_results[task["id"]] = success
            else:
                # Sequential execution
                task = sub_wave[0]
                task["status"] = "running"
                task["started_at"] = datetime.now(timezone.utc).isoformat()
                print(f"    🔄 {task['id']}: {task['title']} ({task['assigned_to']})")

                start_t = time.time()
                success, envelope, error = execute_task(task)
                elapsed = int(time.time() - start_t)

                if success:
                    task["status"] = "complete"
                    task["result_envelope"] = envelope
                    task["completed_at"] = datetime.now(timezone.utc).isoformat()
                    print(f"    ✅ {task['id']}: {task['title']} ({elapsed}s)")
                else:
                    task["status"] = "failed"
                    task["error"] = error
                    task["completed_at"] = datetime.now(timezone.utc).isoformat()
                    print(f"    ❌ {task['id']}: {task['title']} ({elapsed}s)")
                    print(f"       {error[:100]}")

                    # Check if failed task blocks others
                    if task["blocks"]:
                        print(f"       Blocked tasks: {task['blocks']}")
                        for blocked_id in task["blocks"]:
                            for t in plan.tasks:
                                if t["id"] == blocked_id:
                                    t["status"] = "skipped"
                                    t["error"] = f"Blocked by failed {task['id']}"

                task_results[task["id"]] = success
        print()

    # Summary
    total_elapsed = int(time.time() - total_start)
    completed = sum(1 for t in plan.tasks if t["status"] == "complete")
    failed = sum(1 for t in plan.tasks if t["status"] == "failed")
    skipped = sum(1 for t in plan.tasks if t["status"] == "skipped")

    plan.status = "complete" if failed == 0 else "failed"
    plan.total_actual_cost = sum(t.get("estimated_cost_usd", 0) for t in plan.tasks if t["status"] == "complete")

    print("=" * 60)
    print(f"  Plan Complete: {completed}/{len(plan.tasks)} tasks succeeded")
    print(f"  Failed: {failed}, Skipped: {skipped}")
    print(f"  Total time: {total_elapsed}s")
    print(f"  Estimated cost: ${plan.total_estimated_cost:.2f}")
    print(f"  Actual cost: ~${plan.total_actual_cost:.2f}")
    print("=" * 60)

    plan.save()
    print(f"\n  Plan saved: {PLANS_DIR / f'{plan.plan_id}.json'}")

    return failed == 0


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="NemoClaw Task Decomposer & Executor")
    parser.add_argument("--decompose", metavar="GOAL", help="Decompose a goal into tasks")
    parser.add_argument("--execute", metavar="PLAN_JSON", help="Execute a saved plan")
    parser.add_argument("--dry-run", action="store_true", help="Show plan without executing")
    parser.add_argument("--templates", action="store_true", help="List available templates")
    parser.add_argument("--cost-estimate", metavar="GOAL", help="Estimate cost for a goal")
    parser.add_argument("--status", metavar="PLAN_ID", help="Show plan status")
    parser.add_argument("--input", nargs=2, action="append", metavar=("KEY", "VALUE"),
                       help="Extra inputs for decomposition")
    args = parser.parse_args()

    if args.templates:
        print(f"Available templates ({len(TEMPLATES)}):")
        for name, tmpl in TEMPLATES.items():
            print(f"  {name}: {tmpl['description']}")
            print(f"    Tasks: {len(tmpl['tasks'])}")
            print(f"    Triggers: {tmpl['triggers'][:2]}")
            print()
        return

    extra_inputs = {}
    if args.input:
        for key, value in args.input:
            extra_inputs[key] = value

    if args.decompose:
        print(f"Decomposing: {args.decompose}")
        plan, source, error = decompose(args.decompose, extra_inputs)

        if error:
            print(f"  ❌ Decomposition failed: {error}")
            sys.exit(1)

        print(f"  Source: {source}")
        print()
        plan.summary()

        if args.dry_run:
            return

        # Save plan
        path = plan.save()
        print(f"  Plan saved: {path}")

        # Auto-execute or request approval
        if plan.needs_approval():
            print(f"\n  ⚠️  Cost ${plan.total_estimated_cost:.2f} > ${AUTO_APPROVE_THRESHOLD_USD:.0f} threshold")
            print(f"  Run: python3 scripts/task_decomposer.py --execute {path}")
        else:
            print(f"\n  Auto-executing (${plan.total_estimated_cost:.2f} < ${AUTO_APPROVE_THRESHOLD_USD:.0f})...")
            execute_plan(plan)

    elif args.execute:
        path = args.execute
        if not os.path.exists(path):
            # Try plans dir
            path = str(PLANS_DIR / args.execute)
        if not os.path.exists(path):
            print(f"Plan not found: {args.execute}")
            sys.exit(1)

        with open(path) as f:
            data = json.load(f)
        plan = TaskPlan.from_dict(data)

        if args.dry_run:
            plan.summary()
        else:
            execute_plan(plan)

    elif args.cost_estimate:
        plan, source, error = decompose(args.cost_estimate, extra_inputs)
        if error:
            print(f"  ❌ {error}")
            sys.exit(1)
        print(f"  Source: {source}")
        print(f"  Tasks: {len(plan.tasks)}")
        print(f"  Estimated cost: ${plan.total_estimated_cost:.2f}")
        print(f"  Needs approval: {'Yes' if plan.needs_approval() else 'No'}")
        for t in plan.tasks:
            print(f"    ${t['estimated_cost_usd']:.3f} — {t['title']} ({t['skill']})")

    elif args.status:
        path = PLANS_DIR / f"{args.status}.json"
        if not path.exists():
            print(f"Plan not found: {args.status}")
            sys.exit(1)
        with open(path) as f:
            data = json.load(f)
        plan = TaskPlan.from_dict(data)
        plan.summary()
        for t in plan.tasks:
            status_icon = {"pending": "⏳", "running": "🔄", "complete": "✅",
                          "failed": "❌", "skipped": "⏭️"}.get(t["status"], "?")
            print(f"  {status_icon} {t['id']}: {t['title']} [{t['status']}]")
            if t.get("error"):
                print(f"     Error: {t['error'][:80]}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
