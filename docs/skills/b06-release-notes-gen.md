# Release Notes Generator

**ID:** `b06-release-notes-gen` | **Version:** 1.0.0 | **Family:** F06 | **Domain:** B | **Type:** executor | **Tag:** dual-use

## Description

Generates structured release notes from git commit history, version number, and audience type. Produces a version header, summary of changes, categorized sections (features, fixes, improvements, breaking changes), migration notes if applicable, known issues, and contributor acknowledgments. Anti-fabrication guarantee: all listed changes must be traceable to provided commit messages.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `commit_history` | string | Yes | Raw git commit history (e.g., output of `git log --oneline` or full commit messages) covering the changes to be included in this release.  |
| `version_number` | string | Yes | The version number for this release (e.g., "2.4.1", "v3.0.0-rc1").  |
| `audience_type` | string | Yes | The intended audience for the release notes. Determines tone, depth, and terminology.  |
| `product_name` | string | No | The name of the product or project being released. Used in the version header.  |
| `previous_version` | string | No | The previous version number, used to frame the changelog context (e.g., "2.3.0").  |
| `known_issues` | string | No | Optional list of known issues to include verbatim in the Known Issues section.  |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | The fully structured release notes document in Markdown format.  |
| `result_file` | file_path | Path to the written release notes artifact file.  |
| `envelope_file` | file_path | Path to the JSON envelope containing metadata and quality scores.  |

## Steps

- **step_1** — Parse Commits and Build Generation Plan (`local`, `general_short`)
- **step_2** — Generate Structured Release Notes Document (`llm`, `premium`)
- **step_3** — Evaluate Release Notes Quality and Traceability (`critic`, `moderate`)
- **step_4** — Improve Release Notes Based on Critic Feedback (`llm`, `premium`)
- **step_5** — Write Final Release Notes Artifact (`local`, `general_short`)

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=10, max_improvements=5
- **Max Execution:** 120s
- **Max Cost:** $0.5

## Declarative Guarantees

- All listed changes in the release notes are traceable to commits in the provided commit history.
- No changes are fabricated or inferred beyond what is present in the commit messages.
- Release notes include a version header, change summary, and at least one categorized section.
- Breaking changes, when present, are accompanied by migration notes.
- Contributor acknowledgments are derived solely from commit author information.
- Tone and terminology are calibrated to the specified audience_type.
- Output is valid Markdown suitable for direct publication.

## Composability

- **Output Type:** structured_release_notes_markdown

## Example Usage

```json
{
  "skill_id": "b06-release-notes-gen",
  "inputs": {
    "commit_history": "feat: add 10 Tier 2 skills with meta-skill automation; fix: reroute premium from Opus to Sonnet saving 5x cost; feat: regression test suite with 20/20 passing; fix: checkpoint DB backup before every run; feat: skill chaining via input-from validated; fix: Path B external review improvements applied",
    "version_number": "2.0.0",
    "audience_type": "developers"
  }
}
```
