# b05-scaffold-gen

**ID:** `b05-scaffold-gen`
**Version:** 1.0.0
**Type:** executor
**Family:** F05 | **Domain:** B | **Tag:** internal

## Description

Generates a complete project scaffold for a given project type, language, framework, and feature requirements. Produces directory structure, boilerplate files, configuration templates, dependency manifest, and setup instructions. Each generated file includes purpose comments. Only generates files appropriate for the stated stack.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `project_type` | string | Yes | The type of project to scaffold. Determines top-level structure and tooling choi |
| `language` | string | Yes | Primary programming language for the project (e.g., python, typescript, go, rust |
| `framework` | string | No | Framework or runtime to use (e.g., fastapi, express, gin, actix, spring-boot). L |
| `feature_requirements` | string | Yes | Comma-separated or prose description of features to include (e.g., auth, databas |
| `project_name` | string | Yes | The name of the project, used as the root directory name and in package manifest |

## Execution Steps

1. **Parse Inputs Validate Stack Build Generation Plan** (local) — Validates the project_type, language, framework, and feature_requirements inputs. Resolves which files, directories, and dependencies are appropriate for the stated stack. Produces a structured generation plan listing every file to be created, its purpose, and the dependency manifest entries required.

2. **Generate Complete Project Scaffold** (llm) — Using the validated generation plan from step_1, produces the full project scaffold. Outputs a structured markdown document containing: (1) annotated directory tree, (2) full content of each boilerplate file with a purpose comment header, (3) dependency manifest (e.g., requirements.txt, package.json, go.mod, Cargo.toml), (4) configuration templates (e.g., .env.example, docker-compose.yml, CI config), (5) setup instructions. Only generates files appropriate for the stated stack.

3. **Evaluate Scaffold Quality Completeness Correctness** (critic) — Two-layer validation of the generated scaffold. Deterministic checks: verifies directory tree is present, at least one dependency manifest file is included, setup instructions section exists, and each file block contains a purpose comment. LLM evaluation: scores the scaffold on stack appropriateness (no fabricated dependencies), file completeness for the stated project_type, idiomatic structure for the language/framework, and clarity of purpose comments. Combines scores with min() and returns a quality_score 0-10.

4. **Improve Scaffold Based On Critic Feedback** (llm) — Revises the generated scaffold using the structured feedback from the critic step. Addresses identified issues such as missing files, fabricated dependencies, non-idiomatic structure, or unclear purpose comments. Produces an improved scaffold document that resolves all flagged deficiencies while preserving correct sections from the prior generation.

5. **Write Scaffold Artifact To Disk** (local) — Final deterministic gate. Receives the best-quality scaffold from the critic loop via __final_output__, performs a last structural check, and writes the artifact to the configured storage location. Returns confirmation that the artifact was written successfully.


## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/b05-scaffold-gen/run.py --force --input project_type "value" --input language "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)
