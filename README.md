# NemoClaw Local Foundation

**Status:** Multi-Agent System (MA-4 complete, 20 phases planned)
**Skills:** 30 built across 10 families (479 in catalog)
**Agents:** 7 defined with enforcement (MA-1 through MA-4)
**Runtime:** Python 3.12.13 via .venv312
**Execution:** LangGraph StateGraph + Direct Anthropic, OpenAI, Google API
**Validation:** 31/31 checks passing
**Repo:** github.com/clawbot-alpha-factory/nemoclaw-local-foundation

---

## What This Is

A local MacBook-based AI company foundation built on LangGraph with multi-agent coordination. The system includes 30 production-tested skills across 10 families, a 7-agent leadership team with authority hierarchy and domain enforcement, 3-layer memory architecture, structured inter-agent messaging with voting and governance, a full decision lifecycle system, and automated skill generation via meta-skills.

This project started as a NemoClaw/OpenShell local build and migrated to a custom LangGraph + Direct API architecture in Phase 6. The NemoClaw sandbox is retained but not required for inference.

---

## Architecture

| Layer | Technology |
|---|---|
| Agent execution | LangGraph StateGraph |
| State persistence | LangGraph SqliteSaver |
| Multi-agent orchestration | orchestrator.py v2 + agent registry |
| Agent memory | 3-layer: private, shared workspace, long-term |
| Agent messaging | 11-intent structured messaging with voting |
| Decision system | Full lifecycle with dependency tracking |
| Inference — Anthropic | claude-sonnet-4-6, claude-haiku-4-5 |
| Inference — OpenAI | gpt-5.4, gpt-5.4-mini, o3 |
| Inference — Google | gemini-2.5-pro, gemini-2.5-flash |
| Model routing | 9 aliases, 10 task classes — config/routing/routing-config.yaml v4.0 |
| Budget enforcement | $30/provider, 90% warn, 100% hard stop — config/routing/budget-config.yaml v3.0 |
| Skill execution | skill-runner.py v4.0, schema v2, 5-step pipeline with critic loop |
| Skill automation | Meta-skills generate specs + code at ~$0.25/skill |
| External tools | 16-tool registry (2 active: GitHub, Asana) |
| Validation | 31 checks across 6 categories |
| Machine | MacBook Apple Silicon M1, 16GB RAM, macOS Sequoia |

---

## 7 Agents (AI Company Leadership Team)

| # | Agent | Title | Level | Capabilities |
|---|---|---|---|---|
| 1 | Strategy Lead | CSO | 2 | 5 (market research, trend scanning, validation) |
| 2 | Product Architect | CPO | 3 | 5 (requirements, architecture, API design) |
| 3 | Growth & Revenue Lead | CRO | 3 | 1 (pricing) — more planned |
| 4 | Narrative & Content Lead | CCO | 3 | 6 (copy, video, docs, KB, meetings, tone) |
| 5 | Engineering Lead | CTO | 3 | 7 (code, scaffold, bug fix, CI/CD, release, setup, runbook) |
| 6 | Operations Lead | COO | 2 | 5 (format, prompts, skill gen, research) |
| 7 | Executive Operator | CEO | 1 | Full override, governance, conflict resolution |

Config: `config/agents/agent-schema.yaml`, `config/agents/capability-registry.yaml`
Engine: `scripts/agent_registry.py`

---

## 30 Skills

| Family | Skills | Domain |
|---|---|---|
| F01 System Architecture | a01-arch-spec-writer, a01-sys-context-mapper, a01-api-surface-designer | A |
| F05 Code Generation | b05-feature-impl-writer, b05-script-automator, b05-scaffold-gen, b05-bug-fix-impl | B |
| F06 DevOps & Release | b06-cicd-designer, b06-release-notes-gen | B |
| F07 Technical Docs | c07-setup-guide-writer, c07-runbook-author, c07-api-doc-gen, c07-decision-record-writer | C |
| F08 Knowledge Mgmt | e08-comp-intel-synth, e08-meeting-summary-gen, e08-kb-article-writer | E |
| F09 Product Strategy | f09-product-req-writer, f09-pricing-strategist | F |
| F11 Creative | d11-copywriting-specialist, d11-video-script-writer | D |
| F12 Research | e12-market-research-analyst, e12-tech-trend-scanner | E |
| F25 Prompt Engineering | g25-output-format-enforcer, g25-sys-prompt-designer | G |
| F26 Meta-Skills | g26-skill-spec-writer, g26-skill-template-gen | G |
| F35 Humanizer | i35-tone-calibrator | I |
| F36 Business Builder | j36-biz-idea-validator, j36-mvp-scope-definer | J |
| Utility | research-brief | — |

---

## Multi-Agent Infrastructure

| Phase | System | Status | Tests |
|---|---|---|---|
| MA-1 | Agent Schema & Registry | ✅ | 8/8 |
| MA-2 | 3-Layer Memory + patches | ✅ | Verified |
| MA-3 | Message Protocol + patches | ✅ | 14/14 |
| MA-4 | Decision Log System | ✅ | 12/12 |
| MA-5 | Task Decomposition | ⏳ Next | — |
| MA-6–20 | Cost governance, interaction modes, conflict... | Planned | — |

---

## Quick Start

```bash
cd ~/nemoclaw-local-foundation && source .venv312/bin/activate

# System validation
python3 scripts/validate.py

# Budget
python3 scripts/budget-status.py

# Run a skill
python3 skills/skill-runner.py --skill e12-market-research-analyst \
  --input research_topic "AI agents" --input industry_context "B2B SaaS"

# Skill chaining
python3 skills/skill-runner.py --skill f09-product-req-writer \
  --input product_idea "AI assistant" --input target_audience "Engineers" \
  --input scope_level mvp --input-from path/to/envelope.json

# Regression tests (30 skills)
python3 scripts/test-all.py

# Multi-agent pipeline
python3 scripts/orchestrator.py --workflow workflows/pipeline-v2.yaml

# NL workflow planning
python3 scripts/orchestrator.py --plan "Research AI agents and write a product spec" --dry-run

# Agent systems
python3 scripts/agent_registry.py --summary
python3 scripts/agent_memory.py --workspace test --test
python3 scripts/agent_messaging.py --test
python3 scripts/decision_log.py --test
```

---

## Directory Structure

```
nemoclaw-local-foundation/
├── config/
│   ├── agents/                    # Agent definitions + capability registry
│   │   ├── agent-schema.yaml
│   │   └── capability-registry.yaml
│   ├── routing/
│   │   ├── routing-config.yaml    # v4.0
│   │   └── budget-config.yaml     # v3.0, $30/provider
│   └── .env                       # API keys (gitignored)
├── docs/
│   ├── architecture/
│   ├── extensions/
│   └── reference/
├── scripts/
│   ├── agent_memory.py            # MA-2
│   ├── agent_messaging.py         # MA-3
│   ├── agent_registry.py          # MA-1
│   ├── budget-enforcer.py
│   ├── budget-status.py
│   ├── decision_log.py            # MA-4
│   ├── obs.py
│   ├── orchestrator.py            # Multi-agent v2
│   ├── skill-runner.py            # v4.0
│   ├── test-all.py
│   ├── tier3-batch-build.py
│   ├── tools.py
│   ├── validate.py
│   ├── new-skill.py
│   └── checkpoint_utils.py
├── skills/                        # 30 skill directories
├── workflows/                     # Pipeline definitions
└── README.md
```

---

## Key References

| Document | Location |
|---|---|
| Architecture Lock | docs/architecture/architecture-lock.md |
| Skill System | docs/architecture/skill-system.md |
| Skill Build Plan | docs/architecture/skill-build-plan.md |
| Script Reference | docs/reference/script-reference.md |
| Config Reference | docs/reference/config-reference.md |
| Design Decisions | docs/reference/design-decisions-log.md |
| External Tools | docs/extensions/external-tools-registry.md |
| Agent Schema | config/agents/agent-schema.yaml |
| Capability Registry | config/agents/capability-registry.yaml |
