---
name: thread-research
description: Session bootstrap for deep codebase research — investigating architecture, tracing code paths, understanding complex systems, answering how/why questions about NemoClaw. Invoke when you need to understand something deeply before changing it.
disable-model-invocation: true
context: fork
agent: Explore
allowed-tools: Read, Grep, Glob, Bash
---

# Thread: Deep Research

You are running a **deep research session** on NemoClaw's codebase.

Research request: $ARGUMENTS

## Research Protocol

### Step 1 — Scope the Question
Identify which domain(s) are relevant:
- `lib/routing.py` + `config/routing/` → routing/budget questions
- `skills/*/` → skill execution questions
- `config/agents/` + `scripts/agent_*.py` → agent behavior questions
- `command-center/backend/` → API/service questions
- `command-center/frontend/` → UI questions
- `scripts/` → operational questions

### Step 2 — Find Entry Points
```bash
# Find by keyword
grep -rn "<keyword>" --include="*.py" --include="*.yaml" --include="*.ts"

# Find by file pattern
find skills/ -name "*.yaml" | head -20
ls scripts/ | grep -i <topic>
```

### Step 3 — Trace the Code Path
Start from the entry point, read the actual code:
- For skills: skill.yaml → run.py → lib/routing.py
- For agents: agent-schema.yaml → capability-registry.yaml → agent_registry.py
- For backend: main.py → routers/ → services/

### Step 4 — Cross-Reference Architecture Locks
Check `docs/architecture-lock.md` for any L-XXX locks that govern the area.

### Step 5 — Synthesize Findings
Return:
1. **Direct answer** to the research question
2. **Key files** involved (with line numbers)
3. **Architecture locks** that constrain changes
4. **Risks** if modifying this area
5. **Recommended approach** if change is needed

## Research Output Format
```
RESEARCH: [Question]
━━━━━━━━━━━━━━━━━━━━

ANSWER:
[Direct answer]

KEY FILES:
- path/to/file.py:L42 — [what it does]
- config/thing.yaml — [what it configures]

ARCHITECTURE LOCKS:
- L-XXX: [constraint]

RISKS:
- [what could break if changed]

APPROACH:
[Recommended way to proceed]
```
