# Skill Template Generator

**ID:** `g26-skill-template-gen` | **Version:** 1.0.0 | **Family:** F26 | **Domain:** G | **Type:** executor | **Tag:** internal

## Description

Takes a skill.yaml and generates an architecture-aligned first-draft run.py with step handlers, provider dispatch, and validation structure. Produces strong prompt scaffolding and correct runtime wiring. Human review of generated run.py is still required before deployment.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `skill_yaml` | string | Yes | Complete skill.yaml content to generate code for |
| `reference_pattern` | string | No | Advisory hint for which reference to follow. Step 1 infers actual requirements from skill.yaml. |
| `deterministic_check_type` | string | No | What kind of deterministic preservation checks to generate |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | The complete run.py content as a string |
| `result_file` | file_path | Path to the markdown artifact containing the Python code |
| `envelope_file` | file_path | Path to the JSON envelope for skill chaining |

## Steps

- **step_1** — Parse skill.yaml and classify step implementation requirements (`local`, `general_short`)
- **step_2** — Generate architecture-aligned run.py implementation (`llm`, `premium`)
- **step_3** — Validate code correctness and architectural compliance (`critic`, `moderate`)
- **step_4** — Fix code issues based on critic feedback (`llm`, `premium`)
- **step_5** — Validate final code and write artifact (`local`, `general_short`)

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=10, max_improvements=5
- **Max Execution:** 120s
- **Max Cost:** $0.15

## Declarative Guarantees

- Output is valid Python that compiles without errors
- STEP_HANDLERS dict contains an entry for every step_id in the skill.yaml
- LLM and critic steps use call_resolved() with proper context passing
- Local steps do not call call_resolved() or any LLM call function
- Critic step handlers return structured JSON with quality_score field
- __main__ block follows standard argparse pattern with --step and --input
- Required imports are present for all referenced modules
- No invented helper functions, state fields, or runtime interfaces
- Generated code follows current runner contract for artifact and output handling

## Composability

- **Output Type:** skill_run_py
- **Accepts Input From:** g26-skill-spec-writer

## Example Usage

```json
{
  "skill_id": "g26-skill-template-gen",
  "inputs": {
    "skill_yaml": "name: test-skill\nversion: 1.0.0\ndisplay_name: Test Skill\ndescription: A minimal test skill\nauthor: Core88\ncreated: 2026-03-27\nfamily: F99\ndomain: J\ntag: internal\nskill_type: executor\nschema_version: 2\nrunner_version_required: '>=4.0.0'\nrouting_system_version_required: '>=3.0.0'\nmax_loop_iterations: 3\ncontext_requirements: [workflow_id, budget_state, step_history]\nexecution_role: You are a test skill.\ninputs:\n  - name: test_input\n    type: string\n    required: true\n    description: Test input\n    validation:\n      min_length: 5\noutputs:\n  - name: result\n    type: string\n    description: Test output\n  - name: result_file\n    type: file_path\n    description: Artifact path\n  - name: envelope_file\n    type: file_path\n    description: Envelope path\nartifacts:\n  storage_location: skills/test-skill/outputs/\n  filename_pattern: test-skill_{workflow_id}_{timestamp}.md\n  envelope_pattern: test-skill_{workflow_id}_{timestamp}_envelope.json\n  format: markdown\n  committed_to_repo: false\n  gitignored: true\nsteps:\n  - id: step_1\n    name: Parse and validate test input\n    step_type: local\n    task_class: general_short\n    description: Validate the test input\n    input_source: inputs.test_input\n    output_key: step_1_output\n    idempotency: {rerunnable: true, cached: false, never_auto_rerun: false}\n    requires_human_approval: false\n    failure: {success_conditions: [{left: step_1_output, op: not_empty, right: true}], strategy: halt, retry_count: 0, fallback_step: null, escalation_message: Failed}\n    transition: {default: step_2}\n  - id: step_2\n    name: Generate test output content\n    step_type: llm\n    task_class: moderate\n    description: Generate output\n    input_source: step_1.output\n    output_key: generated_output\n    idempotency: {rerunnable: true, cached: true, never_auto_rerun: false}\n    requires_human_approval: false\n    failure: {success_conditions: [{left: generated_output, op: not_empty, right: true}], strategy: retry, retry_count: 2, fallback_step: null, escalation_message: Failed}\n    transition: {default: step_3}\n  - id: step_3\n    name: Write final test artifact\n    step_type: local\n    task_class: general_short\n    description: Write artifact\n    input_source: __final_output__\n    output_key: artifact_path\n    idempotency: {rerunnable: false, cached: false, never_auto_rerun: true}\n    requires_human_approval: false\n    failure: {success_conditions: [{left: artifact_path, op: not_empty, right: true}], strategy: halt, retry_count: 0, fallback_step: null, escalation_message: Failed}\n    transition: {default: __end__}\ncontracts:\n  machine_validated: {output_format: markdown, required_fields: [result], quality: {min_length: 50, max_length: 5000, min_quality_score: 7}, sla: {max_execution_seconds: 60, max_cost_usd: 0.05}}\n  declarative_guarantees: [Output is well-formed]\napproval_boundaries: {safe_steps: [step_1, step_2, step_3], approval_gated_steps: [], blocked_external_effect_steps: []}\nrouting: {default_alias: moderate, allow_override: false}\ncomposable: {output_type: test_output, can_feed_into: [], accepts_input_from: []}\nobservability: {log_level: detailed, track_cost: true, track_latency: true, track_tokens: true, track_quality: true, metrics_file: '~/.nemoclaw/logs/skill-metrics.jsonl'}"
  }
}
```
