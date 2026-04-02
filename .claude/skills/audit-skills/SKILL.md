---
name: audit-skills
description: Audit all built and registered skills for production readiness — schema, compliance, critic loops, revenue gaps. Use when auditing skill quality.
context: fork
model: sonnet
allowed-tools: Read, Grep, Glob
---

Audit all built skills and registered skills for production readiness. Read each skill before scoring it.

## 1. Built Skills Inventory
Scan every directory under `skills/`. For each skill:
- **File completeness**: has `skill.yaml`, `run.py`, `test-input.json`, `outputs/`
- **Schema validity**: `schema_version: 2`, `step_type` values only `local`/`llm`/`critic`
- **Model alias compliance**: no hardcoded model names — L-003
- **Critic loop**: skills of type `executor` or `transformer` should have `critic_loop.enabled: true`
- **Contracts**: has `machine_validated` block with `min_length`, `min_quality_score`

## 2. Registered Skills (K40-K54)
Check registered skills. For each: does directory exist? Is there an assigned agent?

## 3. Revenue-Critical Skill Gap Analysis
Rate coverage for: payment processing, lead gen, cold outreach, proposal gen, invoice gen, social automation, content repurposing, SEO, sales qualification, contract gen, client reporting, competitive intel.

## 4. Skill Family Production-Readiness Ratings
Tier 1 (production-ready) through Tier 4 (not started) for each family.

## 5. Final Report
Print structured summary with: built skills scanned, schema valid count, L-003 compliant count, registered skills status, revenue gaps, top priority skills to build.
