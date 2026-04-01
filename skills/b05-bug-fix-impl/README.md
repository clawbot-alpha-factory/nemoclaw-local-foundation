# b05-bug-fix-impl

**ID:** `b05-bug-fix-impl`
**Version:** 1.0.0
**Type:** executor
**Family:** F05 | **Domain:** B | **Tag:** internal

## Description

Takes a bug description, affected code snippet, expected behavior, and actual behavior. Produces a structured fix with root cause analysis, minimal code changes with before/after diff, explanation of why the fix works, regression risk assessment, and suggested test cases to prevent recurrence. Anti-fabrication: fix must address only the stated bug without introducing unrelated changes.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `bug_description` | string | Yes | A clear description of the bug being fixed. |
| `affected_code_snippet` | string | Yes | The code snippet containing the bug. |
| `expected_behavior` | string | Yes | What the code should do when working correctly. |
| `actual_behavior` | string | Yes | What the code currently does (the buggy behavior). |
| `language` | string | No | Programming language of the affected code snippet. |
| `severity` | string | No | Severity level of the bug. |

## Execution Steps

1. **Parse Bug Context and Build Fix Plan** (local) — Validate all inputs, detect the programming language if not specified, and construct a structured analysis plan including scope boundaries to enforce the anti-fabrication constraint (fix only the stated bug).

2. **Generate Targeted Bug Fix Implementation** (llm) — Perform root cause analysis of the bug, then produce a minimal, targeted fix. Output must include: (1) root cause analysis, (2) before/after unified diff, (3) explanation of why the fix works, (4) regression risk assessment, (5) suggested test cases. The fix must address ONLY the stated bug — no unrelated refactoring, style changes, or feature additions.

3. **Evaluate Fix Quality and Correctness** (critic) — Two-layer validation of the generated fix. Deterministic checks: verify presence of root cause section, before/after diff block, explanation section, regression risk section, and at least one test case. LLM evaluation: score fix correctness, minimality (no unrelated changes), clarity of explanation, regression risk accuracy, and test case relevance. Combine scores with min() and produce a quality_score 0-10.

4. **Improve Fix Based on Critic Feedback** (llm) — Revise the bug fix based on specific critic feedback. Address identified weaknesses such as incomplete root cause analysis, unrelated code changes, missing test cases, or unclear explanations. Maintain the anti-fabrication constraint — only fix the stated bug, nothing more.

5. **Write Bug Fix Artifact to Disk** (local) — Final deterministic gate: confirm the selected fix output is non-empty, then write the structured bug fix report to the artifact storage location. Returns {"output": "artifact_written"} on success.


## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/b05-bug-fix-impl/run.py --force --input bug_description "value" --input affected_code_snippet "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)
