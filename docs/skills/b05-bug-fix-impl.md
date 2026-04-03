# Bug Fix Implementer

**ID:** `b05-bug-fix-impl` | **Version:** 1.0.0 | **Family:** F05 | **Domain:** B | **Type:** executor | **Tag:** internal

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

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | Structured bug fix report with root cause analysis, before/after diff, explanation, regression risk, and test cases. |
| `result_file` | file_path | Path to the written markdown artifact containing the full bug fix report. |
| `envelope_file` | file_path | Path to the JSON envelope file with metadata and quality scores. |

## Steps

- **step_1** — Parse Bug Context and Build Fix Plan (`local`, `general_short`)
- **step_2** — Generate Targeted Bug Fix Implementation (`llm`, `premium`)
- **step_3** — Evaluate Fix Quality and Correctness (`critic`, `moderate`)
- **step_4** — Improve Fix Based on Critic Feedback (`llm`, `premium`)
- **step_5** — Write Bug Fix Artifact to Disk (`local`, `general_short`)

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=10, max_improvements=5
- **Max Execution:** 120s
- **Max Cost:** $0.35

## Declarative Guarantees

- Fix addresses only the stated bug — no unrelated refactoring or feature additions.
- Output always includes root cause analysis, before/after diff, and explanation.
- Regression risk assessment is present in every output.
- At least one suggested test case is included to prevent recurrence.
- The before/after diff is minimal and directly tied to the described bug.
- Quality score of 7 or above is required before artifact is written.

## Composability

- **Output Type:** structured_bug_fix_report
- **Can Feed Into:** d04-code-review-analyst, e08-test-case-generator
- **Accepts Input From:** a01-bug-triage-classifier, c03-code-context-extractor

## Example Usage

```json
{
  "skill_id": "b05-bug-fix-impl",
  "inputs": {
    "bug_description": "The extract_section function matches H1 headings when it should only match H2. Returns wrong section content when document title contains a keyword.",
    "affected_code_snippet": "pattern = rf'(?:^|\\n)##?\\s[^\\n]*{re.escape(kw)}[^\\n]*\\n(.*?)(?=\\n##?\\s[^#]|\\Z)'",
    "expected_behavior": "Only match H2 headings (## Heading) and capture content until the next H2 heading.",
    "actual_behavior": "Also matches H1 headings (# Title), causing document title to be returned as section content."
  }
}
```
