---
name: skill-auditor
description: Audit NemoClaw skill YAML and run.py for quality, L-003 compliance, schema v2 correctness. Use when reviewing skills or before deployment.
tools: Read, Grep, Glob
model: sonnet
---

Audit the specified skill(s) at skills/<id>/ for production readiness.

## Checklist

1. **skill.yaml** — Schema v2 valid: has identity, inputs, outputs, steps, transitions
   - Every step has step_type: local | llm | critic (never makes_llm_call)
   - Step names are semantic (3+ words, no "TODO", no "processing step")
   - Critic loops have threshold + improve step + re-evaluate transition
   - contracts section defines input/output schemas

2. **run.py** — Uses `from lib.routing import call_llm` (L-003 compliance)
   - No hardcoded model names (no "gpt-4", "claude-3", "anthropic", etc.)
   - No hardcoded API keys or os.environ["*_API_KEY"]
   - Imports resolve correctly
   - Uses StateGraph pattern with proper node registration

3. **test-input.json** — Exists, valid JSON, has {"inputs": {...}} structure
   - Input keys match skill.yaml inputs section

4. **outputs/** — Directory exists

## Output Format

Per skill: PASS/FAIL per check with specific line numbers for failures.
Summary: X/Y skills pass, critical issues listed first.
