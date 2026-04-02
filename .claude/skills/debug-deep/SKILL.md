---
name: debug-deep
description: Deep diagnostic pass — import errors, syntax, dead code, routing consistency, hardcoded paths, frontend/backend mismatches. Use when debugging the full codebase.
context: fork
model: sonnet
allowed-tools: Bash, Read, Grep, Glob
---

Perform a deep diagnostic pass across the entire codebase. Investigate each category below, read the relevant files, and report every finding with file:line references.

## 1. Python Import Errors
For every `.py` file in `scripts/` and `command-center/backend/app/`:
- Flag imports referencing modules not in requirements.txt, stdlib, or repo
- Flag circular imports
- Flag relative imports pointing to non-existent files

## 2. Syntax Errors
Run syntax check on every `.py` file (excluding `.venv313/`).

## 3. Dead Code
Identify: unused functions in scripts/, skill YAML steps not in transitions, unused config keys, outputs never written.

## 4. Routing Config vs. Code Consistency
Check for: alias names in code not in config, hardcoded providers (L-003), budget enforcer mismatches, direct API key access in skills.

## 5. Hardcoded Paths
Search for `/Users/` paths, `/home/` paths, `.venv312/` references (old venv).

## 6. Backend Routes vs. Frontend API Calls
Cross-reference backend routes with frontend fetch calls. Flag broken calls, dead routes, and shape mismatches.

## 7. Skill YAML Cross-References
Verify: transitions reference valid step IDs, critic_loop references valid steps, final_output.candidates are written by steps.

## 8. Config Inter-File Consistency
Verify: all agent IDs have capability entries, all capabilities reference valid agents, all skills in registry have directories, PinchTab profiles match agents.

## 9. Final Bug Report
Print structured report with: critical bugs, warnings, dead code, recommendations.
