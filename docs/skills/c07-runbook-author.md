# Runbook Author

**ID:** `c07-runbook-author` | **Version:** 1.0.0 | **Family:** F07 | **Domain:** C | **Type:** executor | **Tag:** dual-use

## Description

Takes a system description, operational procedures to cover, and failure scenarios, produces a structured operational runbook with numbered procedures, decision trees for recovery/incident procedures, verification checkpoints per procedure, rollback instructions for recovery/modification procedures, and a quick reference card with time estimates. Works only from provided input — no external knowledge.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `system_description` | string | Yes | What system the runbook covers, its components and operational context |
| `procedures` | string | Yes | Comma-separated list of procedures to document (e.g., cold start, health check, budget reset, incident response) |
| `failure_scenarios` | string | No | Known failure modes the runbook should address |
| `audience` | string | No | Who uses this runbook. operator: step-by-step, heavy verification. developer: concise, assumes stack familiarity. on-call: triage-first, decision trees prioritized, escalation paths required. |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | The complete operational runbook in markdown |
| `result_file` | file_path | Path to the markdown artifact |
| `envelope_file` | file_path | Path to the JSON envelope |

## Steps

- **step_1** — Parse system context and classify procedures (`local`, `general_short`)
- **step_2** — Generate operational runbook with decision trees and checkpoints (`llm`, `complex_reasoning`)
- **step_3** — Evaluate runbook completeness and decision tree quality (`critic`, `moderate`)
- **step_4** — Strengthen runbook based on critic feedback (`llm`, `complex_reasoning`)
- **step_5** — Validate final runbook and write artifact (`local`, `general_short`)

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=10, max_improvements=5
- **Max Execution:** 120s
- **Max Cost:** $0.15

## Declarative Guarantees

- Every input procedure has a dedicated section with actionable steps
- Every procedure section has at least one verification checkpoint
- Recovery and incident procedures include decision trees with real branching (multiple paths)
- Recovery and modification procedures include rollback instructions or explicit no-rollback statement
- Quick reference card summarizes all procedures with estimated completion time
- On-call audience gets escalation paths with who/when to escalate
- No fabricated commands or paths not derivable from the input
- No vague operational language (check logs without specifying which, investigate further without specifying what)

## Composability

- **Output Type:** operational_runbook
- **Can Feed Into:** a01-arch-spec-writer
- **Accepts Input From:** c07-setup-guide-writer

## Example Usage

```json
{
  "skill_id": "c07-runbook-author",
  "inputs": {
    "system_description": "A Kubernetes-deployed microservices application with 5 services, PostgreSQL database, Redis cache, and RabbitMQ message broker. Monitored via Prometheus and Grafana.",
    "procedures": "cold start, health check, database failover, service restart, log review"
  }
}
```
