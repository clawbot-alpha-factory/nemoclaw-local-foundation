---
name: run-skill
description: Execute a NemoClaw skill by ID with optional inputs. Use when asked to run, test, or execute a specific skill.
argument-hint: "<skill-id> [--input key value]"
allowed-tools: Bash, Read
---

Execute: `python3 skills/skill-runner.py --skill $0`

If additional arguments provided, pass them through.
If no arguments, ask which skill to run.

Report the output artifact and any errors.
