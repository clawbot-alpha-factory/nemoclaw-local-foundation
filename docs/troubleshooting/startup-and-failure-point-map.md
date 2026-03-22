# Doc 14 — Startup and Failure Point Map

**Version:** v2 — Updated March 22 2026
**Phase:** Phase 2 Complete
**Target:** MacBook, Apple Silicon, Docker Desktop

---

## Startup Sequence

A healthy NemoClaw startup follows this exact order.

| Step | Requirement | Check Command |
|---|---|---|
| 1 | Docker Desktop running | docker info --format ServerVersion |
| 2 | openshell in PATH | which openshell |
| 3 | NemoClaw gateway healthy | nemoclaw nemoclaw-assistant status |
| 4 | Sandbox ready | openshell sandbox list |
| 5 | Inference provider active | openshell inference get |
| 6 | Routing confirmed | nemoclaw nemoclaw-assistant logs --follow |

---

## Quick Diagnostic Runbook

Run this first when something breaks:

    docker info --format ServerVersion && which openshell && nemoclaw nemoclaw-assistant status && openshell inference get

| If you see | Go to |
|---|---|
| docker socket error | Failure Point 1 |
| openshell not found | Failure Point 2 |
| gateway not reachable | Failure Point 3 |
| sandbox stopped | Failure Point 4 |
| Python 3.9.6 | Failure Point 5 |
| 403 inference error | Failure Point 6 |
| 400 protocol mismatch | Failure Point 7 |
| Wrong model in TUI | Failure Point 8 |
| stale routes warning | Failure Point 9 |
| nvcr.io auth error | Failure Point 10 |
| model display wrong after restart | Maintenance Step 1 |

---

## Failure Point 1 — Docker Desktop Not Running

**Symptom:** failed to connect to the docker API at unix:///Users/core88/.docker/run/docker.sock

**Cause:** Docker Desktop not running. Does not auto-start at login.

**Fix:** open -a Docker — wait 60 seconds then retry.

---

## Failure Point 2 — openshell Not Found

**Symptom:** bash: openshell: command not found

**Cause:** New terminal session opened without sourcing ~/.zshrc.

**Fix:** source ~/.zshrc

---

## Failure Point 3 — NemoClaw Gateway Not Reachable

**Symptom:** gateway not reachable / connection refused at https://127.0.0.1:8080

**Cause:** OpenShell gateway container not running.

**Fix:** nemoclaw start — wait 30 seconds then check: nemoclaw nemoclaw-assistant status

---

## Failure Point 4 — Sandbox Not Running

**Symptom:** sandbox nemoclaw-assistant not found / sandbox stopped

**Fix:** openshell sandbox list — then: nemoclaw nemoclaw-assistant connect
If missing entirely: nemoclaw onboard

---

## Failure Point 5 — Python Reverts to 3.9.6

**Symptom:** python3 --version shows Python 3.9.6

**Cause:** New terminal without sourcing ~/.zshrc.

**Fix:** source ~/.zshrc && python3 --version — expected: Python 3.14.3

---

## Failure Point 6 — Inference 403 Error

**Symptom:** run error: 403 status code (no body)

**Cause:** OpenShell network policy blocking inference request.

**Fix:** openshell inference get — confirm provider is openai.
If not: openshell inference set --provider openai --model gpt-4o-mini

---

## Failure Point 7 — Inference 400 Protocol Mismatch

**Symptom:** run error: 400 "no compatible route for source protocol openai_chat_completions"

**Cause:** Known alpha limitation. OpenShell 0.0.13 has no openai to anthropic protocol translation.

**Status:** Documented. Phase 4 migration path defined. Use OpenAI path as default.

---

## Failure Point 8 — Agent Shows Wrong Model Identity

**Symptom:** TUI shows inference/nvidia/nemotron-3-super-120b-a12b despite model switch.

**Cause:** openclaw.json owned by root inside sandbox. Resets on pod recreation.

**Status:** Cosmetic only. Routing confirmed correct via logs. See Maintenance Step 1 below.

---

## Failure Point 9 — Sandbox Inference Cache Stale

**Symptom:** Failed to refresh inference route cache — configured provider not found

**Cause:** Sandbox holds stale reference to a deleted provider. Cache refreshes every 5 seconds.

**Fix:** openshell inference get — confirm correct provider. Cache clears within 30 seconds.

---

## Failure Point 10 — NGC Authentication Failed

**Symptom:** unauthorized: authentication required / error pulling image from nvcr.io

**Fix:** grep NGC_API_KEY ~/nemoclaw-local-foundation/config/.env | cut -d= -f2 | docker login nvcr.io --username $oauthtoken --password-stdin

---

## Known Maintenance Step 1 — openclaw.json Ownership Reset

### Issue

After every sandbox restart or pod recreation, OpenShell resets /sandbox/.openclaw/openclaw.json to root ownership with read-only permissions. This prevents OpenClaw from writing model defaults, causing the agent to display the wrong model identity in the TUI.

### Why It Happens

OpenShell manages the sandbox as a Kubernetes pod inside the Docker Desktop cluster. When the pod is recreated, the file is restored from the container image with root ownership. The sandbox user cannot write to root-owned files.

### When This Must Be Reapplied

Reapply this fix after:
- Any sandbox restart
- Any Mac restart that causes the sandbox pod to recreate
- Any nemoclaw onboard run that recreates the sandbox
- Any OpenShell or NemoClaw upgrade

### Exact Fix

Step 1 — Get the cluster container ID:

    docker ps --format "table {{.Names}}\t{{.ID}}" | grep openshell-cluster

Note the container ID.

Step 2 — Fix ownership via kubectl as root (replace CONTAINER_ID):

    docker exec -it CONTAINER_ID kubectl exec -n openshell nemoclaw-assistant -- chmod 644 /sandbox/.openclaw/openclaw.json
    docker exec -it CONTAINER_ID kubectl exec -n openshell nemoclaw-assistant -- chown sandbox:sandbox /sandbox/.openclaw/openclaw.json

Step 3 — Verify:

    docker exec -it CONTAINER_ID kubectl exec -n openshell nemoclaw-assistant -- ls -la /sandbox/.openclaw/openclaw.json

Expected: -rw-r--r-- 1 sandbox sandbox

Step 4 — Set default model inside sandbox:

    nemoclaw nemoclaw-assistant connect
    openclaw models set inference/openai/gpt-4o-mini
    exit

### Convenience Script

Run scripts/fix-sandbox-permissions.sh — located in the repo scripts directory.

### Status

Known limitation of OpenShell 0.0.13. Should be fixed upstream when OpenShell supports persistent sandbox user file ownership.
