---
name: thread-audit-full
description: Session bootstrap for running a complete NemoClaw system audit across all layers. Invoke when you need a full health picture before a release or after major changes.
disable-model-invocation: true
context: fork
agent: general-purpose
model: sonnet
allowed-tools: Bash, Read, Grep, Glob
---

# Thread: Full System Audit

You are running a **complete NemoClaw audit**. This orchestrates all audit layers in sequence.

## Audit Sequence

### Phase 1 — Validation Suite
```bash
python3 scripts/validate.py
```
31 checks. Must see: 0 failed. Warnings are acceptable.

### Phase 2 — Integration Tests
```bash
python3 scripts/integration_test.py --summary
```
MA-20: 10 phases, 37 checks. Report any phase failures.

### Phase 3 — Skill Quality Audit
Run `/audit-skills` logic:
- Schema v2 compliance for all 124 skills
- L-003 violations (hardcoded models)
- Missing test-input.json files
- Critic loop completeness

### Phase 4 — Agent Coverage Audit
Run `/audit-agents` logic:
- All 124 skills assigned to an agent
- No orphaned skills in capability-registry.yaml
- Authority boundaries respected

### Phase 5 — Code Quality Scan
```bash
grep -rn "TODO\|FIXME\|HACK" scripts/ lib/ --include="*.py" | head -20
grep -rn "ChatAnthropic\|ChatOpenAI\|gpt-4\|claude-3" skills/*/run.py | head -20
```

### Phase 6 — Budget & Costs
```bash
python3 scripts/prod-ops.py costs
python3 scripts/budget-status.py
```

### Phase 7 — System Health
```bash
python3 scripts/prod-ops.py health
```
12 health domains. Flag any degraded domains.

## Final Report Format
```
═══════════════════════════════════
NEMOCLAW FULL AUDIT — [DATE]
═══════════════════════════════════

VALIDATION:    [26/31 passed | X warnings | X failed]
INTEGRATION:   [X/37 passed | X failed]
SKILL QUALITY: [X/124 pass | X L-003 violations | X schema errors]
AGENT COVERAGE:[X/124 assigned | X orphaned]
CODE QUALITY:  [X TODOs | X L-003 remaining]
BUDGET:        [Anthropic $X/$30 | OpenAI $X/$30 | Google $X/$30]
HEALTH:        [X/12 domains healthy | X degraded]

VERDICT: ✅ HEALTHY / ⚠️ DEGRADED / ❌ CRITICAL

PRIORITY ACTIONS:
1. [Most critical issue]
2. [Second issue]
3. [Third issue]
═══════════════════════════════════
```
