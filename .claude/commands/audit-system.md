Run a full system audit across all layers of NemoClaw Local Foundation. Work through each section below in order, collecting results, then print a final summary table.

## 1. Validation Suite
Run `python3 scripts/validate.py` and capture the pass/warn/fail counts and any failed check names.

## 2. Integration Test
Run `python3 scripts/integration_test.py --summary` and capture the overall result. If it fails, also run `--test` to get detailed output.

## 3. API Endpoint Health
Start the Command Center backend if not running, then check all major endpoint groups:
- `GET /api/state` — SystemState
- `GET /api/state/skills`, `/agents`, `/budget`, `/health`, `/validation`
- `GET /api/brain/status`
- `GET /api/comms/lanes`

For each, report HTTP status code and whether the response schema matches expectations.

## 4. Code Quality Scan
Search the entire codebase (excluding `.venv313/`, `node_modules/`, `.next/`, `.cc2-backup-*/`) for:
- `TODO` comments — list file:line and content
- `FIXME` comments — list file:line and content
- `HACK` comments — list file:line and content
- `hardcoded` model names (e.g. `gpt-4`, `claude-3`, `gemini`) outside of `config/routing/` — flag as L-003 violations

## 5. Import Resolution
For each Python file in `scripts/` and `command-center/backend/app/`, verify all `import` and `from ... import` statements resolve within the project or are standard library / installed packages. Flag any `ModuleNotFoundError`-prone imports.

## 6. Config YAML Validity
Parse and validate the following YAML files, reporting any syntax errors or missing required keys:
- `config/routing/routing-config.yaml` — must have `providers` and `routing` keys
- `config/routing/budget-config.yaml` — must have per-provider `total_usd` fields
- `config/agents/agent-schema.yaml` — must have `agents` list with `id`, `role`, `authority_level`
- `config/agents/capability-registry.yaml` — must have `capabilities` with `agent` assignments
- `config/pinchtab-config.yaml` — must have `pinchtab.server_url`

## 7. Skill Completeness Check
Scan every directory under `skills/` and verify each has:
- `skill.yaml` (required — flag missing)
- `run.py` (required — flag missing)
- `test-input.json` (required — flag missing)
- `outputs/` directory (warn if missing)
- `README.md` (warn if missing)

Also verify each `skill.yaml` uses `schema_version: 2` and `step_type` values are only `local`, `llm`, or `critic`.

## 8. Final Summary Report
Print a structured summary:

```
=== NEMOCLAW SYSTEM AUDIT ===
Date: <timestamp>

VALIDATION SUITE     [ PASS/WARN/FAIL counts ]
INTEGRATION TEST     [ PASS / FAIL ]
API ENDPOINTS        [ X/Y healthy ]
TODO/FIXME/HACK      [ N items found ]
IMPORT ISSUES        [ N issues found ]
CONFIG YAML          [ X/Y files valid ]
SKILL COMPLETENESS   [ X/Y skills complete, N missing required files ]

CRITICAL ISSUES:
  - <list any P0 blockers>

WARNINGS:
  - <list non-blocking issues>

RECOMMENDATIONS:
  - <top 3-5 actionable improvements>
```
