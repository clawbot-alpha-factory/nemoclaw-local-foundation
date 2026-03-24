# skill.yaml Schema v2

> **Location:** `docs/architecture/skill-yaml-schema-v2.md`
> **Version:** 2.0
> **Date:** 2026-03-25
> **Phase:** 13 — Skill Engine Upgrade
> **Status:** SPEC — requires approval before implementation
> **Implements:** 9 improvements from the architectural review

---

## Purpose

This document defines the v2 skill.yaml schema — the complete specification that every skill must follow. It replaces the implicit v1 schema (inferred from research-brief). The v2 schema adds skill typing, decision logic, observability, quality contracts, failure escalation, and rich context support.

skill-runner.py v4.0 and new-skill.py v2.0 will be built from this spec.

---

## What Changed From v1

| Feature | v1 (research-brief) | v2 (this spec) |
|---|---|---|
| Context object | Step data only | Rich: workflow_id, budget_state, step_history, agent_role |
| Skill type | Not declared | Required: executor, planner, evaluator, transformer, router |
| Step flow | Linear only (step_1 → step_2 → ...) | Transitions: conditional routing, loops, early exit |
| Output verification | Single validation step | Critic pattern: generate → evaluate → improve |
| Per-step observability | None | Latency, token estimate, cost, success/fail logged |
| Quality contracts | Min length only | Output format, quality threshold, required fields |
| Failure handling | Retry once then fail | Escalation: retry → fallback → alternate path → halt |
| Step naming | Generic allowed | Semantic names required — no "TODO" or "LLM step N" |
| Envelope output | Documented not implemented | Built into runner — every skill writes envelope JSON |

---

## Complete v2 Schema

### Top-Level Fields

```yaml
# ── Identity ──────────────────────────────────────────────
name: h35-tone-calibrator            # Skill ID (matches directory name)
version: 1.0.0                       # Semantic version
display_name: "Tone Calibrator"      # Human-readable name
description: >                       # What this skill does (required, min 20 chars)
  Takes text and a target tone profile, rewrites the text
  to match the tone while preserving meaning and quality.
author: Core88
created: 2026-03-25

# ── Classification ────────────────────────────────────────
family: F35                          # Zero-padded family number
domain: H                            # Domain letter A-L
tag: customer-facing                 # internal | customer-facing | dual-use
skill_type: transformer              # executor | planner | evaluator | transformer | router

# ── Compatibility ─────────────────────────────────────────
schema_version: 2
runner_version_required: ">=4.0.0"
routing_system_version_required: ">=3.0.0"
```

**Skill type definitions:**

| Type | Purpose | Example |
|---|---|---|
| executor | Produces an output artifact from inputs | Research Brief Writer, Code Generator |
| planner | Decomposes a task into sub-tasks or skill sequences | Task Decomposition Engine, Skill Selector |
| evaluator | Scores, critiques, or validates another skill's output | Output Quality Scorer, Code Reviewer |
| transformer | Transforms input from one format/style to another | Tone Calibrator, Code Translator |
| router | Decides which skill or path to invoke next | Complexity Classifier, Intent Router |

### Inputs Section

```yaml
inputs:
  - name: input_text
    type: string
    required: true
    description: "The text to be tone-calibrated"
    validation:
      min_length: 10
      max_length: 10000

  - name: target_tone
    type: string
    required: true
    description: "Target tone profile"
    validation:
      allowed_values: [professional, casual, authoritative, friendly, technical, empathetic]

  - name: preserve_structure
    type: boolean
    required: false
    default: true
    description: "Whether to preserve the original paragraph/section structure"
```

**Supported input types:** `string`, `boolean`, `integer`, `float`, `file_path`, `json`

### Outputs Section

```yaml
outputs:
  - name: result
    type: string
    description: "The tone-calibrated text"

  - name: result_file
    type: file_path
    description: "Path to the markdown artifact"

  - name: envelope_file
    type: file_path
    description: "Path to the JSON envelope for skill chaining"
```

### Artifacts Section

```yaml
artifacts:
  storage_location: skills/h35-tone-calibrator/outputs/
  filename_pattern: "h35-tone-calibrator_{workflow_id}_{timestamp}.md"
  envelope_pattern: "h35-tone-calibrator_{workflow_id}_{timestamp}_envelope.json"
  format: markdown
  committed_to_repo: false
  gitignored: true
```

### Context Section (NEW in v2)

Declares what context the skill needs from the runtime. skill-runner.py populates these fields before step execution.

```yaml
context:
  requires:
    - workflow_id          # Always available — unique run identifier
    - budget_state         # Current provider spend and remaining budget
    - step_history         # List of completed steps with their outputs and metrics
    - agent_role           # The role/persona for this skill execution
  agent_role: >
    You are a professional tone calibration specialist. Your job is to
    rewrite text to match a specified tone while preserving all meaning,
    facts, and structure.
```

**Context fields populated by skill-runner.py:**

| Field | Type | Description |
|---|---|---|
| workflow_id | string | Unique thread ID for this run |
| budget_state | dict | `{provider: {spend, remaining, pct_used}}` per provider |
| step_history | list | `[{step_id, status, latency_ms, cost_usd, output_preview}]` |
| agent_role | string | The persona/role from this section, passed as system context |
| resolved_model | string | Model string from routing system (set per LLM step) |
| resolved_provider | string | Provider name from routing system (set per LLM step) |
| previous_skills | list | Envelope data from upstream skills (when using `--input-from`) |

### Steps Section (Upgraded in v2)

```yaml
steps:
  - id: step_1
    name: "Parse input and analyze current tone"    # Semantic name REQUIRED
    step_type: local                                 # local | llm | critic | decision
    task_class: general_short
    makes_llm_call: false
    description: >
      Parse the input text, detect its current tone characteristics,
      and prepare the transformation plan.
    input_source: inputs.input_text
    output_key: tone_analysis

    idempotency:
      rerunnable: true
      cached: false
      never_auto_rerun: false

    failure:                                         # UPGRADED from single failure_condition
      condition: "input_text is empty or below min_length"
      strategy: halt                                 # retry | fallback | alternate | halt
      retry_count: 0
      fallback_step: null
      escalation: "Fail with input validation error"

    transition:                                      # NEW — conditional next step
      default: step_2
      # conditions evaluated in order, first match wins
      # if no condition matches, default is used

  - id: step_2
    name: "Rewrite text in target tone"
    step_type: llm
    task_class: premium                              # customer-facing → premium tier
    makes_llm_call: true
    description: >
      Using the tone analysis, rewrite the input text to match
      the target tone while preserving meaning and structure.
    input_source: step_1.output
    output_key: rewritten_text

    idempotency:
      rerunnable: true
      cached: true
      never_auto_rerun: false

    failure:
      condition: "Model returns empty or response under 50 characters"
      strategy: retry
      retry_count: 2
      fallback_step: null
      escalation: "After 2 retries, halt with model failure error"

    transition:
      default: step_3

  - id: step_3
    name: "Evaluate tone match quality"              # CRITIC STEP
    step_type: critic
    task_class: moderate
    makes_llm_call: true
    description: >
      Evaluate whether the rewritten text matches the target tone.
      Produce a quality score 0-10 and specific improvement notes.
    input_source: step_2.output
    output_key: quality_evaluation

    idempotency:
      rerunnable: true
      cached: false
      never_auto_rerun: false

    failure:
      condition: "Evaluation fails to produce a score"
      strategy: fallback
      retry_count: 1
      fallback_step: step_4                          # Skip improvement, go to output
      escalation: "If fallback also fails, halt"

    transition:
      default: step_4
      conditions:
        - if: "quality_score >= 8"
          go_to: step_5                              # Skip improvement — quality is good
          reason: "Score meets threshold, no improvement needed"
        - if: "quality_score < 8 and improvement_attempts < 2"
          go_to: step_4                              # Needs improvement
          reason: "Score below threshold, attempt improvement"
        - if: "improvement_attempts >= 2"
          go_to: step_5                              # Stop trying after 2 improvements
          reason: "Max improvement attempts reached"

  - id: step_4
    name: "Improve based on critic feedback"
    step_type: llm
    task_class: premium
    makes_llm_call: true
    description: >
      Take the critic's feedback and improve the rewritten text.
      Then loop back to the critic for re-evaluation.
    input_source: step_3.output
    output_key: improved_text

    idempotency:
      rerunnable: true
      cached: false
      never_auto_rerun: false

    failure:
      condition: "Improvement produces shorter or empty text"
      strategy: fallback
      retry_count: 1
      fallback_step: step_5                          # Use previous version
      escalation: "Use step_2 output as final if improvement fails"

    transition:
      default: step_3                                # Loop back to critic
      # This creates: generate → critic → improve → critic → ... → output

  - id: step_5
    name: "Validate and write artifact"
    step_type: local
    task_class: general_short
    makes_llm_call: false
    description: >
      Validate the final output meets contracts, write markdown
      artifact and JSON envelope.
    input_source: best_available                     # Uses highest-quality output from prior steps
    output_key: artifact_path

    idempotency:
      rerunnable: false
      cached: false
      never_auto_rerun: true

    failure:
      condition: "Output fails contract validation or write fails"
      strategy: halt
      retry_count: 0
      fallback_step: null
      escalation: "Preserve best output in checkpoint, fail with write error"

    transition:
      default: __end__                               # Terminal step
```

**Step types:**

| Type | Description | Makes LLM Call |
|---|---|---|
| local | Pure Python processing — no inference | No |
| llm | Calls a model via the routing system | Yes |
| critic | Evaluates/scores output from a prior step | Yes (uses cheaper model) |
| decision | Evaluates conditions and routes to next step | Optional |

### Observability Section (NEW in v2)

```yaml
observability:
  log_level: detailed                # minimal | standard | detailed
  track_cost: true                   # Log estimated cost per step
  track_latency: true                # Log execution time per step
  track_tokens: true                 # Log estimated token usage per step
  track_quality: true                # Log quality scores from critic steps
  metrics_file: "~/.nemoclaw/logs/skill-metrics.jsonl"
```

**Per-step metric record (written by skill-runner.py):**

```json
{
  "timestamp": "2026-03-25T10:30:00Z",
  "skill_id": "h35-tone-calibrator",
  "workflow_id": "skill-h35-tone-calibrator-20260325-103000-abc123",
  "step_id": "step_2",
  "step_name": "Rewrite text in target tone",
  "step_type": "llm",
  "status": "success",
  "latency_ms": 2340,
  "estimated_tokens": 1200,
  "estimated_cost_usd": 0.012,
  "provider": "anthropic",
  "model": "claude-sonnet-4-6",
  "quality_score": null,
  "retry_count": 0,
  "fallback_used": false
}
```

### Contracts Section (NEW in v2)

Defines what the skill guarantees about its output. Used by the final validation step and by downstream skills consuming the envelope.

```yaml
contracts:
  output_format: markdown
  required_fields:
    - result                         # Must be present and non-empty
  quality:
    min_length: 100                  # Minimum output character count
    max_length: 50000                # Maximum output character count
    min_quality_score: 7             # Minimum score from critic step (0-10)
  guarantees:
    - "Output preserves all factual content from input"
    - "Output matches the requested tone profile"
    - "Output does not introduce new claims not in the original"
  sla:
    max_execution_seconds: 120       # Skill should complete within this time
    max_cost_usd: 0.10               # Skill should cost less than this per run
```

### Failure Escalation (Upgraded in v2)

Each step declares its own failure strategy. skill-runner.py reads these and acts accordingly.

**Strategy definitions:**

| Strategy | Behavior |
|---|---|
| retry | Re-run the same step up to `retry_count` times |
| fallback | Jump to `fallback_step` if retries exhausted |
| alternate | Execute an alternate implementation (e.g., different model) |
| halt | Stop the skill, preserve state in checkpoint, report error |

**Escalation chain example:**

```
Step fails → retry (2 attempts) → fallback to step_5 → if fallback fails → halt
```

### Approval Boundaries

```yaml
approval_boundaries:
  safe_steps: [step_1, step_2, step_3, step_4, step_5]
  approval_gated_steps: []
  blocked_external_effect_steps: []
  notes: >
    All steps are safe — no external writes beyond local artifacts.
    If a future version sends output externally, those steps must
    be classified as approval_gated.
```

### Routing Section

```yaml
routing:
  default_alias: premium             # Matches tag: customer-facing
  allow_override: false
```

### Composable Section

```yaml
composable:
  output_type: "tone_calibrated_text"
  can_feed_into:
    - "h35-ai-detection-bypasser"
    - "i37-cold-email-seq-writer"
    - "l38-linkedin-post-writer"
  accepts_input_from:
    - "c08-research-brief"
    - "b05-feature-impl-writer"
    - "d11-copywriting-specialist"
```

---

## Transition Logic — How It Works

skill-runner.py v4.0 evaluates transitions after each step completes:

```
Step completes → check transition.conditions in order
  ├── First matching condition → go_to that step
  ├── No condition matches → use transition.default
  └── default is __end__ → skill complete
```

**Loop protection:** skill-runner.py tracks `improvement_attempts` (and any counter referenced in conditions). If a loop executes more than `max_loop_iterations` (default: 3), it forces exit to the next non-loop step.

```yaml
# Global loop protection (optional, in top-level)
max_loop_iterations: 3
```

**Condition evaluation:** Conditions reference output keys from the step that just completed. skill-runner.py extracts the value from the step output and evaluates the condition as a simple comparison.

Supported operators: `>=`, `<=`, `>`, `<`, `==`, `!=`, `contains`, `not_empty`

```yaml
conditions:
  - if: "quality_score >= 8"         # Numeric comparison
    go_to: step_5
  - if: "status == complete"         # String equality
    go_to: step_4
  - if: "sections contains Background"  # String containment
    go_to: step_3
```

---

## Envelope Schema v2

The JSON envelope written by every skill on completion:

```json
{
  "schema_version": 2,
  "skill_id": "h35-tone-calibrator",
  "skill_version": "1.0.0",
  "skill_type": "transformer",
  "thread_id": "skill-h35-tone-calibrator-20260325-103000-abc123",
  "timestamp": "2026-03-25T10:30:36Z",
  "status": "complete",
  "error": null,
  "inputs": {
    "input_text": "...",
    "target_tone": "professional"
  },
  "outputs": {
    "primary": "The transformed text...",
    "sections": {},
    "artifact_path": "skills/h35-tone-calibrator/outputs/h35_20260325.md"
  },
  "metrics": {
    "total_cost_usd": 0.028,
    "total_latency_ms": 4800,
    "total_steps": 5,
    "llm_steps": 3,
    "critic_loops": 1,
    "quality_score": 8.5,
    "provider_breakdown": {
      "anthropic": {"calls": 2, "cost": 0.024},
      "openai": {"calls": 1, "cost": 0.004}
    }
  },
  "contracts": {
    "output_format": "markdown",
    "min_quality_met": true,
    "sla_time_met": true,
    "sla_cost_met": true
  },
  "composable": {
    "output_type": "tone_calibrated_text",
    "can_feed_into": ["h35-ai-detection-bypasser", "i37-cold-email-seq-writer"],
    "accepts_input_from": ["c08-research-brief"]
  }
}
```

**Error envelope (on failure):**

```json
{
  "schema_version": 2,
  "skill_id": "h35-tone-calibrator",
  "status": "failed",
  "error": "Step step_2 failed after 2 retries: model returned empty response",
  "metrics": {
    "total_cost_usd": 0.008,
    "failed_at_step": "step_2",
    "steps_completed": 1
  }
}
```

skill-runner.py refuses to start if `--input-from` loads an envelope with non-null `error` field.

---

## Context Object — What skill-runner.py Provides

Before each step executes, skill-runner.py builds the context dict:

```python
context = {
    # Always present
    "workflow_id": "skill-h35-tone-calibrator-20260325-103000-abc123",

    # Budget state — read from provider-spend.json
    "budget_state": {
        "anthropic": {"spend": 0.65, "remaining": 9.35, "pct_used": 0.065},
        "openai": {"spend": 0.12, "remaining": 9.88, "pct_used": 0.012},
        "google": {"spend": 0.01, "remaining": 9.99, "pct_used": 0.001}
    },

    # Step history — accumulated during execution
    "step_history": [
        {"step_id": "step_1", "status": "success", "latency_ms": 45, "cost_usd": 0},
    ],

    # Agent role — from skill.yaml context.agent_role
    "agent_role": "You are a professional tone calibration specialist...",

    # Routing — set per LLM step by budget enforcer
    "resolved_model": "claude-sonnet-4-6",
    "resolved_provider": "anthropic",

    # Upstream skills — populated when --input-from is used
    "previous_skills": [],

    # Loop tracking — for transition conditions
    "improvement_attempts": 0,

    # All prior step outputs — keyed by output_key
    "tone_analysis": "...",
    "rewritten_text": "...",
}
```

---

## Backward Compatibility

The v2 schema is a superset of v1. Existing skills (research-brief) continue to work because:

- New fields have defaults: `skill_type` defaults to `executor`, `transition.default` defaults to next sequential step
- `step_type` defaults to `llm` if `makes_llm_call: true`, else `local`
- `failure.strategy` defaults to `halt` (current behavior)
- `contracts` section is optional
- `observability` section is optional (defaults to `standard` logging)
- `context` section is optional (runner always provides workflow_id and budget_state)
- `composable` section is optional

skill-runner.py v4.0 detects `schema_version: 2` and enables the new features. Skills without `schema_version` or with `schema_version: 1` run in compatibility mode.

---

## Naming Rules Enforced by new-skill.py v2.0

The template generator will reject:

- Step names containing "TODO", "LLM step", "Processing step", or any generic placeholder
- Step names shorter than 10 characters
- Skill descriptions shorter than 20 characters
- Skill IDs not matching the `{domain}{family}-{slug}` pattern with zero-padded family

**When generating boilerplate:** new-skill.py v2.0 requires `--step-names` as a comma-separated list of semantic step names. No generic defaults are generated.

Example:

```bash
python3 scripts/new-skill.py \
  --id h35-tone-calibrator \
  --name "Tone Calibrator" \
  --family 35 --domain H --tag customer-facing \
  --skill-type transformer \
  --step-names "Parse input and analyze current tone,Rewrite text in target tone,Evaluate tone match quality,Improve based on critic feedback,Validate and write artifact" \
  --llm-steps "2,3,4" \
  --critic-steps "3"
```

---

## Implementation Requirements for skill-runner.py v4.0

| Requirement | What Changes |
|---|---|
| Transition engine | After each step, evaluate `transition.conditions` and route to the correct next step |
| Loop protection | Track iteration counters, enforce `max_loop_iterations` |
| Rich context | Build context dict with budget_state, step_history, agent_role before each step |
| Per-step metrics | Time each step, log metrics to skill-metrics.jsonl |
| Envelope writing | Write JSON envelope on completion (success or failure) |
| --input-from | Parse upstream envelope, validate error is null, inject into context.previous_skills |
| Condition evaluation | Parse simple conditions (>=, <=, ==, contains, not_empty) from YAML |
| Critic pattern | Support step_type: critic with quality_score extraction |
| Contract validation | After final step, validate output against contracts section |
| Backward compatibility | Detect schema_version, run v1 skills in compatibility mode |

---

## What This Spec Does NOT Cover

- Multi-skill orchestration (F24) — separate system, not in skill.yaml
- Skill selection/planning (F26) — implemented as skills, not schema
- Memory persistence across runs — future system-level feature
- Parallel step execution — LangGraph supports it, deferred until a skill needs it
