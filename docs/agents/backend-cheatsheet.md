# Backend Cheatsheet

Quick reference for agent execution backends. See `execution-guide.md` for full details.

---

## One-Liner Examples

```bash
# Claude Code — complex task with MCP tools
claude -p "Research top 5 competitors in AI agent space" --output-format json --max-turns 30 --model sonnet --permission-mode acceptEdits --cwd ~/.nemoclaw/workspaces/strategy_lead/

# Codex — code generation with sandbox
codex exec "Implement REST API for user management with tests" --model gpt-5.4 --full-auto --path ~/.nemoclaw/workspaces/engineering_lead/

# API — lightweight text generation
call_llm([{"role": "user", "content": "Score this pitch 1-10"}], "structured_short", 200)

# Resume a Claude Code session
claude --resume ses_abc123def456
```

---

## Model Selection

| Model | Backend | Tier | Best For | Agents |
|-------|---------|------|----------|--------|
| `opus` | Claude Code | L1-L2 | Strategic decisions, governance, complex analysis | Tariq, Nadia, Khalid, Layla |
| `sonnet` | Claude Code | L3 | Domain execution, content, revenue analysis | Omar, Yasmin |
| `haiku` | Claude Code | L4 | Fast execution, outreach, social, campaigns | Hassan, Rania, Amira, Zara |
| `gpt-5.4` | Codex | L3 | Code generation, testing, CI/CD | Faisal |

---

## MCP Tool Inventory

| Tool | Purpose | Key Operations |
|------|---------|---------------|
| **Asana** | Project/task management | `create_task`, `update_task`, `add_comment`, `search_tasks`, `get_my_tasks` |
| **Supabase** | Database & edge functions | `execute_sql`, `apply_migration`, `list_tables`, `deploy_edge_function` |
| **Playwright** | Browser automation | `navigate`, `click`, `type`, `snapshot`, `screenshot`, `evaluate` |
| **Context7** | Library documentation | `resolve-library-id`, `query-docs` |
| **Filesystem** | File operations | `read_file`, `write_file`, `edit_file`, `search_files`, `list_directory` |
| **Sentry** | Error tracking | View issues, track errors, monitor releases (CEO + Engineering only) |

---

## Agent → Backend Matrix

| Agent | Primary | Model | MCP Tools | Max Turns |
|-------|---------|-------|-----------|-----------|
| Tariq (CEO) | claude_code | opus | asana, supabase, playwright, context7, filesystem, sentry | 50 |
| Nadia (Strategy) | claude_code | opus | asana, supabase, playwright, context7, filesystem | 40 |
| Khalid (Operations) | claude_code | opus | asana, supabase, context7, filesystem | 40 |
| Layla (Product) | claude_code | opus | asana, supabase, playwright, context7, filesystem | 40 |
| Omar (Revenue) | claude_code | sonnet | asana, supabase, playwright, context7, filesystem | 30 |
| Yasmin (Content) | claude_code | sonnet | asana, supabase, context7, filesystem | 30 |
| Faisal (Engineering) | codex | gpt-5.4 | asana, supabase, playwright, context7, filesystem, sentry | 30 |
| Hassan (Sales) | claude_code | haiku | asana, supabase, playwright, context7, filesystem | 20 |
| Rania (Marketing) | claude_code | haiku | asana, supabase, playwright, context7, filesystem | 20 |
| Amira (Client Success) | claude_code | haiku | asana, supabase, context7, filesystem | 20 |
| Zara (Social) | claude_code | haiku | asana, supabase, playwright, context7, filesystem | 20 |

---

## Common Error Patterns

| Error | Cause | Fix |
|-------|-------|-----|
| `Permission denied` | Wrong permission mode | Use `--permission-mode acceptEdits` |
| `Max turns exceeded` | Task too complex for turn limit | Break into subtasks or request turn extension |
| `MCP tool not found` | Tool not configured in workspace | Check `.claude/settings.json` for MCP server config |
| `Session expired` | Claude Code session timed out | Use `claude --resume {session_id}` to continue |
| `Budget exceeded` | Provider spend limit hit | Stop immediately, write BLOCKED.md, notify CEO |
| `Model not available` | Wrong model name | Use exact names: `opus`, `sonnet`, `haiku`, `gpt-5.4` |
| `Sandbox violation` | Codex tried to write outside workspace | Use `--path` to set correct workspace root |
| `Heartbeat missed` | Forgot Asana comment interval | Post comment every 5 tool calls minimum |

---

## Decision Flowchart

```
Need to execute a task?
├── Needs MCP tools (files, DB, browser, Asana)?
│   ├── Yes + Code task → Codex CLI (engineering_lead)
│   └── Yes + Non-code → Claude Code CLI (your assigned model)
└── No (pure text generation)?
    └── API Backend → call_llm(messages, task_class)
```
