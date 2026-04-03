# Setup Guide Writer

**ID:** `c07-setup-guide-writer` | **Version:** 1.0.0 | **Family:** F07 | **Domain:** C | **Type:** executor | **Tag:** dual-use

## Description

Takes a system description, target environment, and prerequisite context, produces a complete step-by-step setup guide with prerequisites table, numbered installation steps with verification commands or UI action instructions, environment notes, troubleshooting section, and post-setup checklist. Works only from provided input — no external knowledge.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `system_description` | string | Yes | What system is being set up, its components, and purpose |
| `target_environment` | string | Yes | OS, hardware, runtime requirements (e.g., MacBook Apple Silicon, macOS 15+, Docker Desktop 29+) |
| `prerequisites` | string | No | Known prerequisites, dependencies, API keys needed |
| `setup_steps_hint` | string | No | Optional ordered list of high-level steps to cover |
| `audience` | string | No | Who reads this guide. Controls vocabulary complexity, command explanation depth, and whether GUI alternatives are mentioned for CLI steps. |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | The complete setup guide in markdown |
| `result_file` | file_path | Path to the markdown artifact |
| `envelope_file` | file_path | Path to the JSON envelope |

## Steps

- **step_1** — Parse system context and plan guide structure (`local`, `general_short`)
- **step_2** — Generate complete setup guide with verification commands (`llm`, `complex_reasoning`)
- **step_3** — Evaluate guide completeness and verification coverage (`critic`, `moderate`)
- **step_4** — Strengthen guide based on critic feedback (`llm`, `complex_reasoning`)
- **step_5** — Validate final guide and write artifact (`local`, `general_short`)

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=10, max_improvements=5
- **Max Execution:** 120s
- **Max Cost:** $0.15

## Declarative Guarantees

- Every numbered setup step has either a CLI code block or a clearly marked UI action instruction
- Every numbered setup step has a verification instruction (Expected:, Verify:, Confirm:, or equivalent)
- Prerequisites table lists all required tools with version and install source
- Troubleshooting section contains at least 3 distinct failure scenarios
- Guide is self-contained — no 'see external docs' without specifying what those docs contain
- No fabricated commands or paths not derivable from the input
- Audience level is respected: vocabulary, explanation depth, GUI alternatives where appropriate

## Composability

- **Output Type:** setup_guide
- **Can Feed Into:** c07-runbook-author, a01-arch-spec-writer
- **Accepts Input From:** g26-skill-spec-writer

## Example Usage

```json
{
  "skill_id": "c07-setup-guide-writer",
  "inputs": {
    "system_description": "A Python FastAPI application with PostgreSQL database, Redis cache, and Celery task queue. Deployed locally using Docker Compose for development.",
    "target_environment": "Local macOS development with Docker Compose",
    "audience": "developer"
  }
}
```
