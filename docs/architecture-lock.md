# Architecture Lock Register

Locked architectural decisions for the NemoClaw Local Foundation. These decisions are final and must not be revisited without explicit approval.

## Runtime & Infrastructure Locks

| # | Decision | Locked Value | Rationale | Locked Date |
|---|---|---|---|---|
| L-001 | Python version | 3.12.13 via `.venv312` | Stability + LangGraph compatibility | Phase 1 |
| L-002 | State management | LangGraph StateGraph + SqliteSaver | Checkpointing + graph-based execution | Phase 6 |
| L-003 | LLM integration | Direct API via LangChain wrappers | No sandbox overhead, clean provider abstraction | Phase 6 |
| L-004 | Model routing | 9-alias system via `routing-config.yaml` | Per-use-case model selection without hardcoding | Phase 6 |
| L-005 | Budget enforcement | Per-provider limits via `budget-config.yaml` | Cost control across Anthropic/OpenAI/Google | Phase 6 |
| L-006 | Sandbox decision | No sandbox required (Decision Gate G3) | OpenShell overhead unnecessary for local execution | Phase 6 |
| L-007 | Skill execution | `skill-runner.py` v4.0 | Single entry point for all skill execution | Tier 1 |
| L-008 | Validation gate | `validate.py` 31-check suite | Must pass before any commit | Tier 1 |
| L-009 | Skill schema | `skill-yaml-schema-v2` | Standardized skill definition format | Tier 1 |

## Skill Architecture Locks

| # | Decision | Locked Value | Rationale |
|---|---|---|---|
| L-010 | Section extraction | `##\s` regex (not `##?`) | Prevents false H2 matches |
| L-011 | Token budgets | overview=12K, strategic=16K, detailed=20K | Depth-driven quality control |
| L-012 | Quality scoring | `min()` across dimensions | Never weighted average — catches weakest dimension |
| L-013 | Acceptance threshold | Equal to `min_quality_score` (7) | No separate threshold logic |
| L-014 | Failure mode | Hard-fail on integrity violations | No silent degradation |
| L-015 | Output key naming | `step_1_output`, `generated_{thing}`, `improved_{thing}`, `artifact_path` | Consistent context key convention |
| L-016 | LLM call pattern | LangChain wrappers for all calls | No raw API calls in skills |
| L-017 | Shell quoting | Single quotes for `$` content | Prevents shell variable expansion |
| L-018 | YAML editing | Python regex, never `yaml.dump()` | `yaml.dump()` destroys artifacts section |

## Multi-Agent Architecture Locks

### MA-1: Agent Schema & Registry
| # | Decision | Locked Value |
|---|---|---|
| L-100 | Agent count | 7 agents with defined roles |
| L-101 | Authority levels | 3-tier: 1 (strategic), 2 (execution lead), 3 (specialist) |
| L-102 | Agent schema | Capabilities, authority, domains per agent |

### MA-2: 3-Layer Memory
| # | Decision | Locked Value |
|---|---|---|
| L-110 | Memory architecture | 3-layer: working, episodic, shared workspace |
| L-111 | Workspace write permission | Requires `domain_patterns` match |

### MA-3: Message Protocol
| # | Decision | Locked Value |
|---|---|---|
| L-120 | Message interface | `channel.add_message(Message(...))` — not `.send()` |
| L-121 | Channel model | Named channels with typed messages |

### MA-4: Decision Log
| # | Decision | Locked Value |
|---|---|---|
| L-130 | Decision tracking | Rationale + alternatives + outcome required |
| L-131 | Auditability | All decisions logged with agent ID and timestamp |

### MA-5: Task Decomposition
| # | Decision | Locked Value |
|---|---|---|
| L-140 | Return signature | `decompose()` returns 3-tuple `(plan, source, error)` |
| L-141 | Parallel cap | 5 concurrent tasks per wave |
| L-142 | Cost gating | Auto-execute ≤$15, approval required >$15 |
| L-143 | Template set | `market_to_product`, `validate_and_scope`, `research_and_document`, `full_product_pipeline` |
| L-144 | LLM fallback | OpenAI when no template matches |

### MA-6: Cost Governance
| # | Decision | Locked Value |
|---|---|---|
| L-150 | Circuit breaker | 3-state: CLOSED → OPEN → HALF_OPEN, trips at 150% |
| L-151 | Cost tracking | Per-agent via `AgentLedger` |
| L-152 | Governor interface | `CostGovernor` with `.breaker` and `.ledger` attributes |

### MA-7: Interaction Modes
| # | Decision | Locked Value |
|---|---|---|
| L-160 | Mode set | brainstorm (LLM), critique, debate, synthesis (LLM), reflection |
| L-161 | Session interface | `InteractionEngine.start_session(mode, topic, participants)` returns `(SessionResult, errors)` |
| L-162 | Chaining | 4 pipelines available |

### MA-8: Behavior Rules
| # | Decision | Locked Value |
|---|---|---|
| L-170 | Rule count | 12 rules across 7 categories |
| L-171 | Enforcement | Graduated: warn 3x then block |
| L-172 | Auto-escalation | `AUTO_ESCALATE_THRESHOLD = 5` |
| L-173 | Check interface | `BehaviorGuard.check(agent_id, action_type, context)` returns result dict |

### MA-9: Failure Recovery
| # | Decision | Locked Value |
|---|---|---|
| L-180 | Failure categories | 6: resource, agent, logic, system, transient, external |
| L-181 | Escalation thresholds | resource=1, agent=2, logic=3, system=3, transient=5 |
| L-182 | Blast radius ordering | Cascading check runs BEFORE escalation threshold |
| L-183 | None key handling | `_make_key` uses `or "none"` not `.get(key, "none")` |

### MA-10: Conflict Resolution
| # | Decision | Locked Value |
|---|---|---|
| L-190 | Conflict types | 6 types |
| L-191 | Resolution strategies | 6 strategies + auto-select |
| L-192 | Resolve interface | `ConflictResolver.resolve(conflict, strategy, votes, force)` |
| L-193 | Minor conflict handling | Auto-resolve with audit logging |
| L-194 | Batch ordering | Critical-first |

### MA-11: Peer Review
| # | Decision | Locked Value |
|---|---|---|
| L-200 | Check ordering | Self-review check BEFORE assignment check in `submit_review` |
| L-201 | Import pattern | `sys.path.insert(0, str(REPO / "scripts"))` then `from conflict_resolution import` |
| L-202 | Reviewer scoring | domain(+3), capability(+2), authority(+1), accuracy(+1), workload(-1) |

### MA-12: Agent Performance
| # | Decision | Locked Value |
|---|---|---|
| L-210 | Dimensions | 5 performance dimensions |
| L-211 | Weight profiles | 7 role-specific + 5 org goal profiles |
| L-212 | Sample threshold | `MIN_SAMPLE_THRESHOLD = 3` |
| L-213 | Recovery credit | Failed-but-recovered = 0.5 |
| L-214 | Decision accuracy | 70% outcome + 30% confidence accuracy |

### MA-13: Learning Loop
| # | Decision | Locked Value |
|---|---|---|
| L-220 | Store return | `store.add()` returns `(lesson_id, is_new, actual_occurrences)` |
| L-221 | Priority ordering | Critical priority checked BEFORE `auto_apply` flag |
| L-222 | Source weights | MA-9(5) > MA-4(4) > MA-12(3) > MA-11(2) > MA-8(2) > MA-10(1) |
| L-223 | Learning decay | 90-day half-life, expire at 0.1 |

### MA-14: System Health
| # | Decision | Locked Value |
|---|---|---|
| L-230 | Health domains | 11 domains, weights sum to 1.0 |
| L-231 | Alert trigger | 3+ degraded domains → system-wide alert |
| L-232 | Export format | JSON (ready for web dashboard) |

### MA-15: Output Quality Gate
| # | Decision | Locked Value |
|---|---|---|
| L-240 | Enforcement | Mandatory for all outputs, block on failure |
| L-241 | Min lengths | research=500, product_spec=800 |
| L-242 | Revision cap | Max 3 revisions then escalate |

### MA-16: Human-in-the-Loop
| # | Decision | Locked Value |
|---|---|---|
| L-250 | Actions | 4: approve, reject, modify, defer |
| L-251 | Categories | 6 with configurable expiry (4h–72h) |
| L-252 | Expiry actions | Per-category: reject, defer, or escalate |

### MA-17: Context Window Management
| # | Decision | Locked Value |
|---|---|---|
| L-260 | Pool budgets | default=80K, research=160K, analysis=200K (10x multiplier) |
| L-261 | Overflow handling | Soft enforcement — only ephemeral items rejected |
| L-262 | Pruning | Priority-based (critical items never pruned) |

### MA-18: Internal Competition
| # | Decision | Locked Value |
|---|---|---|
| L-270 | Auto-trigger | Tasks above $5 + all critical priority |
| L-271 | Competitors | 2 default, 3 for critical |
| L-272 | Tiebreak | Score gap < 0.05 → faster generation wins |

### MA-19: Security & Access Control
| # | Decision | Locked Value |
|---|---|---|
| L-280 | Access domains | 6 domains |
| L-281 | Permission sets | 7 role-based |
| L-282 | Unauthorized handling | Block + auto-escalate |
| L-283 | Temporary grants | With expiry, authority level 1 only |

### MA-20: Integration Test
| # | Decision | Locked Value |
|---|---|---|
| L-290 | Test phases | 10 phases across all 19 MA systems |
| L-291 | Total checks | 37 |

## Workflow Locks

| # | Decision | Locked Value |
|---|---|---|
| L-300 | Build workflow | spec → review → approval → build → test → validate → commit → push |
| L-301 | Commit discipline | Atomic: docs + code + tests together |
| L-302 | Commit messages | Structured with test scores, key fixes, capability summaries |
| L-303 | Push timing | After every validated fix |
| L-304 | Output artifacts | Never committed to repo |
| L-305 | Spec approval | Required before any code written |
| L-306 | Required fixes | ❌ items applied before build begins |
| L-307 | Review format | Structured tables with ratings, not prose |

## Lock Modification Rules

1. No lock may be changed without explicit user approval
2. Lock changes must document: what changed, why, what it affects, rollback path
3. New MA systems or major subsystems get their own lock section upon completion
4. All locks reference the phase or tier when they were established
