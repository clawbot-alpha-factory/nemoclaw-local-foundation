# Knowledge Base Article Writer

**ID:** `e08-kb-article-writer` | **Version:** 1.0.0 | **Family:** F08 | **Domain:** E | **Type:** executor | **Tag:** dual-use

## Description

Produces structured knowledge base articles from a topic, target audience, and source material. Generates clear titles, problem statements, step-by-step solutions, troubleshooting tips, related article suggestions, and metadata tags. Supports how-to, troubleshooting, reference, and conceptual article types. All solutions are grounded in provided source material to prevent fabrication.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `topic` | string | Yes | The subject or question the KB article should address. |
| `article_type` | string | Yes | The type of KB article to produce. |
| `target_audience` | string | Yes | The intended reader — e.g., end users, IT admins, developers, support agents. |
| `source_material` | string | Yes | Raw source content — documentation excerpts, support tickets, product specs, or internal notes — that grounds all solutions and steps in the article.  |
| `related_article_hints` | string | No | Optional comma-separated list of related article titles or IDs to suggest. |
| `tone` | string | No | Desired tone for the article. |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | The fully structured KB article in markdown format. |
| `result_file` | file_path | Path to the written KB article artifact file. |
| `envelope_file` | file_path | Path to the JSON envelope containing metadata and quality scores. |

## Steps

- **step_1** — Parse Inputs Validate Source Build Article Plan (`local`, `general_short`)
- **step_2** — Generate Structured KB Article Draft (`llm`, `premium`)
- **step_3** — Evaluate Article Quality Anti-Fabrication Compliance (`critic`, `moderate`)
- **step_4** — Improve Article Based On Critic Feedback (`llm`, `premium`)
- **step_5** — Write Final Article Artifact (`local`, `general_short`)

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=10, max_improvements=5
- **Max Execution:** 120s
- **Max Cost:** $0.35

## Declarative Guarantees

- All article content is grounded in the provided source_material — no fabricated solutions or steps.
- The article structure matches the requested article_type (how-to, troubleshooting, reference, or conceptual).
- Every article includes a title, problem statement or overview, solution or explanation, troubleshooting tips, and metadata tags.
- The tone and vocabulary are calibrated to the specified target_audience.
- Related article suggestions are drawn from provided hints or clearly marked as suggested placeholders.
- The critic loop ensures a minimum quality score of 7 before artifact write.
- Anti-fabrication compliance is explicitly evaluated in every critic pass.

## Composability

- **Output Type:** structured_kb_article_markdown

## Example Usage

```json
{
  "skill_id": "e08-kb-article-writer",
  "inputs": {
    "topic": "How to add a new skill to the NemoClaw system",
    "article_type": "how-to",
    "target_audience": "developer",
    "source_material": "Use g26-skill-spec-writer to generate the spec from a skill concept. Then use g26-skill-template-gen to generate the code from the spec. Deploy files to skills/skill-id/ directory with run.py, skill.yaml, and outputs/.gitignore. Run skill-runner.py with test inputs to verify. Fix any context key mismatches between yaml output_key and code context.get calls. Ensure step_3 and step_4 have cached:false in yaml. Run validate.py to confirm 31/31 checks pass. Commit with descriptive message."
  }
}
```
