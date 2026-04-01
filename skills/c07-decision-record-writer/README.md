# c07-decision-record-writer

**ID:** `c07-decision-record-writer`
**Version:** 1.0.0
**Type:** executor
**Family:** F07 | **Domain:** C | **Tag:** internal

## Description

Produces a structured Architecture Decision Record (ADR) following the Michael Nygard template. Takes a decision title, context, and options considered, then generates a complete ADR with status, context and problem statement, decision drivers, options with pros and cons, chosen option with justification, logically derived consequences, compliance notes, and review date. Anti-fabrication enforcement ensures consequences are grounded in the chosen option.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `decision_title` | string | Yes | The concise title of the architectural decision being recorded. |
| `decision_context` | string | Yes | The context surrounding the decision — the forces at play, the problem being sol |
| `options_considered` | list | Yes | A list of options that were considered. Each entry should name the option and pr |
| `chosen_option` | string | Yes | The name of the option that was selected as the decision. |
| `decision_drivers` | list | No | Key factors, constraints, or goals that drove the decision. If not provided, the |
| `status` | string | No | The current status of the ADR. |
| `compliance_domains` | list | No | Compliance or regulatory domains relevant to this decision (e.g., GDPR, SOC2, HI |
| `review_date` | string | No | ISO 8601 date string for when this ADR should be reviewed (e.g., "2027-03-27").  |

## Execution Steps

1. **Parse Inputs and Build ADR Generation Plan** (local) — Validate all inputs, normalize the options list, resolve the review date if not provided, infer decision drivers from context if the list is empty, and construct a structured generation plan that will guide the LLM in producing a complete, grounded ADR.

2. **Generate Complete ADR Document Draft** (llm) — Using the validated inputs and generation plan, produce a complete ADR following the Michael Nygard template. Include all required sections: title, status, context and problem statement, decision drivers, options considered with detailed pros and cons, chosen option with full justification, consequences (positive, negative, neutral) logically derived from the chosen option, compliance notes, and review date. Anti-fabrication: every consequence must be traceable to a specific property of the chosen option.

3. **Evaluate ADR Quality and Structural Completeness** (critic) — Two-layer validation of the generated ADR. Deterministic layer: verify all required Nygard template sections are present (title, status, context, decision drivers, options with pros/cons, chosen option, consequences split by positive/negative/neutral, compliance notes, review date). LLM evaluation layer: score reasoning quality, consequence grounding (anti-fabrication check), justification depth, and overall coherence. Combine scores with min() to produce a final quality_score 0-10.

4. **Improve ADR Based on Critic Feedback** (llm) — Revise the ADR draft using the critic's structured feedback. Address all identified deficiencies: strengthen consequence grounding by explicitly linking each consequence to a property of the chosen option, deepen justification reasoning, fill any missing template sections, and improve clarity of pros/cons analysis. Preserve all factual content from the original draft while correcting quality issues.

5. **Write Final ADR Artifact to Storage** (local) — Deterministic final gate: confirm the selected ADR output is non-empty and contains the minimum required Nygard sections, then write the artifact to the configured storage location. Returns the artifact path confirmation to the runner.


## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/c07-decision-record-writer/run.py --force --input decision_title "value" --input decision_context "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)
