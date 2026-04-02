---
name: skill-builder
description: Generate new NemoClaw skills from template, wire routing, create test inputs. Use when creating or adding new skills.
tools: Read, Grep, Glob, Bash, Edit, Write
model: opus
---

Create a new NemoClaw skill using the template system.

## Process

1. Determine skill parameters from user request:
   - id (e.g., h35-tone-calibrator)
   - name (e.g., "Tone Calibrator")
   - family number, domain letter, tag
   - skill-type (executor|planner|evaluator|transformer|router)
   - step names and which are LLM/critic steps

2. Run: `python3 scripts/new-skill.py --id <id> --name "<name>" --family <N> --domain <D> --tag <tag> --skill-type <type> --step-names "<steps>" --llm-steps "<N>" --critic-steps "<N>"`

3. Customize the generated skill.yaml with proper prompts and contracts

4. Customize run.py with domain-specific logic

5. Create meaningful test-input.json

6. Verify: `python3 scripts/test-all.py --skill <id>`

7. Verify L-003: `grep -n 'call_llm\|from lib.routing' skills/<id>/run.py`

## Conventions

- Schema v2 only
- All LLM calls via lib/routing.py call_llm (L-003)
- Step names must be semantic (3+ words)
- Include critic loop for quality-gated skills
- Family numbers zero-padded, domains single letters A-L
