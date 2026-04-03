# Script Automator

**ID:** `b05-script-automator` | **Version:** 1.0.0 | **Family:** F05 | **Domain:** B | **Type:** executor | **Tag:** dual-use

## Description

Takes a task description, target shell, and operational context, produces a complete automation script with argument parsing, input validation, conditional error handling, logging, dry-run support for destructive operations, exit code discipline, and usage documentation. Focused on operational scripts — the glue that connects systems and replaces manual CLI workflows. Does NOT execute the script.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `task_description` | string | Yes | What the script should automate, trigger conditions, expected behavior |
| `target_shell` | string | Yes | Target language for the script |
| `operational_context` | string | No | Systems involved, file paths, APIs called, environment assumptions |
| `safety_requirements` | string | No | What must NOT happen: data loss prevention, confirmation prompts, dry-run needs |
| `output_format` | string | No | standalone (single script) or script_plus_config (script + config file) |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | The complete automation script in markdown |
| `result_file` | file_path | Path to the markdown artifact |
| `envelope_file` | file_path | Path to the JSON envelope |

## Steps

- **step_1** — Parse task and classify script type (`local`, `general_short`)
- **step_2** — Generate complete automation script with safety controls (`llm`, `complex_reasoning`)
- **step_3** — Evaluate script completeness and safety compliance (`critic`, `moderate`)
- **step_4** — Strengthen script based on critic feedback (`llm`, `complex_reasoning`)
- **step_5** — Validate final script and write artifact (`local`, `general_short`)

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=10, max_improvements=5
- **Max Execution:** 90s
- **Max Cost:** $0.1

## Declarative Guarantees

- Argument parsing for all configurable values — no magic constants
- Error handling on file operations, subprocess calls, and network requests — not on trivial operations
- No embedded secrets, tokens, API keys, or passwords — use environment variables or arguments
- Dry-run mode for destructive/deployment scripts with behavioral enforcement (prevents execution, prints intended actions)
- Confirmation prompt for destructive scripts unless --force is provided
- Usage/help documentation accessible via --help or header comment
- Exit 0 on success, non-zero on failure
- Logging for data pipeline, deployment, and monitoring scripts
- Idempotent where applicable — safe to re-run without unintended side effects

## Composability

- **Output Type:** automation_script
- **Can Feed Into:** c07-setup-guide-writer, c07-runbook-author
- **Accepts Input From:** a01-arch-spec-writer, b05-feature-impl-writer

## Example Usage

```json
{
  "skill_id": "b05-script-automator",
  "inputs": {
    "task_description": "A bash script that monitors a directory for new CSV files, validates their headers match an expected schema, moves valid files to a processed directory, and logs invalid files with the reason for rejection. Should run as a cron job every 5 minutes.",
    "target_shell": "bash"
  }
}
```
