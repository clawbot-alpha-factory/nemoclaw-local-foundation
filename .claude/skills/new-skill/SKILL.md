---
name: new-skill
description: Create a new NemoClaw skill from template with proper routing and tests. Use when asked to create, generate, or add a new skill.
argument-hint: "<skill-id> <skill-name>"
allowed-tools: Bash, Read, Write, Edit
context: fork
agent: skill-builder
---

Create a new skill. User wants: $ARGUMENTS

Follow the skill-builder agent's process to generate, customize, and verify the skill.
