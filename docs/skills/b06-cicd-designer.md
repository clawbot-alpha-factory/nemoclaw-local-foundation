# CI/CD Pipeline Designer

**ID:** `b06-cicd-designer` | **Version:** 1.0.0 | **Family:** F06 | **Domain:** B | **Type:** executor | **Tag:** dual-use

## Description

Designs a complete CI/CD pipeline specification from a project description, deployment targets, and quality gates. Produces structured pipeline definitions with stages (lint, test, build, deploy), trigger conditions, environment matrix, artifact management, secret handling strategy, rollback procedures, notification rules, and estimated pipeline duration. Supports GitHub Actions, GitLab CI, and generic YAML formats. All stages are justified by project requirements — no fabricated stages are included.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `project_description` | string | Yes | Description of the project including language, framework, dependencies, and any special build or deployment requirements.  |
| `deployment_targets` | string | Yes | Comma-separated list of deployment targets (e.g., staging, production, canary) with environment details such as cloud provider or Kubernetes cluster.  |
| `quality_gates` | string | Yes | Quality gate requirements such as minimum test coverage percentage, static analysis thresholds, security scan pass criteria, and performance benchmarks.  |
| `pipeline_format` | string | Yes | Target pipeline format for the output specification.  |
| `additional_constraints` | string | No | Optional additional constraints such as compliance requirements, cost limits, specific runner types, or organizational policies.  |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | The complete CI/CD pipeline specification in the requested format, including all stages, trigger conditions, environment matrix, artifact management, secret handling strategy, rollback procedures, notification rules, and estimated pipeline duration.  |
| `result_file` | file_path | Path to the written pipeline specification artifact file. |
| `envelope_file` | file_path | Path to the execution envelope JSON for this skill run. |

## Steps

- **step_1** — Parse Inputs and Build Pipeline Design Plan (`local`, `general_short`)
- **step_2** — Generate Complete Pipeline Specification Document (`llm`, `premium`)
- **step_3** — Evaluate Pipeline Quality and Completeness (`critic`, `moderate`)
- **step_4** — Improve Pipeline Based on Critic Feedback (`llm`, `premium`)
- **step_5** — Write Pipeline Artifact to Storage (`local`, `general_short`)

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=10, max_improvements=5
- **Max Execution:** 180s
- **Max Cost:** $0.35

## Declarative Guarantees

- Every pipeline stage included in the output is explicitly justified by a stated project requirement.
- No stages are fabricated or included by default without a corresponding requirement signal.
- The output includes all required sections — stages, triggers, environment matrix, artifact management, secret handling, rollback procedures, notification rules, and estimated duration.
- Secret handling strategy follows least-privilege principles and never exposes secrets in logs or artifacts.
- Rollback procedures are defined for every deployment target specified in the input.
- The pipeline format strictly conforms to the requested target (GitHub Actions, GitLab CI, or generic YAML).
- Quality gate thresholds from the input are reflected as enforceable checks within the pipeline stages.

## Composability

- **Output Type:** cicd_pipeline_specification

## Example Usage

```json
{
  "skill_id": "b06-cicd-designer",
  "inputs": {
    "project_description": "A Python LangGraph application with 20 skills, YAML configurations, and API integrations with Anthropic, OpenAI, and Google. Uses pip for dependencies and pytest for testing.",
    "deployment_targets": "No deployment yet, validation only. Run linting, type checking, unit tests, and one integration test.",
    "quality_gates": "Linting with ruff, unit tests with pytest, integration test that runs one skill end-to-end, 31-check validation script.",
    "pipeline_format": "github_actions"
  }
}
```
