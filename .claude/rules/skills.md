---
paths:
  - "skills/**"
---

## NemoClaw Skill Conventions
- Schema v2 ONLY: step_type must be local, llm, or critic (never makes_llm_call)
- All LLM calls through lib/routing.py call_llm — NEVER hardcode models (L-003)
- test-input.json required: {"inputs": {...}} format
- Critic loops need: threshold + improve step + re-evaluate transition
- Step names must be semantic (3+ words, no "TODO" or "processing step")
- Skill IDs: <family>-<name> pattern (e.g., a01-arch-spec-writer)
- Family numbers zero-padded (F01-F99), domains single letters A-L
- Delete checkpoint DB between test runs to prevent stale cache
- Quality minimum: 10/10 across all skills
