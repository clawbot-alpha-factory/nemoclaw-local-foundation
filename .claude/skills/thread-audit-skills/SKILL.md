---
name: thread-audit-skills
description: Session bootstrap for deep skill quality audit — schema compliance, L-003 violations, critic loops, revenue gaps. Invoke for targeted skill layer review.
disable-model-invocation: true
context: fork
agent: general-purpose
model: sonnet
allowed-tools: Read, Grep, Glob, Bash
---

# Thread: Skill Quality Audit

You are running a **deep skill audit** across all 124 NemoClaw skills.

## Audit Checklist (per skill)

### 1. Schema v2 Compliance
```bash
# Find skills missing required fields
grep -rL "step_type" skills/*/skill.yaml
grep -rn "makes_llm_call" skills/*/skill.yaml   # ← L-009 violation
```
Every skill.yaml must have: identity, inputs, outputs, steps, transitions.
Every step must have `step_type: local | llm | critic`.

### 2. L-003 Compliance (Routing)
```bash
# Find hardcoded models
grep -rn "ChatAnthropic\|ChatOpenAI\|ChatGoogleGenerativeAI" skills/*/run.py
grep -rn "gpt-4\|claude-3\|claude-opus\|claude-sonnet\|gemini" skills/*/run.py
grep -rn "model=" skills/*/run.py | grep -v "call_llm\|routing\|#"
```
All LLM calls must use `from lib.routing import call_llm` with a task_class alias.

### 3. Test Input Files
```bash
# Find skills missing test-input.json
for d in skills/*/; do [ ! -f "$d/test-input.json" ] && echo "MISSING: $d"; done
```

### 4. Critic Loop Completeness
For skills with a critic step, verify:
- Critic step scores on multiple dimensions
- Improvement step exists
- Re-evaluation transition exists
- Threshold ≥ 9.0

### 5. Output Directory
```bash
for d in skills/*/; do [ ! -d "$d/outputs" ] && echo "MISSING outputs/: $d"; done
```

### 6. Step Name Quality
```bash
# Find semantic violations (short names, generic names)
grep -rn "step_name: \"Step\|step_name: \"Process\|step_name: \"TODO" skills/*/skill.yaml
```
All step names must be 3+ words, descriptive.

### 7. Revenue Coverage Check
Critical revenue skill families that must be production-ready:
- `rev-01` through `rev-25` (25 skills)
- `k40` through `k61` (commercial)
- `out-01` through `out-08` (outreach)

## Report Format
```
SKILL AUDIT REPORT — [DATE]
━━━━━━━━━━━━━━━━━━━━━━━━━━

Total skills: 124
Schema v2 compliant: X/124
L-003 compliant: X/124
Has test-input.json: X/124
Has critic loop (where needed): X/Y
Has outputs/ dir: X/124

L-003 VIOLATIONS (fix first):
  - skills/X/run.py line N: hardcoded "gpt-4o"
  ...

SCHEMA VIOLATIONS:
  - skills/Y/skill.yaml: missing transitions
  ...

REVENUE CRITICAL GAPS:
  - skills/rev-XX: [issue]
  ...

PRIORITY FIXES:
1. ...
```
