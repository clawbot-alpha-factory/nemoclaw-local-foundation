---
name: deep-research
description: Thoroughly explore a topic across the codebase. Use when asked to research, investigate, find, or understand something complex.
argument-hint: "<topic or question>"
context: fork
agent: Explore
---

Research the following thoroughly across the entire NemoClaw codebase:

$ARGUMENTS

Search strategy:
1. Grep for relevant keywords across all file types
2. Glob for related files by name patterns
3. Read key files found
4. Cross-reference with config/ and docs/

Return: specific file paths, line numbers, and a clear summary of findings.
