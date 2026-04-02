---
name: audit-infrastructure
description: Full infrastructure audit — state/persistence, caching, CI/CD, containerization, secrets, monitoring gaps. Use when auditing infrastructure readiness.
context: fork
model: sonnet
allowed-tools: Bash, Read, Grep, Glob
---

Perform a full infrastructure audit for a production autonomous AI company.

## 1. Read Existing Infrastructure
- `command-center/backend/requirements.txt`
- `command-center/frontend/package.json`
- `config/routing/routing-config.yaml` and `budget-config.yaml`
- Check for: `Dockerfile`, `docker-compose.yaml`, `Makefile`, `.github/workflows/`, `pyproject.toml`
- Check `~/.nemoclaw/` directory structure

## 2. Infrastructure Gap Audit
Assess: state/persistence, vector DB, embedding pipeline, document store, message queue, caching, secrets management, logging, error tracking, metrics, CI/CD, containerization, auto-scaling, webhooks, payments, email, scheduler, file storage, relational DB, rate limiting.

Rate each: critical / high / medium / low impact.

## 3. Project Skeleton Audit
Check for missing: `__init__.py`, root `requirements.txt`/`pyproject.toml`, Dockerfiles, docker-compose, Makefile, GitHub workflows, CHANGELOG.

## 4. Implement Top 5 Critical Missing Pieces
Rank all gaps by (impact x urgency). Implement top 5 that can be done locally (no cloud accounts).

## 5. Final Infrastructure Report
Print structured summary with critical/high/medium gaps, skeleton files missing, and implementations completed.
