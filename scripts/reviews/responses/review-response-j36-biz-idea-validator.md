## 1. Schema Compliance
**Score: 7/10**

### Specific issues found
- **Likely context/output key mismatch in step references**
  - In YAML, step outputs are declared as `output_key`, e.g. `step_1_output`, `generated_validation`, `step_3_output`, `improved_validation`, `artifact_path`.
  - But `input_source` uses mixed forms like `step_1.output`, `step_2.output`, `step_3.output`, which may not match schema/runtime conventions depending on the runner.
  - Examples:
    - `step_2.input_source: "step_1.output"`
    - `step_3.input_source: "step_2.output"`
    - `step_4.input_source: "step_3.output"`
- **Final outputs do not clearly map to step outputs**
  - YAML outputs are `result`, `result_file`, `envelope_file`.
  - No explicit mapping is provided from `generated_validation`/`improved_validation`/`artifact_path` to `result`/`result_file`/`envelope_file`.
- **Artifact contract not actually represented in flow**
  - YAML promises artifact files and envelope file, but the declared step output is only `artifact_path`.
- **Potential schema strictness issue**
  - Fields like `family: F36`, `domain: J`, `tag: dual-use` may be valid in your ecosystem, but if schema v2 is strict JSON-schema based, unrecognized top-level fields could fail unless allowed.

### Recommended fixes
**REQUIRED**
- Normalize all inter-step references to the schema-approved form and ensure they match the runner’s expected convention.
- Add explicit final output mapping so:
  - `result` = final markdown content
  - `result_file` = artifact path
  - `envelope_file` = envelope metadata path

**NICE-TO-HAVE**
- Validate `skill.yaml` against the actual schema v2 validator in CI.
- Add comments/examples for `input_source` and `output_key` usage consistency.

---

## 2. Code-Yaml Alignment
**Score: 3/10**

### Specific issues found
- **Major key mismatch: code expects raw plan, step 1 returns wrapped object**
  - `step_1_local()` returns `{"output": plan}`.
  - `step_2_llm()` reads `context.get("step_1_output", {})` and treats it as the plan directly.
  - This means `plan.get("scope")` etc. will fail to find expected fields because actual structure is `{"output": {...}}`.
- **Same mismatch throughout all steps**
  - `step_3_critic()` expects report string in `improved_validation` or `generated_validation`, but step 2/4 return `{"output": content}`.
  - `step_4_llm()` reads `generated_validation`/`improved_validation` as strings, but they are likely dicts with `output`.
  - `step_5_local()` also expects strings in `improved_validation`, `generated_validation`, etc.
- **YAML output keys vs code return values are inconsistent**
  - YAML `step_5.output_key` is `artifact_path`, but code returns `{"output": "artifact_written"}`.
- **Declared outputs not implemented**
  - `result`, `result_file`, `envelope_file` are never produced by code.
- **Step 5 does not write any file**
  - Direct contradiction of YAML artifact behavior and output contract.
- **`__final_output__` not implemented**
  - YAML says step 5 input source is `__final_output__`; code ignores final candidate selection logic and just picks first truthy item.
- **Quality-based candidate selection not implemented**
  - YAML says `final_output.select: highest_quality`; code does not compare scores.

### Recommended fixes
**REQUIRED**
- Standardize step I/O shape. Either:
  - return raw values under output keys in runtime context, or
  - consistently dereference `["output"]` in downstream steps.
- Implement final output mapping and artifact writing exactly as specified.
- Implement `highest_quality` candidate selection using critic scores.

**NICE-TO-HAVE**
- Create helper functions like `get_step_output(context, key)` to centralize unwrapping.
- Add integration tests covering each step’s expected context shape.

---

## 3. Deterministic Checks
**Score: 4/10**

### Specific issues found
- **Step 3 deterministic checks are partial, not thorough**
  - It checks section existence and some item counts, but misses:
    - explicit validation of TAM, SAM, and SOM all present
    - explicit derivation-chain validation
    - explicit check that each sizing path corresponds to each TAM/SAM/SOM or clearly infeasible
    - explicit check that next steps include owner, timeline, expected outcome
    - explicit check that each risk has likelihood and impact
    - explicit check that recommendation references prior sections by name
- **Numeric grounding regex is weak**
  - `check_estimate_grounding()` only catches money-like tokens such as `$10M`.
  - It misses:
    - plain numbers (`100,000 users`)
    - percentages without `$`
    - ratios, ARPU, CAC, churn, payback months
- **Item count logic is too simplistic**
  - Counts bullets/numbered items only; summary paragraphs are ignored even if required.
  - Excludes item count for Go/No-Go, though spec requires 3–5 factors.
- **Step 5 “deterministic gate” is not a real gate**
  - Only checks section presence and only fails if 4+ sections are missing.
  - It should fail on any required structural guarantee violation.
- **No validation of scope upper bounds**
  - YAML specifies ranges; code checks only minimums.

### Recommended fixes
**REQUIRED**
- Expand deterministic validators for:
  - TAM/SAM/SOM presence
  - all three sizing paths
  - risk labels + likelihood + impact per risk
  - verdict token at start
  - next-step fields
  - references to prior sections
- Make step 5 a strict validator, not a loose presence check.

**NICE-TO-HAVE**
- Parse markdown structurally instead of regexing headings.
- Add a formal validation report object with machine-readable fields.

---

## 4. Anti-Fabrication
**Score: 5/10**

### Specific issues found
- **Prompt intent is good, enforcement is weak**
  - Prompts strongly discourage fabrication, but deterministic enforcement is insufficient.
- **Competitor anti-fabrication not validated**
  - Prompt says “Do NOT invent competitor names,” but code never checks whether names in output were present in input.
- **Numeric anti-fabrication check is too narrow**
  - As above, only catches some currency patterns.
- **No quote/source hallucination checks**
  - If model invents “According to Gartner...” or fake surveys, there is no deterministic detection.
- **Input grounding anchors are naive**
  - Any numeric token found in any input becomes an anchor, even if unrelated to market sizing or revenue.
- **Improvement step may introduce new unsupported numbers**
  - Prompt allows “derived from anchors,” but no deterministic post-check ensures derivation is actually shown.

### Recommended fixes
**REQUIRED**
- Add deterministic check for competitor-name leakage against names/entities extracted from `competitive_landscape`.
- Expand unsupported numeric detection beyond dollar amounts.
- Reject fabricated external authority claims unless present in inputs.

**NICE-TO-HAVE**
- Require explicit “Grounding Notes” per numeric section.
- Add provenance markers such as `[INPUT]`, `[ESTIMATE]`, `[DATA GAP]`.

---

## 5. Error Handling
**Score: 4/10**

### Specific issues found
- **Fallback behavior can silently degrade correctness**
  - `step_2_llm`, `step_3_critic`, `step_4_llm` fall back to `call_openai` regardless of original provider errors, which may violate routing expectations.
- **No retries implemented in code**
  - YAML declares retries, but run.py itself does not implement them; perhaps runner does, but code assumes it.
- **Critic JSON parse failure defaults to score 5**
  - This can allow progress with unvalidated quality.
- **Step 5 fallback writes success without writing**
  - Returns `"artifact_written"` even though no file exists.
- **No hard-fail on declarative guarantee violations**
  - Ungrounded numbers, missing categories, weak verdict linkage only reduce score; if loop limit hits, flow proceeds anyway.
- **No exception handling around main file input parse**
  - Bad JSON input file causes crash.

### Recommended fixes
**REQUIRED**
- Hard-fail in step 5 if declarative guarantees are unmet.
- Do not return success for artifact writing unless the file is actually written.
- Treat critic parse failure as validation failure, not neutral score.

**NICE-TO-HAVE**
- Add explicit structured error codes.
- Add provider-specific fallback policy controlled by context/config.
- Wrap main input loading with robust error handling.

---

## 6. LLM Prompt Quality
**Score: 8/10**

### Specific issues found
- **Strong structure and constraints overall**
  - Clear sectioning, anti-fabrication rules, and scope guidance.
- **Some overloading may hurt output quality**
  - The generation prompt is very dense and mixes structure, methodology, and policy.
- **Potential contradiction around item counts**
  - “bullet-point items per section where applicable” conflicts with summaries/paragraphs and numbered next steps.
- **Competitive section asks for mapping but not format**
  - “Map positioning” without a specific matrix/table format may lead to uneven outputs.
- **Improvement prompt includes blanket rule “Tag ALL numeric claims”**
  - This may over-tag benign counts/timelines and produce awkward text.

### Recommended fixes
**REQUIRED**
- Clarify machine-checkable formatting for risk items, next steps, and recommendation references.

**NICE-TO-HAVE**
- Ask for a fixed template per section.
- Separate policy constraints from content instructions.
- Use XML/JSON tags or markdown subheaders for easier validation.

---

## 7. Scoring Logic
**Score: 6/10**

### Specific issues found
- **Uses `min()` correctly for final quality score**
  - Good: `quality_score = min(structural_score, analytical_rigor, actionability)`.
- **But structural score itself is a weighted formula**
  - Review criterion asked whether min is used, not weighted average. Final score is min, but the deterministic layer is still weighted and includes an arbitrary `10 * 0.4` constant.
- **Structural formula is opaque**
  - `+ 10 * 0.4` acts as a fixed bonus, reducing sensitivity to missing checks.
- **Threshold 7 may be too lenient**
  - Given artifact guarantees, threshold should likely be stricter when anti-fabrication violations exist.
- **Loop escape can bypass threshold**
  - YAML allows proceeding after max iterations even if score < 7.

### Recommended fixes
**REQUIRED**
- Replace weighted structural score with a gate-style minimum across deterministic dimensions or explicit pass/fail checks.
- Prevent finalization when critical anti-fabrication or required-section violations exist.

**NICE-TO-HAVE**
- Split “fatal violations” vs “quality issues.”
- Increase acceptance threshold or require no fatal deterministic violations.

---

## 8. Code Quality
**Score: 5/10**

### Specific issues found
- **Readable overall, but architecture is inconsistent**
  - Main issue is repeated context-shape confusion (`output` wrapping).
- **Dead/unused imports and code**
  - `datetime, timezone` imported but unused.
- **No file writing despite artifact contract**
  - This is both correctness and maintainability debt.
- **Regex-based markdown parsing is brittle**
  - `extract_section()` depends on exact `## ` headings.
- **Potential security/config concerns**
  - `load_env()` manually parses a fixed local path and may encourage secret sprawl outside standard runtime secret management.
- **No type hints / minimal abstraction**
  - Makes integration bugs harder to catch.

### Recommended fixes
**REQUIRED**
- Fix context/output architecture and implement real artifact writing.
- Remove misleading success paths and dead imports.

**NICE-TO-HAVE**
- Add type hints and dataclasses for plan/critic outputs.
- Introduce utility functions for context reading and validation.
- Use a markdown parser library.

---

## 9. Integration Correctness
**Score: 5/10**

### Specific issues found
- **Provider call patterns are mostly okay**
  - `call_resolved()` and provider-specific wrappers are reasonable.
- **But no budget tracking integration**
  - YAML requires `budget_state` in context and observability says `track_cost/tokens/latency`; code does none of this.
- **No use of `execution_role` from YAML**
  - Prompt duplicates role text manually instead of consuming config.
- **Fallback to OpenAI may violate routing/budget policy**
  - If resolved provider is Anthropic/Google, automatic fallback to OpenAI may be undesirable.
- **No envelope metadata generation**
  - Integration contract incomplete.
- **No observability output**
  - Metrics file in YAML is ignored.

### Recommended fixes
**REQUIRED**
- Implement budget/cost/token accounting or integrate with runner-native tracking.
- Respect routing policy for provider fallback.
- Generate envelope metadata as declared.

**NICE-TO-HAVE**
- Surface model/provider used in outputs/envelope.
- Log validation metrics and quality scores to observability sink.

---

## 10. Production Readiness
**Score: 3/10**

### Specific issues found
- **Would not ship as-is**
  - Biggest risk: **the code does not implement the YAML contract**, especially outputs and artifact writing.
- **Critical functional bug likely breaks multi-step flow**
  - Wrapped `{"output": ...}` values are treated as raw strings/dicts inconsistently.
- **Anti-fabrication guarantees are not actually enforceable**
  - Numeric grounding and competitor checks are too weak.
- **Final gate is not a gate**
  - Skill can approve low-quality/non-compliant output after loop exhaustion.

### Recommended fixes
**REQUIRED**
- Align runtime data model across all steps.
- Implement strict final validation + real artifact/envelope writing.
- Strengthen deterministic anti-fabrication checks.

**NICE-TO-HAVE**
- Add CI tests with golden cases and failure cases.
- Add machine-readable intermediate representation for validation report.

---

# Overall score
**5/10**

# Top 3 REQUIRED fixes
1. **Fix step I/O and context alignment**
   - Downstream steps must correctly consume outputs from upstream steps; current `{"output": ...}` wrapping is inconsistent and likely breaks the workflow.
2. **Implement real artifact behavior**
   - Step 5 must actually write the markdown file and envelope JSON, and return `result`, `result_file`, and `envelope_file` consistently with YAML.
3. **Make deterministic validation strict and enforceable**
   - Hard-fail on missing required sections, missing risk categories, missing sizing paths, ungrounded numeric claims, and invented competitor names.

# Top 3 NICE-TO-HAVE improvements
1. Replace regex-only markdown checks with structured parsing/template-based output.
2. Add observability and budget tracking per YAML.
3. Refactor prompts into reusable templates and add explicit formatting substructures for easier validation.

# Verdict
**REJECT**