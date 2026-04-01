# b06-release-notes-gen

**ID:** `b06-release-notes-gen`
**Version:** 1.0.0
**Type:** executor
**Family:** F06 | **Domain:** B | **Tag:** dual-use

## Description

Generates structured release notes from git commit history, version number, and audience type. Produces a version header, summary of changes, categorized sections (features, fixes, improvements, breaking changes), migration notes if applicable, known issues, and contributor acknowledgments. Anti-fabrication guarantee: all listed changes must be traceable to provided commit messages.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `commit_history` | string | Yes | Raw git commit history (e.g., output of `git log --oneline` or full commit messa |
| `version_number` | string | Yes | The version number for this release (e.g., "2.4.1", "v3.0.0-rc1").
 |
| `audience_type` | string | Yes | The intended audience for the release notes. Determines tone, depth, and termino |
| `product_name` | string | No | The name of the product or project being released. Used in the version header.
 |
| `previous_version` | string | No | The previous version number, used to frame the changelog context (e.g., "2.3.0") |
| `known_issues` | string | No | Optional list of known issues to include verbatim in the Known Issues section.
 |

## Execution Steps

1. **Parse Commits and Build Generation Plan** (local) — Validates all inputs, parses the commit history to extract individual commits, identifies commit authors for contributor acknowledgments, detects conventional commit prefixes (feat, fix, chore, refactor, BREAKING CHANGE, etc.), and builds a structured generation plan including categorization hints and audience-specific tone guidance.

2. **Generate Structured Release Notes Document** (llm) — Using the parsed commit plan from step_1, generates the full release notes document in Markdown. Includes: version header, executive summary, categorized sections (Features, Bug Fixes, Improvements, Breaking Changes), migration notes if breaking changes are present, known issues section, and contributor acknowledgments. Strictly anti-fabrication: every listed change must map to a commit in the provided history. Tone and depth are calibrated to the specified audience_type.

3. **Evaluate Release Notes Quality and Traceability** (critic) — Two-layer validation of the generated release notes. Deterministic layer: checks that all required sections are present (version header, summary, at least one categorized section, contributors), verifies no fabricated changes appear that lack a corresponding commit, checks Markdown structure integrity, and validates audience-appropriate language. LLM layer: scores clarity, completeness, accuracy of categorization, migration note quality (if applicable), and overall professional quality. Combines scores with min() to produce a final quality_score (0-10).

4. **Improve Release Notes Based on Critic Feedback** (llm) — Revises the release notes using the structured feedback from the critic step. Addresses identified issues such as missing sections, fabricated or uncategorized changes, unclear migration instructions, or audience tone mismatches. Preserves all traceable changes from the original commit history and does not introduce new content not grounded in the provided commits.

5. **Write Final Release Notes Artifact** (local) — Deterministic final gate. Confirms the selected release notes output is non-empty and structurally valid, then writes the artifact to disk and returns the standard completion signal. The runner handles envelope generation automatically.


## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/b06-release-notes-gen/run.py --force --input commit_history "value" --input version_number "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)
