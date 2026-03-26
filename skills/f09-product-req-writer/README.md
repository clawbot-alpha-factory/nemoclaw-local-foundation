# Skill: f09-product-req-writer

**Name:** Product Requirements Writer
**Version:** 1.0.0
**Family:** F09 | **Domain:** F | **Tag:** dual-use
**Type:** executor | **Schema:** v2 | **Runner:** v4.0+
**Status:** Production — tested

## What It Does

Takes a product idea, target audience, and business context. Produces a structured product requirements document with:

- Problem statement and target audience analysis
- Scope with explicit in-scope and out-of-scope boundaries
- User stories in "As a / I want / so that" format with unique IDs (US-1, US-2...)
- Functional requirements as system behaviors (no "As a" format) with IDs (FR-1, FR-2...)
- Categorized non-functional requirements (performance, security, scalability, etc.)
- Testable acceptance criteria: condition word AND measurable element, linked to US/FR
- MoSCoW prioritization with scope-appropriate levels
- Dependencies with type (technical, business, external) and direction
- Measurable success metrics with numbers and timeframes
- Edge cases and failure scenarios (minimum 2)
- Assumptions section (explicit when input data is missing)

## Usage

```bash
~/nemoclaw-local-foundation/.venv312/bin/python \
  ~/nemoclaw-local-foundation/skills/skill-runner.py \
  --skill f09-product-req-writer \
  --input product_idea 'A skill marketplace where NemoClaw users can browse, install, and rate community-built skills. Skills are versioned packages with YAML configs and Python run files. Users can filter by domain, rating, and compatibility.' \
  --input target_audience 'NemoClaw developers building local AI systems who want to extend their skill library without writing everything from scratch. Technical, comfortable with CLI, value quality and documentation.' \
  --input business_context 'First community feature for the NemoClaw ecosystem. Goal is to increase adoption and create network effects. No monetization in v1.' \
  --input constraints 'Must work with existing skill-runner.py v4.0+ and v2 schema. Python 3.12. No new infrastructure beyond GitHub for v1.' \
  --input scope_level mvp
```

## Steps

| Step | Name | Type | Task Class |
|---|---|---|---|
| step_1 | Parse product idea and structure requirements plan | local | general_short |
| step_2 | Generate complete product requirements document | llm | complex_reasoning |
| step_3 | Evaluate requirements completeness and structural rigor | critic | moderate |
| step_4 | Strengthen requirements based on critic feedback | llm | complex_reasoning |
| step_5 | Validate final PRD and write artifact | local | general_short |

## Critic Loop

Generate → evaluate → improve loop. Threshold: 8/10. Max improvements: 2.

## Scope Enforcement

| Scope | User Stories | MoSCoW Levels | Special Rules |
|---|---|---|---|
| mvp | 3-7 | Must + Should | Focused minimum viable product |
| full | 5-25 | Must + Should + Could + Won't | Complete product specification |
| increment | 2-5 | Must + Should | Must reference existing system |

## Deterministic Validation

- Required sections: Problem Statement, Target Audience, Scope, User Stories, Functional Requirements, Non-Functional Requirements, Acceptance Criteria, Prioritization, Dependencies, Success Metrics
- User stories: "As a / I want / so that" format with unique IDs, count within scope limits
- Functional requirements: system behaviors only, no "As a" patterns
- NFRs: categorized (performance, security, scalability, etc.)
- Acceptance criteria: condition word AND measurable element, linked to US-N or FR-N
- MoSCoW: scope-appropriate levels enforced
- Dependencies: type (technical, business, external) AND direction (depends on, blocks, etc.)
- Success metrics: measurable with numbers/timeframes, banned generic phrases
- Edge cases: minimum 2
- Scope: both in-scope and out-of-scope required
- Banned: vague requirements ("should be fast", "must be user-friendly", "TBD")
- Anti-hallucination: no invented data, assumptions stated explicitly

## Resume

```bash
~/nemoclaw-local-foundation/.venv312/bin/python \
  ~/nemoclaw-local-foundation/skills/skill-runner.py \
  --skill f09-product-req-writer --thread-id THREAD_ID --resume
```
