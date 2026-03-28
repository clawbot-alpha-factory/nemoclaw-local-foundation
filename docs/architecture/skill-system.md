# Skill System

> **Location:** `docs/architecture/skill-system.md`
> **Version:** 2.0
> **Date:** 2026-03-28
> **Phase:** MA-4 — Multi-Agent System
> **Source of truth:** `skills/skill-runner.py` v4.0 + 30 skills across 10 families
> **Schema:** skill-yaml-schema-v2
> **Meta-skills:** g26-skill-spec-writer + g26-skill-template-gen (~$0.25/skill)
> **Testing:** test-all.py with per-skill test-input.json (30/30 passing)
> **Chaining:** --input-from envelope path for skill-to-skill data flow

---

## Purpose

This document explains how Skills work in the NemoClaw local foundation — how they are defined, how they execute, how state is managed, how to create new ones, and how to resume interrupted runs.

---

## What a Skill Is

A Skill is a structured multi-step workflow that takes defined inputs, executes a sequence of LLM-powered steps, and produces defined outputs. Each step routes through the model routing and budget system.

A Skill is not a single prompt. It is a governed pipeline with typed inputs, typed outputs, per-step routing, checkpointed state, validation rules, and audit logging.

---

## Skill Architecture

```
skill.yaml (definition)
     │
     ▼
skill-runner.py reads definition
     │
     ▼
Builds LangGraph StateGraph from steps
     │
     ▼
For each step:
  ├── budget-enforcer resolves task_class → alias → model
  ├── Inference call via langchain
  ├── Cost logged to provider-usage.jsonl
  ├── Step result stored in SkillState (TypedDict)
  └── Checkpoint saved to langgraph.db
     │
     ▼
Final step writes artifact to outputs/
     │
     ▼
Thread ID printed for resume reference
```

---

## Key Components

| Component | Location | Purpose |
|---|---|---|
| skill-runner.py | skills/ | LangGraph execution engine v4.0 — reads skill.yaml + run.py, builds graph, runs steps, writes envelope |
| skill.yaml | skills/{name}/ | Skill definition — inputs, outputs, steps, routing, validation, approval |
| outputs/ | skills/{name}/outputs/ | Artifact storage (gitignored) |
| langgraph.db | ~/.nemoclaw/checkpoints/ | LangGraph SqliteSaver checkpoint database |

---

## Directory Structure for a Skill

Every skill follows this layout:

```
skills/
├── skill-runner.py              # Shared execution engine v4.0
└── {skill-name}/
    ├── skill.yaml               # Skill definition (committed)
    ├── run.py                   # Skill implementation (committed)
    ├── test-input.json          # Regression test inputs (committed)
    ├── outputs/                  # Artifacts + envelopes (gitignored)
    │   ├── {skill}_*.md         # Markdown artifact
    │   └── {skill}_*_envelope.json  # JSON envelope for chaining
    └── README.md                # Optional usage notes
```

---

## skill.yaml Specification

The skill.yaml is the complete definition of a skill. It controls everything — inputs, outputs, steps, routing, validation, and approval.

### Top-Level Fields

| Field | Type | Required | Description |
|---|---|---|---|
| name | string | Yes | Skill identifier (must match directory name) |
| version | string | Yes | Semantic version |
| description | string | Yes | What the skill does |
| author | string | Yes | Creator |
| created | date | Yes | Creation date |
| schema_version | integer | Yes | skill.yaml schema version (currently 1) |
| runner_version_required | string | Yes | Minimum skill-runner.py version |
| routing_system_version_required | string | Yes | Minimum routing system version |
| compatibility_notes | string | No | Known compatibility requirements |

### Inputs Section

Defines what the skill accepts. Each input has a name, type, required flag, default, description, and validation rules.

```yaml
inputs:
  - name: topic
    type: string
    required: true
    description: The research topic to investigate
    validation:
      min_length: 5
      max_length: 500

  - name: depth
    type: string
    required: false
    default: standard
    description: Depth of research
    validation:
      allowed_values: [brief, standard, deep]
```

### Outputs Section

Defines what the skill produces. Includes validation rules for output quality.

```yaml
outputs:
  - name: brief
    type: string
    description: Structured research brief in markdown
    validation:
      min_length: 200
      must_contain_sections: [Background, Key Findings, Open Questions, Recommendations]

  - name: brief_file
    type: file_path
    description: Path to the written markdown artifact
```

### Artifacts Section

Controls how output files are written and stored.

```yaml
artifacts:
  storage_location: skills/research-brief/outputs/
  filename_pattern: "research_brief_{workflow_id}_{timestamp}.md"
  format: markdown
  committed_to_repo: false
  gitignored: true
  resume_reads_prior_output: true
  prior_output_key: brief_file
```

### Steps Section

Each step defines one node in the LangGraph StateGraph.

```yaml
steps:
  - id: step_1
    name: Validate input and plan research
    task_class: general_short
    description: Validate topic input and create a research plan
    input_source: inputs.topic
    output_key: research_plan
    idempotency:
      rerunnable: true
      cached: false
      never_auto_rerun: false
    requires_human_approval: false
    approval_class: safe
    failure_condition: topic is empty or too short
    next_step_condition: research_plan is not empty
```

**Step fields:**

| Field | Purpose |
|---|---|
| id | Unique step identifier (step_1, step_2, etc.) |
| name | Human-readable step name |
| task_class | Routes to a model alias via routing-config.yaml |
| description | What this step does |
| input_source | Where this step reads its input from |
| output_key | Key name for this step's output in SkillState |
| idempotency | Whether the step can be safely re-run |
| requires_human_approval | Whether to pause for human approval before executing |
| approval_class | safe, approval_gated, or blocked_external |
| failure_condition | What constitutes failure for this step |
| next_step_condition | What must be true to proceed to the next step |

### Validation Section

Defines input and output validation rules and what happens on failure.

```yaml
validation:
  input:
    - rule: topic must be at least 5 characters
  output:
    - rule: brief must contain Background section
  failure_conditions:
    - condition: model returns empty response
      action: retry once — if retry fails set status to failed
    - condition: artifact write fails
      action: pause with status failed — preserve step_4 output in checkpoint
```

### Approval Boundaries Section

Classifies each step's safety level.

```yaml
approval_boundaries:
  safe_steps: [step_1, step_2, step_3, step_4, step_5]
  approval_gated_steps: []
  blocked_external_effect_steps: []
  notes: >
    v1 is fully local. No external writes, no API side effects beyond inference.
```

### Routing Section

Skill-level routing defaults.

```yaml
routing:
  default_alias: cheap_openai
  allow_override: false
```

---

## Running a Skill

### Standard run

```bash
~/nemoclaw-local-foundation/.venv312/bin/python \
  ~/nemoclaw-local-foundation/skills/skill-runner.py \
  --skill research-brief \
  --input topic "your topic here" \
  --input depth standard
```

**Important:** Use `.venv312/bin/python`, not system python3. skill-runner.py imports LangGraph and langchain, which require Python 3.12.

### What happens during execution

1. skill-runner.py loads `skills/research-brief/skill.yaml`
2. A thread ID is generated: `skill-research-brief-{date}-{time}-{hash}`
3. A LangGraph StateGraph is built with one node per step
4. Each step executes in sequence, printing progress:
   ```
   [node] step_1: Validate input and plan research
     [budget] alias=cheap_openai model=gpt-5.4-mini cost=$0.0004 remaining=$9.8782
   [done] step_1
   ```
5. After each step, state is checkpointed to langgraph.db
6. The final step writes the artifact to the outputs directory
7. The thread ID and output path are printed

### Output

```
Skill complete: research-brief
Thread ID: skill-research-brief-20260324-121719-ad57cb1c
Output: /Users/core88/nemoclaw-local-foundation/skills/research-brief/outputs/research_brief_skill-research-brief-20260324-121719-ad57cb1c_20260324_121818.md
```

---

## Resuming a Paused or Failed Skill

If a skill run is interrupted (crash, Ctrl+C, reboot), it can be resumed from the last checkpoint.

### Resume command

```bash
~/nemoclaw-local-foundation/.venv312/bin/python \
  ~/nemoclaw-local-foundation/skills/skill-runner.py \
  --skill research-brief \
  --thread-id skill-research-brief-20260324-121719-ad57cb1c \
  --resume
```

**How resume works:**

1. skill-runner.py reads the thread ID from the command line
2. LangGraph loads the last checkpoint for that thread from langgraph.db
3. Execution continues from the step after the last completed checkpoint
4. If the checkpoint is at step_3, steps 1–3 are skipped and step_4 runs next

**When to resume vs restart:**

| Situation | Action |
|---|---|
| Clean interruption (Ctrl+C between steps) | Resume — checkpoint is clean |
| Crash during API call | Restart — partial response may corrupt state |
| Reboot | Check checkpoint DB, then decide. See restart-recovery-runbook.md |
| Unsure | Restart from scratch — safer than resuming from unknown state |

### Restart from scratch

Just run the skill again without `--thread-id` or `--resume`. A new thread ID is generated.

---

## State Management

### SkillState TypedDict

All step inputs and outputs flow through a shared state dictionary. Each step reads from and writes to named keys.

```
SkillState = {
  "topic": "...",           # From user input
  "depth": "standard",     # From user input
  "research_plan": "...",   # Written by step_1
  "raw_research": "...",    # Written by step_2
  "structured_brief": "...", # Written by step_3
  "validated_brief": "...",  # Written by step_4
  "brief_file": "/path/..." # Written by step_5
}
```

### Checkpointing

After every step completes, the full SkillState is checkpointed to the SQLite database.

| Setting | Value |
|---|---|
| Checkpoint backend | LangGraph SqliteSaver |
| Database location | ~/.nemoclaw/checkpoints/langgraph.db |
| Checkpoint granularity | Per step (after each step completes) |
| Thread isolation | Each skill run gets a unique thread ID |

### Idempotency

Each step declares its idempotency behavior in skill.yaml:

| Field | Meaning |
|---|---|
| rerunnable: true | Safe to execute this step again with the same input |
| cached: true | If the step has already produced output, skip it on resume |
| never_auto_rerun: true | This step must never run twice (e.g., file writes) |

Step 5 (write artifact) is marked `never_auto_rerun: true` to prevent duplicate file writes on resume.

---

## Creating a New Skill

### Recommended path: Meta-skills (automated)

The fastest way to create a new skill is via the meta-skill pipeline:

1. **Generate spec** via g26-skill-spec-writer (produces skill.yaml)
2. **Generate code** via g26-skill-template-gen (produces run.py)
3. **Apply known fixes** (context keys, cache on critic steps, step_3 improved-first read)
4. **Create test-input.json** with realistic test inputs matching the skill's required fields
5. **Test:** `python3 scripts/test-all.py --skill {skill-id}`
6. **Validate:** `python3 scripts/validate.py`
7. **Commit:** `git add skills/{skill-id}/ && git commit`

Cost: ~$0.25/skill. Batch automation: `python3 scripts/tier3-batch-build.py`

### Alternative path: Manual creation

1. **Scaffold:** `python3 scripts/new-skill.py` (interactive)
2. **Edit** skill.yaml and run.py following i35-tone-calibrator as reference
3. **Test and commit** as above

### Naming convention

Format: `{domain_letter}{family_number}-{skill-slug}` (e.g., `e12-market-research-analyst`)
- Domain letter: lowercase a-l (12 domains)
- Family number: zero-padded (a01, f09, j36)
- Slug: lowercase-hyphenated, max 30 chars
- Step IDs: `step_1`, `step_2`, etc.

### Known patterns (mandatory for all skills)

- H2-scoped section extraction (`##\s` not `##?`)
- Depth-driven token budgets (overview=12K, strategic=16K, detailed=20K)
- `min()` scoring (never weighted average)
- LangChain wrappers for all LLM calls
- step_3/step_4 must have `cached: false`
- step_3 must read improved version first: `context.get("improved_X", context.get("generated_X", ""))`
- step_5 returns `artifact_written: true`

---

## Graph Patterns

Phase 9 validated 5 LangGraph graph patterns that skill-runner.py supports:

| Pattern | Description | Status |
|---|---|---|
| Conditional branching | Step routes to different next steps based on output | Validated |
| Error branches | Error routes to handler node, state preserved | Validated |
| Retry paths | Failed node retries configured times before succeeding or escalating | Validated |
| Fallback paths | Primary path fails completely, fallback produces valid output | Validated |
| Parallel nodes | Two independent nodes execute and merge outputs correctly | Validated |

Test harness: `skills/graph-validation/validate_graph.py`
Results: `docs/architecture/langgraph-graph-validation-results.json`
Report: `docs/architecture/graph-validation-report.md`

The research-brief skill uses the linear chain pattern. Future skills can use any validated pattern.

---

## Validation Checks

`validate.py` includes 6 skill-related checks:

| Check | What It Verifies |
|---|---|
| [26] obs.py executes cleanly | Observer script runs without error |
| [27] LangGraph graph patterns validated | Graph validation test harness passes |
| [28] skill-runner.py exists | Execution engine is present |
| [29] research-brief/skill.yaml valid | Skill definition is parseable YAML with required fields |
| [30] research-brief/outputs/ writable | Artifact directory exists and is writable |
| [31] LangGraph checkpoint DB exists | Checkpoint database file is present |

---

## Known Limitations

| Limitation | Impact | Future Fix |
|---|---|---|
| Linear execution only in practice | Branching validated but no skill uses it yet | Build a skill that requires branching |
| No parallel step execution | Steps always run sequentially | LangGraph supports parallelism — needs skill design |
| Skill chaining via envelopes | Supported via --input-from, validated e12→f09 | Direct pipeline chaining works |
| No skill versioning at runtime | Runner does not check version compatibility | Version check in skill-runner.py |
| Artifacts are local-only | Output files are not synced or backed up | Cloud artifact storage extension |
| LLM non-determinism | Same input may produce slightly different output | Test inputs must allow heading/format variation |
| List inputs from CLI | Runner passes all --input values as strings | Skills expecting lists need JSON/comma parsing in step_1 |
| Checkpoint stale cache | cached:true on critic steps causes infinite loops | All step_3/step_4 MUST use cached:false |
