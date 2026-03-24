#!/usr/bin/env python3
"""
NemoClaw External Tools Framework v1.0.0
Phase 10.5 — External Tool Integrations

Standard integration framework for all external tools.
Every tool integration in Phase 12 must use this pattern.

Provides:
- credential loading from config/.env
- connection validation per tool
- audit logging for all tool calls
- standard error handling
- tool registry status report
"""

import json
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone

BASE_DIR   = os.path.expanduser("~/nemoclaw-local-foundation")
ENV_FILE   = os.path.join(BASE_DIR, "config/.env")
TOOLS_LOG  = os.path.expanduser("~/.nemoclaw/logs/tools-audit.log")

# ── Tool Registry ─────────────────────────────────────────────────────────────
# Each tool defines: env_var, phase, validation_fn or None
TOOL_REGISTRY = {
    "github":        {"env_var": None,                      "phase": "now",  "note": "active — no separate key needed"},
    "asana":         {"env_var": "ASANA_ACCESS_TOKEN",      "phase": "10.5", "note": "key validation + API"},
    "supabase":      {"env_var": "SUPABASE_URL",            "phase": "12",   "note": "placeholder — activate Phase 12"},
    "vercel":        {"env_var": "VERCEL_TOKEN",            "phase": "12",   "note": "placeholder — activate Phase 12"},
    "lemonsqueezy":  {"env_var": "LEMONSQUEEZY_API_KEY",    "phase": "12",   "note": "placeholder — activate Phase 12"},
    "apollo":        {"env_var": "APOLLO_API_KEY",          "phase": "12",   "note": "placeholder — activate Phase 12"},
    "instantly":     {"env_var": "INSTANTLY_API_KEY",       "phase": "12",   "note": "placeholder — activate Phase 12"},
    "resend":        {"env_var": "RESEND_API_KEY",          "phase": "12",   "note": "placeholder — activate Phase 12"},
    "payoneer":      {"env_var": "PAYONEER_API_KEY",        "phase": "12",   "note": "placeholder — activate Phase 12"},
    "opusclip":      {"env_var": "OPUSCLIP_API_KEY",        "phase": "12",   "note": "placeholder — activate Phase 12"},
    "apify":         {"env_var": "APIFY_TOKEN",             "phase": "12",   "note": "placeholder — activate Phase 12"},
    "n8n":           {"env_var": None,                      "phase": "12",   "note": "self-hosted — no key needed"},
    "cliq":          {"env_var": None,                      "phase": "when", "note": "bank-level — no API"},
    "cursor":        {"env_var": None,                      "phase": "12",   "note": "uses existing OpenAI/Anthropic keys"},
    "lovable":       {"env_var": None,                      "phase": "12",   "note": "web-based — no backend API key"},
    "capcut":        {"env_var": None,                      "phase": "12",   "note": "no programmatic API"},
}


# ── Env Loader ────────────────────────────────────────────────────────────────
def load_env():
    env = {}
    if not os.path.exists(ENV_FILE):
        return env
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


# ── Audit Logger ──────────────────────────────────────────────────────────────
def write_tools_log(tool, action, status, detail=""):
    os.makedirs(os.path.dirname(TOOLS_LOG), exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()
    entry = json.dumps({
        "timestamp": ts,
        "tool": tool,
        "action": action,
        "status": status,
        "detail": detail
    })
    with open(TOOLS_LOG, "a") as f:
        f.write(entry + "\n")


# ── Standard Tool Wrapper ─────────────────────────────────────────────────────
class ToolWrapper:
    """
    Base class for all tool integrations in Phase 12.
    Every tool integration must subclass this and implement:
    - validate_connection()
    - call(action, **kwargs)
    """

    def __init__(self, tool_name):
        self.tool_name = tool_name
        self.env = load_env()
        info = TOOL_REGISTRY.get(tool_name, {})
        self.env_var = info.get("env_var")
        self.phase = info.get("phase", "unknown")

    def get_credential(self):
        if not self.env_var:
            return None
        return self.env.get(self.env_var, "")

    def validate_connection(self):
        raise NotImplementedError(f"{self.tool_name}: validate_connection() not implemented")

    def call(self, action, **kwargs):
        write_tools_log(self.tool_name, action, "called", str(kwargs)[:200])
        raise NotImplementedError(f"{self.tool_name}: call() not implemented — build in Phase 12")


# ── Asana Integration ─────────────────────────────────────────────────────────
class AsanaTool(ToolWrapper):
    """
    Asana integration — Phase 10.5
    Key validated. Full integration built in Phase 12.
    """

    BASE_URL = "https://app.asana.com/api/1.0"

    def __init__(self):
        super().__init__("asana")

    def _request(self, path):
        token = self.get_credential()
        if not token:
            raise ValueError("ASANA_ACCESS_TOKEN not found in config/.env")
        req = urllib.request.Request(
            f"{self.BASE_URL}{path}",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())

    def validate_connection(self):
        try:
            data = self._request("/users/me")
            user = data["data"]
            name = user.get("name", "unknown")
            email = user.get("email", "unknown")
            write_tools_log("asana", "validate_connection", "success", f"user={name}")
            return True, f"{name} ({email})"
        except urllib.error.HTTPError as e:
            write_tools_log("asana", "validate_connection", "failed", f"HTTP {e.code}")
            return False, f"HTTP {e.code}"
        except Exception as e:
            write_tools_log("asana", "validate_connection", "failed", str(e))
            return False, str(e)

    def get_workspaces(self):
        """Get list of Asana workspaces. Phase 12 integration."""
        data = self._request("/workspaces")
        write_tools_log("asana", "get_workspaces", "success")
        return data.get("data", [])

    def call(self, action, **kwargs):
        write_tools_log(self.tool_name, action, "called", str(kwargs)[:200])
        if action == "get_workspaces":
            return self.get_workspaces()
        raise NotImplementedError(f"Asana action {action} not yet implemented — build in Phase 12")


# ── Tool Status Report ────────────────────────────────────────────────────────
def tool_status_report():
    env = load_env()
    print()
    print("=" * 65)
    print("  NemoClaw External Tools Status")
    print("=" * 65)

    phase_order = {"now": 0, "10.5": 1, "12": 2, "when": 3}

    for tool, info in sorted(TOOL_REGISTRY.items(),
                              key=lambda x: phase_order.get(x[1]["phase"], 99)):
        env_var = info["env_var"]
        phase   = info["phase"]
        note    = info["note"]

        if env_var is None:
            status = "⚪ no key needed"
        elif env_var in env and len(env[env_var]) > 10:
            status = "✅ key present"
        else:
            status = "⏳ placeholder"

        print(f"  {tool:<14} Phase {phase:<5} {status:<20} {note}")

    print("=" * 65)
    print()


# ── Validate All Active Tools ─────────────────────────────────────────────────
def validate_active_tools():
    """Validate connection for all tools with keys present. Returns (passed, failed)."""
    results = {"passed": [], "failed": []}

    # Asana — only active tool with key in Phase 10.5
    asana = AsanaTool()
    ok, detail = asana.validate_connection()
    if ok:
        results["passed"].append(f"asana: {detail}")
    else:
        results["failed"].append(f"asana: {detail}")

    return results


if __name__ == "__main__":
    tool_status_report()
    print("Validating active tool connections...")
    results = validate_active_tools()
    for r in results["passed"]:
        print(f"  ✅ {r}")
    for r in results["failed"]:
        print(f"  ❌ {r}")
    print()
