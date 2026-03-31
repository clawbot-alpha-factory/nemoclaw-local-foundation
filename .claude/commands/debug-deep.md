Perform a deep diagnostic pass across the entire codebase. Investigate each category below, read the relevant files, and report every finding with file:line references.

## 1. Python Import Errors
For every `.py` file in `scripts/` and `command-center/backend/app/`:
- Check all `import` and `from ... import` statements
- Flag any import that references a module not in `requirements.txt`, not in stdlib, and not present in the repo
- Flag circular imports (A imports B, B imports A)
- Flag relative imports that point to non-existent files

## 2. Syntax Errors
Run a syntax check on every `.py` file in the repo (excluding `.venv313/`):
```bash
python3 -m py_compile <file>
```
Report any file that fails with its error message.

## 3. Dead Code
Identify:
- Functions defined in `scripts/` that are never called anywhere in the repo
- Skill YAML steps that are defined but never referenced in `transitions`
- Config keys in `routing-config.yaml` or `budget-config.yaml` that no code reads
- `outputs/` entries in `skill.yaml` that are never written by any step

## 4. Routing Config vs. Code Consistency
Read `config/routing/routing-config.yaml` and then search all Python code for:
- Alias names used in code that don't exist in the config (e.g. `task_class` values)
- Provider names hardcoded in code that bypass the routing system (L-003 violations)
- Budget enforcer calls that reference a provider not in `budget-config.yaml`
- Any `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY` accessed directly in skills (must go through routing)

## 5. Hardcoded Paths
Search for hardcoded absolute paths outside of config files:
- Any `/Users/` paths in Python files
- Any `/home/` paths
- Paths that should use `os.path.expanduser("~/.nemoclaw/...")` but don't
- Any paths that reference `.venv312/` (old venv — should be `.venv313/`)

## 6. Backend Routes vs. Frontend API Calls
Read `command-center/backend/app/main.py` and all router files in `command-center/backend/app/api/routers/`.
Read all `command-center/frontend/src/lib/api.ts` and any `fetch()`/`axios` calls in frontend components.

Cross-reference:
- Frontend calls a route that doesn't exist in the backend → **broken call**
- Backend route exists but frontend never calls it → **dead route** (warn only)
- Request/response shape mismatches (e.g. frontend expects `{ skills: [] }` but backend returns `{ data: [] }`)

## 7. Skill YAML Cross-References
For each `skill.yaml` in `skills/`:
- `transitions` reference step IDs — verify all referenced step IDs exist in the `steps` list
- `critic_loop.generator_step`, `critic_step`, `improve_step` — verify all reference valid step IDs
- `final_output.candidates` — verify referenced output keys are written by at least one step
- `inputs_from_memory` keys — verify they match keys written by an upstream skill in any workflow YAML

## 8. Config Inter-File Consistency
- Every agent `id` in `agent-schema.yaml` must have an entry in `capability-registry.yaml`
- Every `capability` in `capability-registry.yaml` must reference a valid `agent` id
- Every skill referenced in `capability-registry.yaml` must have a directory under `skills/`
- PinchTab profiles in `pinchtab-config.yaml` must match agent ids in `agent-schema.yaml`

## 9. Final Bug Report
```
=== DEEP DEBUG REPORT ===

CRITICAL BUGS (will cause runtime failures):
  [C1] <file>:<line> — <description>
  ...

WARNINGS (degraded behavior, not crashes):
  [W1] <file>:<line> — <description>
  ...

DEAD CODE / CLEANUP:
  [D1] <file>:<function> — never called
  ...

RECOMMENDATIONS:
  1. Fix <C1> first because <reason>
  2. ...
```
