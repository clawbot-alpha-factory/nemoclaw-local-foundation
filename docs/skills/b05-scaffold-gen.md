# Scaffold Generator

**ID:** `b05-scaffold-gen` | **Version:** 1.0.0 | **Family:** F05 | **Domain:** B | **Type:** executor | **Tag:** internal

## Description

Generates a complete project scaffold for a given project type, language, framework, and feature requirements. Produces directory structure, boilerplate files, configuration templates, dependency manifest, and setup instructions. Each generated file includes purpose comments. Only generates files appropriate for the stated stack.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `project_type` | string | Yes | The type of project to scaffold. Determines top-level structure and tooling choices.  |
| `language` | string | Yes | Primary programming language for the project (e.g., python, typescript, go, rust, java).  |
| `framework` | string | No | Framework or runtime to use (e.g., fastapi, express, gin, actix, spring-boot). Leave empty for language-native scaffolds with no framework.  |
| `feature_requirements` | string | Yes | Comma-separated or prose description of features to include (e.g., auth, database, logging, docker, ci-cd, testing, linting).  |
| `project_name` | string | Yes | The name of the project, used as the root directory name and in package manifests.  |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | Full scaffold specification including directory tree, file contents with purpose comments, dependency manifest, and setup instructions in structured markdown.  |
| `result_file` | file_path | Path to the written scaffold markdown artifact. |
| `envelope_file` | file_path | Path to the JSON envelope containing metadata and output references. |

## Steps

- **step_1** — Parse Inputs Validate Stack Build Generation Plan (`local`, `general_short`)
- **step_2** — Generate Complete Project Scaffold (`llm`, `premium`)
- **step_3** — Evaluate Scaffold Quality Completeness Correctness (`critic`, `moderate`)
- **step_4** — Improve Scaffold Based On Critic Feedback (`llm`, `premium`)
- **step_5** — Write Scaffold Artifact To Disk (`local`, `general_short`)

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=10, max_improvements=5
- **Max Execution:** 180s
- **Max Cost:** $0.5

## Declarative Guarantees

- The scaffold only includes files and dependencies appropriate for the stated language, framework, and project_type.
- Every generated file includes a purpose comment at the top of its content block.
- A dependency manifest appropriate to the language is always included in the output.
- Setup instructions are always present and reference the actual generated structure.
- No files are fabricated for frameworks or runtimes not specified in the inputs.
- The directory tree is always present and consistent with the generated file contents.

## Composability

- **Output Type:** project_scaffold_document

## Example Usage

```json
{
  "skill_id": "b05-scaffold-gen",
  "inputs": {
    "project_type": "cli-tool",
    "language": "python",
    "feature_requirements": "A CLI tool that reads YAML configuration files, validates them against a JSON schema, and reports violations with line numbers and fix suggestions. Must support stdin piping and glob patterns.",
    "project_name": "yaml-validator"
  }
}
```
