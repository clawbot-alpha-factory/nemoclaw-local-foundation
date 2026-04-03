# Agent Execution Guide

> Definitive reference for all NemoClaw agents on how to dispatch, execute, and manage work.
> Your execution backend, model, and MCP tools are injected into your system prompt — check your EXECUTION BACKEND block.

---

## 1. How You Execute Work

You have three execution backends. Use the right one for the task:

| Backend | When to Use | MCP Tools | Cost |
|---------|------------|-----------|------|
| **Claude Code CLI** | Complex tasks needing MCP tools (Asana, Supabase, browser, files) | Yes — full suite | Medium-High |
| **Codex CLI** | Code generation, testing, sandboxed execution | Yes — full suite | Medium |
| **API Backend** | Lightweight text generation, analysis, scoring | No | Low |

**Decision rule:** If the task needs to read/write files, query databases, browse the web, or manage Asana tasks → use your CLI backend. If it's pure text generation (drafting, summarizing, scoring) → use the API backend via `call_llm()`.

---

## 2. Claude Code CLI

### Command Format
```bash
claude -p "{prompt}" \
  --output-format json \
  --max-turns {max_turns} \
  --model {model} \
  --permission-mode acceptEdits \
  --cwd {workdir}
```

### Models
| Model | Use Case | Assigned To |
|-------|----------|-------------|
| `opus` | Strategic decisions, complex analysis, system governance | L1 (CEO), L2 (Strategy, Operations), Product Architect |
| `sonnet` | General execution, domain work, content creation | L3 domain leads (Growth, Narrative) |
| `haiku` | Fast turnaround, high-volume tasks, outreach | L4 execution specialists (Sales, Marketing, Client Success, Social) |

### MCP Tools Available
| Tool | What It Does |
|------|-------------|
| **Asana** | Create/update tasks, post comments, manage projects, track missions |
| **Supabase** | Query/write database, run migrations, manage edge functions |
| **Playwright** | Browser automation, web scraping, form filling, screenshots |
| **Context7** | Fetch current library/framework documentation |
| **Filesystem** | Read/write/search files in workspace and project directories |
| **Sentry** | Error tracking, issue management (CEO + Engineering only) |

### Session Resume
```bash
claude --resume {session_id}
```
Use this to continue a long-running task across multiple sessions. The session ID is returned in the JSON output of the initial run.

### Key Rules
- All output goes to `output/` directory in your workspace
- Post heartbeats via Asana MCP (see Section 7)
- Write `STATUS.md` on completion (see Section 6)
- Never hardcode models — your model is assigned in `agent-schema.yaml`
- JSON output format is mandatory for machine-readable results

---

## 3. Codex CLI

### Command Format
```bash
codex exec "{prompt}" \
  --model gpt-5.4 \
  --full-auto \
  --path {workdir}
```

### Sandbox Mode
- **workspace-write**: Can modify files in the workspace directory
- **Network access**: Enabled for package installation and API calls

### MCP Tools
Same suite as Claude Code: Asana, Supabase, Playwright, Context7, Filesystem, Sentry.

### Key Rules
- Commit after each unit of work (atomic commits)
- Write tests alongside code — never ship untested code
- Use conventional commit messages: `feat:`, `fix:`, `refactor:`, `test:`
- Run linting and type checks before marking complete

---

## 4. API Backend

For lightweight tasks that don't need MCP tools or file access.

### Interface
```python
from lib.routing import call_llm

result, error = call_llm(
    messages=[{"role": "user", "content": prompt}],
    task_class="moderate",  # or: structured_short, complex, critical
    max_tokens=4000,
    agent_id="your_agent_id"
)
```

### Task Classes
| Class | Use Case | Cost |
|-------|----------|------|
| `structured_short` | Quick scoring, classification, short answers | Lowest |
| `moderate` | Analysis, drafting, summaries | Medium |
| `complex` | Deep research, multi-step reasoning | Higher |
| `critical` | Strategic decisions, quality gates | Highest |

### Limitations
- No MCP tools (no Asana, no files, no browser)
- No session persistence
- Text in, text out only
- Best for: scoring, classification, text generation, analysis

---

## 5. Your Workspace

Every agent has an isolated workspace:

```
~/.nemoclaw/workspaces/{agent_id}/
├── workspace/          # Working files, drafts, intermediate artifacts
├── output/             # Final deliverables (artifacts, reports, code)
├── shared/             # Cross-agent handoff files
├── CLAUDE.md           # Agent-specific instructions for Claude Code
├── .codex/
│   └── instructions.md # Agent-specific instructions for Codex
└── STATUS.md           # Current mission status (RUNNING/DONE/BLOCKED)
```

### Rules
- Never write outside your workspace unless explicitly instructed
- `output/` is the only directory the CEO checks for deliverables
- `shared/` is readable by other agents for handoffs
- Keep `workspace/` clean — delete intermediate files after use

---

## 6. Mission Protocol

Missions flow through a strict lifecycle:

```
CEO dispatches mission (Asana task + workspace instructions)
    ↓
You receive task in your workspace (CLAUDE.md or .codex/instructions.md)
    ↓
You execute with your assigned backend
    ↓
You write STATUS.md → DONE (with summary of deliverables)
    ↓
CEO reviews output/ directory
    ↓
CEO delivers to human or routes to next agent
```

### STATUS.md Format
```markdown
# Mission Status

## Status: DONE | RUNNING | BLOCKED

## Summary
One paragraph describing what was accomplished.

## Deliverables
- output/report.md — Market analysis report
- output/data.json — Structured findings

## Issues
None | Description of blockers

## Next Steps
None | What the next agent should do
```

---

## 7. Heartbeat Protocol

Every 5 tool calls, post an Asana comment on the mission task:

```
[YOUR_ROLE] Turn {current}/{max_turns}. Status: {what_completed}. Next: {what_planned}.
```

### Examples
```
[STRATEGY_LEAD] Turn 8/40. Status: Completed competitor analysis for 3 players. Next: Synthesizing positioning gaps.
[ENGINEERING_LEAD] Turn 15/30. Status: Scaffold generated, tests passing. Next: Implementing API endpoints.
[SOCIAL_MEDIA_LEAD] Turn 6/20. Status: Generated 3 hook variants scored 9+. Next: Creating video script.
```

### Rules
- Use Asana MCP `add_comment` tool
- Include turn count so CEO can track progress
- Be specific about what's done and what's next
- If approaching max_turns, flag it: "Approaching turn limit — may need extension"

---

## 8. Cross-Agent Handoffs

When your work requires another agent's expertise:

### Writing a Handoff
Write `shared/context.md` in your workspace:
```markdown
# Handoff Context

## From: {your_agent_id}
## To: {target_agent_id}
## Mission: {mission_name}

## What I Did
Brief summary of your work and key findings.

## What You Need to Do
Specific instructions for the receiving agent.

## Key Files
- output/analysis.md — My analysis (read this first)
- shared/data.json — Structured data for your use

## Constraints
- Budget remaining: ${amount}
- Deadline: {date}
- Quality target: {score}/10
```

### Receiving a Handoff
1. Check `shared/context.md` in your workspace for incoming handoffs
2. Read the referenced files before starting
3. Continue the mission — don't restart from scratch
4. Update STATUS.md to reflect the combined work

---

## 9. When to Escalate

### You Are Blocked
1. Write `BLOCKED.md` in your workspace:
```markdown
# BLOCKED

## Agent: {your_agent_id}
## Mission: {mission_name}
## Blocked Since: {timestamp}

## Reason
What's preventing progress.

## What I Tried
Steps taken before escalating.

## What I Need
Specific help required to unblock.
```
2. Update Asana task status to blocked
3. Post Asana comment: `[YOUR_ROLE] BLOCKED: {reason}. Need: {what_you_need}.`

### Budget Exceeded
1. Stop all execution immediately
2. Write STATUS.md with status BLOCKED and reason "Budget exceeded"
3. Post Asana comment: `[YOUR_ROLE] BUDGET EXCEEDED. Spent: ${amount}. Limit: ${limit}. Stopping.`
4. Do NOT continue work — wait for CEO to approve additional budget

### Quality Below Threshold
If output scores below your quality target after 3 revision attempts:
1. Save best attempt to `output/`
2. Write STATUS.md with issues section explaining the quality gap
3. Post Asana comment requesting human review

---

## 10. Self-Improvement

After every completed mission, log lessons learned:

```python
from lib.vector_memory import VectorMemory

memory = VectorMemory()
memory.encode(
    text="Lesson: {what_you_learned}",
    metadata={
        "agent_id": "{your_agent_id}",
        "mission": "{mission_name}",
        "type": "lesson_learned",
        "outcome": "success|failure|partial"
    },
    importance=7,  # 1-10, higher = more important
    collection="agent_memory"
)
```

### What to Log
- Approaches that worked well (importance 6-8)
- Approaches that failed and why (importance 7-9)
- New patterns discovered (importance 5-7)
- Tool limitations encountered (importance 8-10)
- Cross-agent coordination insights (importance 6-8)

### What NOT to Log
- Routine task completions (too noisy)
- Information already in the codebase
- Temporary blockers that were resolved
