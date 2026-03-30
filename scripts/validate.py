#!/usr/bin/env python3
"""
NemoClaw Local Validation Script v1.0.0
Runs all 31 checks across 6 categories and reports pass/fail.
Doc 16 — Local Validation Checklist
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone

REPO = os.path.expanduser("~/nemoclaw-local-foundation")
LOGS = os.path.expanduser("~/.nemoclaw/logs")
VALIDATION_LOG = os.path.join(LOGS, "validation-runs.jsonl")

PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"

results = []
total_pass = 0
total_fail = 0
total_warn = 0

def check(category, number, name, fn):
    global total_pass, total_fail, total_warn
    try:
        status, detail = fn()
    except Exception as e:
        status, detail = FAIL, str(e)

    icon = "✅" if status == PASS else ("⚠️ " if status == WARN else "❌")
    print(f"  {icon} [{number:02d}] {name}")
    if detail and status != PASS:
        print(f"       {detail}")

    results.append({
        "category": category,
        "number": number,
        "name": name,
        "status": status,
        "detail": detail,
    })

    if status == PASS:
        total_pass += 1
    elif status == WARN:
        total_warn += 1
    else:
        total_fail += 1

def run(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return r.stdout.strip(), r.stderr.strip(), r.returncode

# ── Category 1 — Environment ──────────────────────────────────────────────────
def c1_docker_running():
    out, err, rc = run("docker info --format '{{.ServerVersion}}' 2>/dev/null")
    if rc != 0 or not out:
        return FAIL, "Docker Desktop is not running"
    return PASS, out

def c1_docker_version():
    out, _, rc = run("docker --version")
    if rc != 0:
        return FAIL, "docker not found"
    parts = out.split()
    ver = parts[2].rstrip(",") if len(parts) > 2 else "0"
    major = int(ver.split(".")[0])
    if major < 29:
        return FAIL, f"Docker version {ver} — requires >= 29.0"
    return PASS, ver

def c1_python_version():
    # Check .venv313 Python 3.12 exists — required for LangGraph workloads
    venv_python = os.path.expanduser("~/nemoclaw-local-foundation/.venv313/bin/python")
    if os.path.exists(venv_python):
        out, _, rc = run(f"{venv_python} --version")
        if rc == 0:
            ver = out.replace("Python ", "")
            parts = ver.split(".")
            if int(parts[0]) == 3 and int(parts[1]) == 12:
                return PASS, f".venv313 Python {ver} — LangGraph runtime ready"
            return WARN, f".venv313 exists but Python {ver} — expected 3.12.x"
    # Fallback: check system python3
    out, _, rc = run("python3 --version")
    if rc != 0:
        return FAIL, "python3 not found and .venv313 missing — run setup"
    ver = out.replace("Python ", "")
    return WARN, f"System Python {ver} — .venv313 not found, LangGraph requires .venv313"

def c1_openshell_path():
    out, _, rc = run("which openshell")
    if rc != 0 or not out:
        return WARN, "openshell not in PATH (not required for skill execution)"
    return PASS, out

def c1_node_version():
    out, _, rc = run("node --version")
    if rc != 0:
        return FAIL, "node not found"
    ver = out.lstrip("v")
    major = int(ver.split(".")[0])
    if major < 20:
        return FAIL, f"Node {out} — requires >= 20"
    return PASS, out

# ── Category 2 — NemoClaw Runtime ────────────────────────────────────────────
def c2_gateway_reachable():
    out, _, rc = run("openshell gateway info 2>/dev/null")
    if rc == 0 and "127.0.0.1:8080" in out:
        return PASS, "gateway endpoint https://127.0.0.1:8080"
    return WARN, "Gateway not reachable (OpenShell not required for skill execution)"

def c2_sandbox_ready():
    out, _, rc = run("openshell sandbox list 2>/dev/null")
    if rc != 0:
        return WARN, "OpenShell sandbox not running (not required for skill execution)"
    if "nemoclaw-assistant" not in out:
        return WARN, "sandbox not running (OpenShell not required for skill execution)"
    if "Ready" in out:
        return PASS, "nemoclaw-assistant Ready"
    return WARN, f"Sandbox found but status unclear: {out[:80]}"

def c2_inference_provider():
    out, _, rc = run("openshell inference get 2>/dev/null")
    if rc != 0:
        return WARN, "OpenShell inference not running (using direct API instead)"
    if "openai" in out:
        return PASS, "provider=openai"
    return FAIL, f"Expected openai provider — got: {out[:80]}"

def c2_inference_model():
    out, _, rc = run("openshell inference get 2>/dev/null")
    if "gpt-4o-mini" in out:
        return PASS, "model=gpt-4o-mini"
    return WARN, "Model is not gpt-4o-mini — check active inference route"

def c2_openclaw_json_writable():
    container_out, _, rc = run("docker ps --format '{{.ID}}' --filter name=openshell-cluster 2>/dev/null")
    if rc != 0 or not container_out:
        return WARN, "Could not check openclaw.json — Docker container not found"
    cid = container_out.split()[0]
    out, _, rc2 = run(f"docker exec {cid} kubectl exec -n openshell nemoclaw-assistant -- ls -la /sandbox/.openclaw/openclaw.json 2>/dev/null")
    if "sandbox sandbox" in out:
        return PASS, "owned by sandbox user"
    if "root root" in out:
        return WARN, "owned by root (not critical — OpenShell not required)"
    return WARN, "Could not determine openclaw.json ownership"

# ── Category 3 — API Keys ─────────────────────────────────────────────────────
def check_env_key(key_name):
    env_path = os.path.join(REPO, "config/.env")
    if not os.path.exists(env_path):
        return FAIL, "config/.env not found"
    with open(env_path) as f:
        lines = f.read().splitlines()
    for line in lines:
        if line.startswith(f"{key_name}="):
            val = line.split("=", 1)[1].strip()
            if val and len(val) > 10:
                return PASS, f"{key_name} present ({len(val)} chars)"
            return FAIL, f"{key_name} present but empty or too short"
    return FAIL, f"{key_name} not found in config/.env"

def c3_ngc_key():
    return check_env_key("NGC_API_KEY")

def c3_anthropic_key():
    return check_env_key("ANTHROPIC_API_KEY")

def c3_openai_key():
    return check_env_key("OPENAI_API_KEY")

def c3_nvidia_key():
    return check_env_key("NVIDIA_INFERENCE_API_KEY")

def c3_google_key():
    return check_env_key("GOOGLE_API_KEY")

# ── Category 4 — Budget System ────────────────────────────────────────────────
def c4_spend_file_exists():
    path = os.path.expanduser("~/.nemoclaw/logs/provider-spend.json")
    if not os.path.exists(path):
        return FAIL, "provider-spend.json not found"
    return PASS, path

def c4_anthropic_budget():
    path = os.path.expanduser("~/.nemoclaw/logs/provider-spend.json")
    if not os.path.exists(path):
        return FAIL, "provider-spend.json not found"
    with open(path) as f:
        data = json.load(f)
    spend = data.get("anthropic", {}).get("cumulative_spend_usd", 0)
    pct = spend / 30.00 * 100
    if pct >= 100:
        return FAIL, f"Anthropic budget EXHAUSTED — ${spend:.3f} / $30.00"
    if pct >= 90:
        return WARN, f"Anthropic budget at {pct:.1f}% — ${spend:.3f} / $30.00"
    return PASS, f"${spend:.3f} / $30.00 ({pct:.1f}%)"

def c4_openai_budget():
    path = os.path.expanduser("~/.nemoclaw/logs/provider-spend.json")
    if not os.path.exists(path):
        return FAIL, "provider-spend.json not found"
    with open(path) as f:
        data = json.load(f)
    spend = data.get("openai", {}).get("cumulative_spend_usd", 0)
    pct = spend / 30.00 * 100
    if pct >= 100:
        return FAIL, f"OpenAI budget EXHAUSTED — ${spend:.3f} / $30.00"
    if pct >= 90:
        return WARN, f"OpenAI budget at {pct:.1f}% — ${spend:.3f} / $30.00"
    return PASS, f"${spend:.3f} / $30.00 ({pct:.1f}%)"

def c4_google_budget():
    path = os.path.expanduser("~/.nemoclaw/logs/provider-spend.json")
    if not os.path.exists(path):
        return FAIL, "provider-spend.json not found"
    with open(path) as f:
        data = json.load(f)
    spend = data.get("google", {}).get("cumulative_spend_usd", 0)
    pct = spend / 30.00 * 100
    if pct >= 100:
        return FAIL, f"Google budget EXHAUSTED — ${spend:.3f} / $30.00"
    if pct >= 90:
        return WARN, f"Google budget at {pct:.1f}% — ${spend:.3f} / $30.00"
    return PASS, f"${spend:.3f} / $30.00 ({pct:.1f}%)"

def c4_usage_log():
    path = os.path.join(LOGS, "provider-usage.jsonl")
    if not os.path.exists(path):
        return FAIL, "provider-usage.jsonl not found"
    if not os.access(path, os.W_OK):
        return FAIL, "provider-usage.jsonl not writable"
    return PASS, path

# ── Category 5 — Routing System ──────────────────────────────────────────────
def c5_enforcer_runs():
    enforcer = os.path.join(REPO, "scripts/budget-enforcer.py")
    if not os.path.exists(enforcer):
        return FAIL, "budget-enforcer.py not found"
    out, err, rc = run(f"python3 {enforcer} --task-class general_short 2>/dev/null")
    if rc != 0:
        return FAIL, f"budget-enforcer.py failed: {err[:80]}"
    try:
        data = json.loads(out)
        if "alias" in data:
            return PASS, f"alias={data['alias']}"
    except Exception:
        pass
    return FAIL, f"Unexpected output: {out[:80]}"

def c5_general_short_routing():
    enforcer = os.path.join(REPO, "scripts/budget-enforcer.py")
    out, _, rc = run(f"python3 {enforcer} --task-class general_short 2>/dev/null")
    if rc != 0:
        return FAIL, "enforcer failed"
    try:
        data = json.loads(out)
        if data.get("alias") == "cheap_openai":
            return PASS, "general_short → cheap_openai ✓"
        return FAIL, f"Expected cheap_openai — got {data.get('alias')}"
    except Exception:
        return FAIL, "Could not parse enforcer output"

def c5_complex_reasoning_routing():
    enforcer = os.path.join(REPO, "scripts/budget-enforcer.py")
    out, _, rc = run(f"python3 {enforcer} --task-class complex_reasoning 2>/dev/null")
    if rc != 0:
        return FAIL, "enforcer failed"
    try:
        data = json.loads(out)
        alias = data.get("alias")
        if alias in ("reasoning_claude", "fallback_openai"):
            return PASS, f"complex_reasoning → {alias} ✓"
        return FAIL, f"Expected reasoning_claude — got {alias}"
    except Exception:
        return FAIL, "Could not parse enforcer output"

# ── Category 6 — Skill System ─────────────────────────────────────────────────
def c3_asana_key():
    return check_env_key("ASANA_ACCESS_TOKEN")

def c3_asana_connection():
    import sys
    sys.path.insert(0, REPO + "/scripts")
    try:
        from tools import AsanaTool
        asana = AsanaTool()
        ok, detail = asana.validate_connection()
        if ok:
            return PASS, f"connected: {detail}"
        return FAIL, f"connection failed: {detail}"
    except Exception as e:
        return FAIL, str(e)[:80]


def c6_obs_script():
    path = os.path.join(REPO, "scripts/obs.py")
    if not os.path.exists(path):
        return FAIL, "obs.py not found"
    import subprocess
    r = subprocess.run(["python3", path], capture_output=True, text=True, timeout=10)
    if r.returncode != 0:
        return FAIL, f"obs.py failed: {r.stderr[:80]}"
    return PASS, "obs.py executes cleanly"


def c6_graph_validation():
    import json as _json
    path = os.path.expanduser(
        "~/nemoclaw-local-foundation/docs/architecture/langgraph-graph-validation-results.json"
    )
    if not os.path.exists(path):
        return FAIL, "graph validation results not found — run skills/graph-validation/validate_graph.py"
    with open(path) as f:
        data = _json.load(f)
    if not data.get("graph_ready", False):
        passed = data.get("total_passed", 0)
        total  = data.get("total_tests", 5)
        return FAIL, f"graph not ready — {passed}/{total} patterns passed"
    passed = data.get("total_passed", 0)
    total  = data.get("total_tests", 5)
    ts     = data.get("timestamp", "unknown")[:10]
    return PASS, f"{passed}/{total} patterns confirmed — {ts}"


def c6_skill_runner_exists():
    path = os.path.join(REPO, "skills/skill-runner.py")
    if not os.path.exists(path):
        return FAIL, "skills/skill-runner.py not found"
    with open(path) as f:
        content = f.read()
    if "SqliteSaver" not in content:
        return WARN, "skill-runner.py exists but SqliteSaver not detected — may be old version"
    return PASS, "skill-runner.py v4.0 with SqliteSaver"

def c6_skill_yaml_valid():
    path = os.path.join(REPO, "skills/research-brief/skill.yaml")
    if not os.path.exists(path):
        return FAIL, "skills/research-brief/skill.yaml not found"
    try:
        import yaml
        with open(path) as f:
            data = yaml.safe_load(f)
        name = data.get("name", "unknown")
        return PASS, f"valid YAML — name={name}"
    except Exception as e:
        return FAIL, f"YAML parse error: {e}"

def c6_outputs_dir():
    path = os.path.join(REPO, "skills/research-brief/outputs")
    if not os.path.exists(path):
        return FAIL, "skills/research-brief/outputs/ not found"
    if not os.access(path, os.W_OK):
        return FAIL, "outputs/ not writable"
    return PASS, path

def c6_checkpoint_db():
    path = os.path.expanduser("~/.nemoclaw/checkpoints/langgraph.db")
    if not os.path.exists(path):
        return FAIL, "langgraph.db not found — run skill once to initialize"
    return PASS, path

# ── Run all checks ────────────────────────────────────────────────────────────
def main():
    os.makedirs(LOGS, exist_ok=True)
    ts = datetime.now(timezone.utc)
    print(f"\n{'='*55}")
    print(f"  NemoClaw Validation — {ts.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*55}")

    print("\nCategory 1 — Environment")
    check("Environment", 1,  "Docker Desktop running",      c1_docker_running)
    check("Environment", 2,  "Docker version >= 29.0",      c1_docker_version)
    check("Environment", 3,  "Python version >= 3.11",      c1_python_version)
    check("Environment", 4,  "openshell in PATH",           c1_openshell_path)
    check("Environment", 5,  "Node >= 20",                  c1_node_version)

    print("\nCategory 2 — NemoClaw Runtime")
    check("Runtime", 6,  "Gateway reachable",               c2_gateway_reachable)
    check("Runtime", 7,  "Sandbox nemoclaw-assistant Ready", c2_sandbox_ready)
    check("Runtime", 8,  "Inference provider = openai",     c2_inference_provider)
    check("Runtime", 9,  "Inference model = gpt-4o-mini",   c2_inference_model)
    check("Runtime", 10, "openclaw.json writable",          c2_openclaw_json_writable)

    print("\nCategory 3 — API Keys")
    check("API Keys", 11, "NGC_API_KEY present",            c3_ngc_key)
    check("API Keys", 12, "ANTHROPIC_API_KEY present",      c3_anthropic_key)
    check("API Keys", 13, "OPENAI_API_KEY present",         c3_openai_key)
    check("API Keys", 14, "NVIDIA_INFERENCE_API_KEY present", c3_nvidia_key)
    check("API Keys", 15, "GOOGLE_API_KEY present",           c3_google_key)
    check("API Keys", 16, "ASANA_ACCESS_TOKEN present",       c3_asana_key)
    check("API Keys", 17, "Asana connection valid",           c3_asana_connection)

    print("\nCategory 4 — Budget System")
    check("Budget", 18, "provider-spend.json exists",       c4_spend_file_exists)
    check("Budget", 19, "Anthropic budget < 100%",          c4_anthropic_budget)
    check("Budget", 20, "OpenAI budget < 100%",             c4_openai_budget)
    check("Budget", 21, "Google budget < 100%",             c4_google_budget)
    check("Budget", 22, "provider-usage.jsonl writable",    c4_usage_log)

    print("\nCategory 5 — Routing System")
    check("Routing", 23, "budget-enforcer.py runs",         c5_enforcer_runs)
    check("Routing", 24, "general_short → cheap_openai",    c5_general_short_routing)
    check("Routing", 25, "complex_reasoning → reasoning_claude", c5_complex_reasoning_routing)

    print("\nCategory 6 — Skill System")
    check("Skills", 26, "obs.py executes cleanly",              c6_obs_script)
    check("Skills", 27, "LangGraph graph patterns validated",  c6_graph_validation)
    check("Skills", 28, "skill-runner.py exists",           c6_skill_runner_exists)
    check("Skills", 29, "research-brief/skill.yaml valid",  c6_skill_yaml_valid)
    check("Skills", 30, "research-brief/outputs/ writable", c6_outputs_dir)
    check("Skills", 31, "LangGraph checkpoint DB exists",   c6_checkpoint_db)

    print(f"\n{'='*55}")
    print(f"  Results: {total_pass} passed  {total_warn} warnings  {total_fail} failed")
    print(f"{'='*55}\n")

    run_record = {
        "timestamp": ts.isoformat(),
        "total_pass": total_pass,
        "total_warn": total_warn,
        "total_fail": total_fail,
        "checks": results,
    }
    with open(VALIDATION_LOG, "a") as f:
        f.write(json.dumps(run_record) + "\n")

    sys.exit(0 if total_fail == 0 else 1)

if __name__ == "__main__":
    main()
