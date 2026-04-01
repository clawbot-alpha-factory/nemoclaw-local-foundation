# b06-cicd-designer

**ID:** `b06-cicd-designer`
**Version:** 1.0.0
**Type:** executor
**Family:** F06 | **Domain:** B | **Tag:** dual-use

## Description

Designs a complete CI/CD pipeline specification from a project description, deployment targets, and quality gates. Produces structured pipeline definitions with stages (lint, test, build, deploy), trigger conditions, environment matrix, artifact management, secret handling strategy, rollback procedures, notification rules, and estimated pipeline duration. Supports GitHub Actions, GitLab CI, and generic YAML formats. All stages are justified by project requirements — no fabricated stages are included.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `project_description` | string | Yes | Description of the project including language, framework, dependencies, and any  |
| `deployment_targets` | string | Yes | Comma-separated list of deployment targets (e.g., staging, production, canary) w |
| `quality_gates` | string | Yes | Quality gate requirements such as minimum test coverage percentage, static analy |
| `pipeline_format` | string | Yes | Target pipeline format for the output specification.
 |
| `additional_constraints` | string | No | Optional additional constraints such as compliance requirements, cost limits, sp |

## Execution Steps

1. **Parse Inputs and Build Pipeline Design Plan** (local) — Validate all inputs, extract key project signals (language, framework, test tooling, deployment targets, quality gate thresholds), and construct a structured pipeline design plan that maps each required stage to a concrete project requirement. Reject any stage that cannot be justified.

2. **Generate Complete Pipeline Specification Document** (llm) — Using the validated design plan, generate a complete CI/CD pipeline specification in the requested format (GitHub Actions, GitLab CI, or generic YAML). Include all justified stages with trigger conditions, environment matrix, artifact management configuration, secret handling strategy, rollback procedures, notification rules, and an estimated pipeline duration. Every stage must cite the project requirement that justifies its inclusion.

3. **Evaluate Pipeline Quality and Completeness** (critic) — Two-layer validation of the generated pipeline specification. Deterministic checks verify that all required sections are present (stages, triggers, environment matrix, artifact config, secret handling, rollback, notifications, duration estimate) and that no unjustified stages exist. LLM evaluation scores the specification on correctness, security posture, completeness, format compliance, and anti-fabrication adherence. Final score is the minimum of deterministic and LLM scores.

4. **Improve Pipeline Based on Critic Feedback** (llm) — Revise the pipeline specification based on the critic's structured feedback. Address all identified issues including missing sections, unjustified stages, security gaps in secret handling, incomplete rollback procedures, or format non-compliance. Preserve all correctly designed sections and improve only the flagged areas.

5. **Write Pipeline Artifact to Storage** (local) — Final deterministic gate that confirms the pipeline specification is non-empty and well-formed, then writes the artifact to the configured storage location. Returns the artifact path confirmation.


## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/b06-cicd-designer/run.py --force --input project_description "value" --input deployment_targets "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)
