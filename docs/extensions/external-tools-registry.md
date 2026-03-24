# External Tools Registry

**Phase:** 10.5 — External Tool Integrations
**Status:** PENDING — tools list to be provided
**Approach:** Hybrid — API keys stored and validated now, active integration built per tool in Phase 12 alongside Skills

---

## Purpose

This file is the single source of truth for all external tool integrations in the NemoClaw system.

For each tool it defines:
- tool name and category
- API key environment variable name
- key source URL
- integration status (key only / active)
- planned integration phase

---

## Tools

To be populated when tools list is provided.

---

## Key Storage Convention

All tool API keys follow the same pattern as provider keys:
- stored in config/.env
- variable name: TOOLNAME_API_KEY
- never committed to repo
- validated by validate.py

