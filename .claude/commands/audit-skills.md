Audit all 30 built skills and 15 registered skills for production readiness. Read each skill before scoring it.

## 1. Built Skills Inventory
Scan every directory under `skills/`. For each skill directory found:

### Per-Skill Checks
- **File completeness**: has `skill.yaml`, `run.py`, `test-input.json`, `outputs/`, `README.md`
- **Schema validity**: `schema_version: 2`, `runner_version_required: ">=4.0.0"`, `step_type` values only `local`/`llm`/`critic`
- **Input validation**: each input has `type`, `required`, and `validation` (min/max lengths or allowed_values)
- **Model alias compliance**: no hardcoded model names (must use routing aliases like `cheap_openai`, `reasoning_claude`) — L-003
- **Critic loop**: skills of type `executor` or `transformer` should have `critic_loop.enabled: true`
- **Contracts**: has `machine_validated` block with `min_length`, `min_quality_score`
- **Output envelope**: step definitions include an output key for chaining

## 2. Registered Skills (K40-K54)
Read `docs/skill-catalog-k40-k49.yaml` and `docs/skill-catalog-k50-k54.yaml`. For each registered skill:
- Does a corresponding directory exist under `skills/`?
- Is there an assigned agent in `config/agents/capability-registry.yaml`?
- Flag any that are registered but not yet built

## 3. Revenue-Critical Skill Gap Analysis
Evaluate coverage for the following skill categories essential to an autonomous revenue-generating company. Rate each as: ✅ Built | ⚠️ Partial | ❌ Missing

| Category | Skills Needed | Status |
|---|---|---|
| Payment processing | checkout, subscription mgmt, refund handling | ? |
| Lead generation | B2B prospecting, ICP scoring, list building | ? |
| Cold outreach | email sequences, LinkedIn DMs, follow-up | ? |
| Proposal generation | scoping, pricing, SOW writing | ? |
| Invoice generation | itemized invoices, PDF export, payment links | ? |
| Social media automation | post scheduling, engagement, analytics | ? |
| Content repurposing | video → clips, blog → tweets, etc. | ? |
| SEO content | keyword research, article writing, optimization | ? |
| Sales qualification | BANT scoring, discovery call prep | ? |
| Contract generation | NDA, MSA, SLA templates | ? |
| Client reporting | weekly/monthly automated reports | ? |
| Competitive intelligence | ongoing monitoring, alerts | ? |

## 4. Skill Family Production-Readiness Ratings
For each family, assign a readiness tier:
- **Tier 1** (Production-ready): complete files, valid schema, critic loop, tested
- **Tier 2** (Needs polish): functional but missing README, weak validation, or no critic loop
- **Tier 3** (Skeleton only): has skill.yaml but run.py is stub or missing steps
- **Tier 4** (Not started): registered but no directory

| Family | Skills Count | Readiness | Blockers |
|---|---|---|---|
| A01 Architecture | 3 | ? | ? |
| B05 Implementation | 4 | ? | ? |
| B06 DevOps | 2 | ? | ? |
| C07 Documentation | 4 | ? | ? |
| D11 Content | 2 | ? | ? |
| E08 Intelligence | 3 | ? | ? |
| E12 Research | 2 | ? | ? |
| F09 Product/Pricing | 2 | ? | ? |
| G25 Utilities | 2 | ? | ? |
| G26 Meta/Factory | 2 | ? | ? |
| I35 Transformation | 1 | ? | ? |
| J36 Business | 2 | ? | ? |
| K40-K54 Registered | 15 | ? | ? |
| biz/cnt/rev/out/scl | varies | ? | ? |

## 5. Final Report
```
=== SKILL AUDIT REPORT ===

BUILT SKILLS SCANNED: N
  - Schema valid: N
  - File-complete: N
  - Critic loop enabled: N
  - L-003 compliant (no hardcoded models): N

REGISTERED SKILLS: 15
  - Built and deployed: N
  - Not yet built: N (list them)

REVENUE-CRITICAL GAPS:
  ❌ Missing: <list skill categories>
  ⚠️ Partial: <list skill categories>

TOP PRIORITY SKILLS TO BUILD NEXT:
  1. <skill-id>: <reason> — estimated LLM cost per run: $X
  2. ...

FAMILIES AT TIER 1 (production-ready): [list]
FAMILIES AT TIER 3-4 (needs work): [list]
```
