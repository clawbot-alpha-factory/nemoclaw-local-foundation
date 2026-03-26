#!/usr/bin/env python3
"""
NemoClaw Skill: b05-script-automator
Script Automator v1.0.0
F05 | B | dual-use | executor
Schema v2 | Runner v4.0+

Generates operational automation scripts with safety controls.
Deterministic validation:
- Argument parsing present (language-aware)
- Usage/help documentation
- Conditional error handling (file, subprocess, network — not trivial ops)
- No embedded secrets (tokens, keys, passwords)
- No bad hardcoded paths (user-specific, not in operational_context)
- Dry-run behavioral enforcement for destructive/deployment scripts
- Confirmation prompt for destructive scripts
- Exit codes: 0 success, non-zero failure
- Logging for observable script types
- Shebang for bash scripts
- Idempotency awareness
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone


# ── Env + LLM Helpers ─────────────────────────────────────────────────────────
def load_env():
    p = os.path.expanduser("~/nemoclaw-local-foundation/config/.env")
    k = {}
    if os.path.exists(p):
        with open(p) as f:
            for ln in f:
                ln = ln.strip()
                if "=" in ln and not ln.startswith("#"):
                    a, b = ln.split("=", 1)
                    k[a.strip()] = b.strip()
    return k


def call_openai(messages, model="gpt-5.4-mini", max_tokens=6000):
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, SystemMessage
    env = load_env()
    key = env.get("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
    if not key: return None, "OPENAI_API_KEY not found"
    llm = ChatOpenAI(model=model, api_key=key, max_tokens=max_tokens, temperature=0.3)
    lc = [SystemMessage(content=m["content"]) if m["role"] == "system" else HumanMessage(content=m["content"]) for m in messages]
    return llm.invoke(lc).content, None


def call_anthropic(messages, model="claude-sonnet-4-6", max_tokens=6000):
    from langchain_anthropic import ChatAnthropic
    from langchain_core.messages import HumanMessage, SystemMessage
    env = load_env()
    key = env.get("ANTHROPIC_API_KEY", os.environ.get("ANTHROPIC_API_KEY", ""))
    if not key: return None, "ANTHROPIC_API_KEY not found"
    llm = ChatAnthropic(model=model, api_key=key, max_tokens=max_tokens, temperature=0.3)
    lc = [SystemMessage(content=m["content"]) if m["role"] == "system" else HumanMessage(content=m["content"]) for m in messages]
    return llm.invoke(lc).content, None


def call_google(messages, model="gemini-2.5-flash", max_tokens=6000):
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.messages import HumanMessage, SystemMessage
    env = load_env()
    key = env.get("GOOGLE_API_KEY", os.environ.get("GOOGLE_API_KEY", ""))
    if not key: return None, "GOOGLE_API_KEY not found"
    llm = ChatGoogleGenerativeAI(model=model, google_api_key=key, max_tokens=max_tokens)
    lc = [SystemMessage(content=m["content"]) if m["role"] == "system" else HumanMessage(content=m["content"]) for m in messages]
    return llm.invoke(lc).content, None


def call_resolved(messages, context, max_tokens=6000):
    m = context.get("resolved_model", "")
    p = context.get("resolved_provider", "anthropic")
    if p == "google": return call_google(messages, model=m or "gemini-2.5-flash", max_tokens=max_tokens)
    if p == "openai": return call_openai(messages, model=m or "gpt-5.4-mini", max_tokens=max_tokens)
    return call_anthropic(messages, model=m or "claude-sonnet-4-6", max_tokens=max_tokens)


# ── Code Block Extraction ─────────────────────────────────────────────────────
CODE_BLOCK_PATTERN = re.compile(r'```(\w*)\s*\n(.*?)\n\s*```', re.DOTALL)


def extract_code_blocks(text):
    blocks = []
    for m in CODE_BLOCK_PATTERN.finditer(text):
        blocks.append((m.group(1).strip().lower(), m.group(2).strip()))
    return blocks


# ── Script Type Classification ────────────────────────────────────────────────
SCRIPT_TYPE_KEYWORDS = {
    "data_pipeline": ["etl", "transform", "parse", "convert", "process", "pipeline",
                       "extract", "ingest", "csv", "json", "migrate data"],
    "deployment": ["deploy", "release", "publish", "push", "ship", "rollout",
                    "provision", "terraform", "docker build", "docker push"],
    "maintenance": ["cleanup", "backup", "rotate", "prune", "archive", "reset",
                     "gc", "garbage", "expire", "vacuum", "compact"],
    "monitoring": ["check", "watch", "alert", "health", "status", "poll",
                    "monitor", "heartbeat", "ping"],
    "integration": ["sync", "connect", "webhook", "bridge", "proxy",
                      "migrate", "import", "export"],
    "destructive": ["delete", "remove", "drop", "purge", "wipe", "destroy",
                     "overwrite", "truncate", "rm -rf", "force remove"],
}

# Destructive and deployment scripts get mandatory dry-run
DRY_RUN_REQUIRED_TYPES = {"destructive", "deployment"}

# Observable scripts need logging
LOGGING_REQUIRED_TYPES = {"data_pipeline", "deployment", "monitoring"}


def classify_script(task_description, safety_requirements):
    """Classify script type. Returns set of types."""
    text_lower = (task_description + " " + safety_requirements).lower()
    types = set()
    for stype, keywords in SCRIPT_TYPE_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            types.add(stype)
    if not types:
        types.add("maintenance")
    return types


# ── Argument Parsing Detection ────────────────────────────────────────────────
ARG_PARSE_PATTERNS = {
    "bash": [
        re.compile(r'\bgetopts\b'),
        re.compile(r'\bwhile\s+\[\[?\s*\$#'),
        re.compile(r'\$\{?[1-9]'),
        re.compile(r'\$@|\$\*'),
        re.compile(r'--\w+\)'),  # case statement pattern
        re.compile(r'\bshift\b'),
    ],
    "python": [
        re.compile(r'\bargparse\b'),
        re.compile(r'\bsys\.argv\b'),
        re.compile(r'\bclick\b'),
        re.compile(r'\btyper\b'),
        re.compile(r'\bfire\b'),
    ],
    "node": [
        re.compile(r'\bprocess\.argv\b'),
        re.compile(r'\byargs\b'),
        re.compile(r'\bcommander\b'),
        re.compile(r'\bminimist\b'),
    ],
}


# ── Usage/Help Detection ─────────────────────────────────────────────────────
USAGE_PATTERNS = [
    re.compile(r'\busage\s*[:=]', re.IGNORECASE),
    re.compile(r'--help', re.IGNORECASE),
    re.compile(r'\bprint_usage\b|\bshow_help\b|\busage\(\)', re.IGNORECASE),
    re.compile(r'^\s*#\s*Usage:', re.MULTILINE | re.IGNORECASE),
    re.compile(r'""".*usage.*"""', re.IGNORECASE | re.DOTALL),
    re.compile(r"'''.*usage.*'''", re.IGNORECASE | re.DOTALL),
    re.compile(r'\bdescription\s*=\s*[\'"]', re.IGNORECASE),  # argparse description
]


# ── Error Handling Detection (Conditional) ────────────────────────────────────
ERROR_HANDLING_PATTERNS = {
    "bash": [
        re.compile(r'\bset\s+-e\b'),
        re.compile(r'\bif\s+\['),
        re.compile(r'\|\|\s*(?:exit|echo|die|return)\b'),
        re.compile(r'\btrap\b'),
        re.compile(r'\b\$\?\s*[-!]=\s*0\b'),
    ],
    "python": [
        re.compile(r'\btry\s*:'),
        re.compile(r'\bexcept\b'),
        re.compile(r'\braise\b'),
        re.compile(r'\bif\s+not\s+os\.path\.exists\b'),
        re.compile(r'\bFileNotFoundError\b'),
    ],
    "node": [
        re.compile(r'\btry\s*\{'),
        re.compile(r'\bcatch\s*\('),
        re.compile(r'\.catch\s*\('),
        re.compile(r'\bif\s*\(!.*exists'),
    ],
}

# Risk path indicators — error handling required when these are present
FILE_OP_PATTERNS = [
    re.compile(r'\bopen\s*\(|\bfs\.\w+|\bread\w*File|\bwrite\w*File', re.IGNORECASE),
    re.compile(r'\bcat\s|\bcp\s|\bmv\s|\brm\s|\bmkdir\b|\btouch\b', re.IGNORECASE),
    re.compile(r'\bos\.path\b|\bpathlib\b|\bshutil\b', re.IGNORECASE),
]

SUBPROCESS_PATTERNS = [
    re.compile(r'\bsubprocess\b|\bexec\b|\bchild_process\b'),
    re.compile(r'\$\(.*\)'),  # bash command substitution
    re.compile(r'\beval\b|\b`.*`'),
]

NETWORK_PATTERNS = [
    re.compile(r'\bcurl\b|\bwget\b|\bfetch\b|\brequests\.\b|\bhttp\b|\baxios\b', re.IGNORECASE),
    re.compile(r'\burllib\b|\bsocket\b', re.IGNORECASE),
]


# ── Embedded Secrets Detection ────────────────────────────────────────────────
SECRET_PATTERNS = [
    re.compile(r'["\']sk-[a-zA-Z0-9]{20,}["\']'),  # OpenAI-style keys
    re.compile(r'["\']sk-ant-[a-zA-Z0-9]{20,}["\']'),  # Anthropic keys
    re.compile(r'["\']AIza[a-zA-Z0-9]{20,}["\']'),  # Google keys
    re.compile(r'["\']Bearer\s+[a-zA-Z0-9]{20,}["\']'),  # Bearer tokens
    re.compile(r'password\s*=\s*["\'][^"\']{8,}["\']', re.IGNORECASE),
    re.compile(r'token\s*=\s*["\'][a-zA-Z0-9]{20,}["\']', re.IGNORECASE),
    re.compile(r'api_key\s*=\s*["\'][a-zA-Z0-9]{20,}["\']', re.IGNORECASE),
    re.compile(r'secret\s*=\s*["\'][a-zA-Z0-9]{10,}["\']', re.IGNORECASE),
]


# ── Hardcoded Path Detection ─────────────────────────────────────────────────
# Standard system paths that are always acceptable
SAFE_PATH_PREFIXES = [
    "/tmp", "/var/log", "/var/run", "/usr/local/bin", "/usr/bin",
    "/bin", "/dev/null", "/etc", "/opt/homebrew",
]


def detect_bad_hardcoded_paths(code, operational_context):
    """Detect user-specific or environment-specific hardcoded paths
    not in operational_context and not in safe system dirs."""
    bad_paths = []
    # Find absolute paths in code
    path_matches = re.findall(r'["\'](/[a-zA-Z0-9_.~/-]{5,})["\']', code)
    context_lower = operational_context.lower() if operational_context else ""

    for path in path_matches:
        path_lower = path.lower()
        # Skip safe system paths
        if any(path_lower.startswith(safe) for safe in SAFE_PATH_PREFIXES):
            continue
        # Skip paths mentioned in operational context
        if path_lower in context_lower or path in (operational_context or ""):
            continue
        # Skip paths that are clearly parameterized
        if "{" in path or "$" in path:
            continue
        # Flag user-specific or home-directory paths
        if path.startswith("/Users/") or path.startswith("/home/") or "~/" in path:
            # Check if this specific path is in operational context
            path_base = path.split("/")[-1] if "/" in path else path
            if path_base.lower() not in context_lower:
                bad_paths.append(path)

    return bad_paths


# ── Dry-Run Behavioral Enforcement ────────────────────────────────────────────
DRY_RUN_FLAG_PATTERNS = [
    re.compile(r'--dry[_-]?run', re.IGNORECASE),
    re.compile(r'\bDRY_RUN\b'),
    re.compile(r'\bdry_run\b'),
    re.compile(r'\bdryrun\b', re.IGNORECASE),
]

# Destructive commands that should be wrapped in dry-run conditionals
DESTRUCTIVE_COMMANDS = [
    re.compile(r'\brm\s+-[rf]', re.IGNORECASE),
    re.compile(r'\brmdir\b'),
    re.compile(r'\bshutil\.rmtree\b'),
    re.compile(r'\bos\.remove\b|\bos\.unlink\b'),
    re.compile(r'\bDROP\s+(?:TABLE|DATABASE)\b', re.IGNORECASE),
    re.compile(r'\bDELETE\s+FROM\b', re.IGNORECASE),
    re.compile(r'\bTRUNCATE\b', re.IGNORECASE),
    re.compile(r'\bdocker\s+(?:rm|rmi|system\s+prune)\b', re.IGNORECASE),
    re.compile(r'\bkubectl\s+delete\b', re.IGNORECASE),
]


def check_dry_run_behavioral(code):
    """Check if dry-run flag exists AND destructive commands are wrapped.
    Returns (has_flag, has_behavioral_enforcement, details)."""
    has_flag = any(pat.search(code) for pat in DRY_RUN_FLAG_PATTERNS)

    if not has_flag:
        return False, False, "No dry-run flag found"

    # Check if destructive commands are inside conditionals
    has_destructive = any(pat.search(code) for pat in DESTRUCTIVE_COMMANDS)
    if not has_destructive:
        # Script has dry-run but no destructive commands — that's fine
        return True, True, "Dry-run flag present, no destructive commands to wrap"

    # Check if dry-run variable is used in conditionals near destructive commands
    # Look for patterns like: if not dry_run: rm -rf, or if [ "$DRY_RUN" != "true" ]
    conditional_wrap = re.search(
        r'(?:if\s+(?:not\s+)?(?:dry_run|DRY_RUN|args\.dry_run|dryrun)|'
        r'if\s+\[\s*["\$].*(?:DRY_RUN|dry.run).*\]|'
        r'(?:dry_run|DRY_RUN)\s*(?:!=|==|is\s+(?:not\s+)?(?:True|False)))',
        code, re.IGNORECASE
    )
    # Also check for echo/print before destructive commands when dry-run
    print_instead = re.search(
        r'(?:echo|print|console\.log)\s*.*(?:would|will|dry.run|skipping)',
        code, re.IGNORECASE
    )

    has_behavioral = bool(conditional_wrap) or bool(print_instead)
    if has_behavioral:
        return True, True, "Dry-run flag with conditional enforcement"
    else:
        return True, False, "Dry-run flag exists but destructive commands are not wrapped in conditionals"


# ── Confirmation Prompt Detection ─────────────────────────────────────────────
CONFIRMATION_PATTERNS = [
    re.compile(r'\binput\s*\(.*(?:sure|confirm|proceed|continue)\b', re.IGNORECASE),
    re.compile(r'\bread\s+-p\s*.*(?:sure|confirm|proceed|continue|y/n)\b', re.IGNORECASE),
    re.compile(r'--force\b', re.IGNORECASE),
    re.compile(r'\b(?:force|skip_confirm|no_confirm)\b', re.IGNORECASE),
    re.compile(r'\bconfirm\s*\(', re.IGNORECASE),
    re.compile(r'Are you sure', re.IGNORECASE),
]


# ── Exit Code Detection ──────────────────────────────────────────────────────
EXIT_CODE_PATTERNS = {
    "bash": [
        re.compile(r'\bexit\s+[01]\b'),
        re.compile(r'\bexit\s+\$\?'),
        re.compile(r'\bset\s+-e\b'),  # Implicit non-zero exit on error
    ],
    "python": [
        re.compile(r'\bsys\.exit\s*\(\s*[01]\s*\)'),
        re.compile(r'\bexit\s*\(\s*[01]\s*\)'),
        re.compile(r'\braise\s+SystemExit\b'),
        re.compile(r'if\s+__name__.*main\b'),  # Convention implies exit handling
    ],
    "node": [
        re.compile(r'\bprocess\.exit\s*\(\s*[01]\s*\)'),
        re.compile(r'\bprocess\.exitCode\b'),
    ],
}


# ── Logging Detection ─────────────────────────────────────────────────────────
LOGGING_PATTERNS = {
    "bash": [
        re.compile(r'\becho\s+.*\[', re.IGNORECASE),  # echo "[INFO]..."
        re.compile(r'\blog\s*\(', re.IGNORECASE),
        re.compile(r'>>\s*.*\.log\b'),
        re.compile(r'\bprintf\b.*\['),
        re.compile(r'\becho\s+".*\$\(date', re.IGNORECASE),
    ],
    "python": [
        re.compile(r'\blogging\.\b'),
        re.compile(r'\bprint\s*\(.*\[', re.IGNORECASE),
        re.compile(r'\bprint\s*\(f".*\{.*\}', re.IGNORECASE),
    ],
    "node": [
        re.compile(r'\bconsole\.(?:log|error|warn)\b'),
    ],
}


# ── Fake Completeness ─────────────────────────────────────────────────────────
FAKE_COMPLETENESS_PATTERNS = [
    re.compile(r'//\s*implementation\s+here', re.IGNORECASE),
    re.compile(r'#\s*implementation\s+here', re.IGNORECASE),
    re.compile(r'//\s*TODO:\s*implement', re.IGNORECASE),
    re.compile(r'#\s*TODO:\s*implement', re.IGNORECASE),
    re.compile(r'^\s*pass\s*$', re.MULTILINE),
    re.compile(r'catch\s*\([^)]*\)\s*\{\s*\}', re.MULTILINE),
    re.compile(r'except\s*.*:\s*\n\s*pass\b', re.MULTILINE),
]

BANNED_FLUFF = [
    "leverage synergies", "best-in-class", "paradigm shift",
    "move the needle", "low-hanging fruit",
]


# ── Full Validation ───────────────────────────────────────────────────────────
def validate_script(code_text, plan, target_shell, operational_context):
    """Full deterministic validation. Returns list of issues."""
    issues = []

    # Extract code blocks
    blocks = extract_code_blocks(code_text)
    if not blocks:
        issues.append("No code blocks found in output")
        return issues

    all_code = "\n".join(content for _, content in blocks)
    code_text_lower = code_text.lower()
    script_types = plan.get("script_types", set())

    # ── Argument parsing ──────────────────────────────────────────────────
    arg_pats = ARG_PARSE_PATTERNS.get(target_shell, ARG_PARSE_PATTERNS["python"])
    has_args = any(pat.search(all_code) for pat in arg_pats)
    if not has_args:
        issues.append(
            f"No argument parsing found for {target_shell} "
            f"(need: argparse, sys.argv, getopts, process.argv, etc.)")

    # ── Usage/help documentation ──────────────────────────────────────────
    has_usage = any(pat.search(all_code) or pat.search(code_text) for pat in USAGE_PATTERNS)
    if not has_usage:
        issues.append("No usage/help documentation found (--help, usage(), or usage comment)")

    # ── Conditional error handling ────────────────────────────────────────
    has_file_ops = any(pat.search(all_code) for pat in FILE_OP_PATTERNS)
    has_subprocess = any(pat.search(all_code) for pat in SUBPROCESS_PATTERNS)
    has_network = any(pat.search(all_code) for pat in NETWORK_PATTERNS)
    needs_error_handling = has_file_ops or has_subprocess or has_network

    if needs_error_handling:
        err_pats = ERROR_HANDLING_PATTERNS.get(target_shell, ERROR_HANDLING_PATTERNS["python"])
        has_error = any(pat.search(all_code) for pat in err_pats)
        if not has_error:
            risk_types = []
            if has_file_ops: risk_types.append("file operations")
            if has_subprocess: risk_types.append("subprocess calls")
            if has_network: risk_types.append("network requests")
            issues.append(
                f"No error handling found but script has risk paths: "
                f"{', '.join(risk_types)}")

    # ── No embedded secrets ───────────────────────────────────────────────
    for pat in SECRET_PATTERNS:
        if pat.search(all_code):
            issues.append(
                "Embedded secret detected — use environment variables or arguments instead")
            break

    # ── No bad hardcoded paths ────────────────────────────────────────────
    bad_paths = detect_bad_hardcoded_paths(all_code, operational_context)
    if bad_paths:
        issues.append(
            f"Hardcoded user-specific paths not in operational_context: "
            f"{bad_paths[:3]} — make configurable via arguments")

    # ── Dry-run for destructive/deployment scripts ────────────────────────
    needs_dry_run = bool(script_types & DRY_RUN_REQUIRED_TYPES)
    if needs_dry_run:
        has_flag, has_behavioral, detail = check_dry_run_behavioral(all_code)
        if not has_flag:
            issues.append(
                f"Script is classified as {', '.join(sorted(script_types & DRY_RUN_REQUIRED_TYPES))} "
                f"but has no --dry-run flag")
        elif not has_behavioral:
            issues.append(
                f"Dry-run flag exists but destructive commands are not wrapped "
                f"in conditional logic — dry-run must prevent execution and print "
                f"intended actions instead")

    # ── Confirmation prompt for destructive ───────────────────────────────
    is_destructive = "destructive" in script_types
    if is_destructive:
        has_confirm = any(pat.search(all_code) for pat in CONFIRMATION_PATTERNS)
        if not has_confirm:
            issues.append(
                "Destructive script missing confirmation prompt "
                "(Are you sure? / --force flag)")

    # ── Exit codes ────────────────────────────────────────────────────────
    exit_pats = EXIT_CODE_PATTERNS.get(target_shell, EXIT_CODE_PATTERNS["python"])
    has_exit = any(pat.search(all_code) for pat in exit_pats)
    if not has_exit:
        issues.append(
            f"No explicit exit codes found for {target_shell} "
            f"(need: exit 0/1, sys.exit(0/1), process.exit(0/1))")

    # ── Logging for observable scripts ────────────────────────────────────
    needs_logging = bool(script_types & LOGGING_REQUIRED_TYPES)
    if needs_logging:
        log_pats = LOGGING_PATTERNS.get(target_shell, LOGGING_PATTERNS["python"])
        has_logging = any(pat.search(all_code) for pat in log_pats)
        if not has_logging:
            issues.append(
                f"Script classified as {', '.join(sorted(script_types & LOGGING_REQUIRED_TYPES))} "
                f"but has no status logging")

    # ── Shebang for bash ──────────────────────────────────────────────────
    if target_shell == "bash":
        has_shebang = any(
            content.strip().startswith("#!/") for _, content in blocks
        )
        if not has_shebang:
            issues.append("Bash script missing shebang line (#!/bin/bash or #!/usr/bin/env bash)")

    # ── Fake completeness ─────────────────────────────────────────────────
    for pat in FAKE_COMPLETENESS_PATTERNS:
        if pat.search(all_code):
            issues.append(f"Fake completeness detected: '{pat.pattern[:40]}'")
            break

    # ── Banned fluff ──────────────────────────────────────────────────────
    for phrase in BANNED_FLUFF:
        if phrase in code_text_lower:
            issues.append(f"Banned fluff: '{phrase}'")

    return issues


# ── Step Handlers ─────────────────────────────────────────────────────────────

EXECUTION_ROLE = """You are a senior DevOps engineer who writes precise, production-minded
automation scripts. You follow these absolute rules:

1. Every script has argument parsing for all configurable values — no magic constants.
2. Usage/help documentation is accessible via --help or a header comment block.
3. Error handling covers file operations, subprocess calls, and network requests.
   Do NOT add error handling around trivial operations.
4. NEVER embed secrets, tokens, API keys, or passwords in the script.
   Use environment variables, arguments, or config file references.
5. Destructive and deployment scripts MUST have a --dry-run flag that:
   - PREVENTS execution of destructive actions when enabled
   - PRINTS intended actions instead of executing them
6. Destructive scripts MUST prompt for confirmation unless --force is provided.
7. Exit 0 on success, non-zero on failure — always explicit.
8. Data pipeline, deployment, and monitoring scripts MUST log status with timestamps.
9. Scripts should be idempotent where applicable — safe to re-run.
10. Do NOT hardcode user-specific paths. Use arguments, env vars, or defaults."""


def step_1_local(inputs, context):
    """Parse task and classify script type."""
    task = inputs.get("task_description", "").strip()
    if not task or len(task) < 30:
        return None, "task_description too short (minimum 30 characters)"

    target_shell = inputs.get("target_shell", "").strip()
    if target_shell not in ("bash", "python", "node"):
        return None, f"Invalid target_shell: '{target_shell}'. Must be bash, python, or node."

    operational_context = inputs.get("operational_context", "").strip()
    safety_requirements = inputs.get("safety_requirements", "").strip()
    output_format = inputs.get("output_format", "standalone").strip()

    # Classify script type
    script_types = classify_script(task, safety_requirements)

    # Determine requirements
    needs_dry_run = bool(script_types & DRY_RUN_REQUIRED_TYPES)
    needs_logging = bool(script_types & LOGGING_REQUIRED_TYPES)
    needs_confirmation = "destructive" in script_types

    # Detect risk paths
    all_text = (task + " " + operational_context).lower()
    has_file_ops = any(w in all_text for w in ["file", "read", "write", "path", "directory", "log"])
    has_subprocess = any(w in all_text for w in ["command", "subprocess", "exec", "run", "shell"])
    has_network = any(w in all_text for w in ["api", "http", "curl", "fetch", "request", "url"])

    result = {
        "task_description": task,
        "target_shell": target_shell,
        "operational_context": operational_context,
        "safety_requirements": safety_requirements,
        "output_format": output_format,
        "script_types": sorted(script_types),
        "needs_dry_run": needs_dry_run,
        "needs_logging": needs_logging,
        "needs_confirmation": needs_confirmation,
        "has_file_ops": has_file_ops,
        "has_subprocess": has_subprocess,
        "has_network": has_network,
    }

    return {"output": result}, None


def step_2_llm(inputs, context):
    """Generate complete automation script with safety controls."""
    analysis = context.get("step_1_output", context.get("_resolved_input", {}))
    if not analysis or not isinstance(analysis, dict):
        return None, "No analysis from step 1"

    task = analysis.get("task_description", "")
    target_shell = analysis.get("target_shell", "bash")
    operational_context = analysis.get("operational_context", "")
    safety = analysis.get("safety_requirements", "")
    output_format = analysis.get("output_format", "standalone")
    script_types = analysis.get("script_types", [])
    needs_dry_run = analysis.get("needs_dry_run", False)
    needs_logging = analysis.get("needs_logging", False)
    needs_confirmation = analysis.get("needs_confirmation", False)

    safety_block = ""
    if safety:
        safety_block = f"\nSAFETY REQUIREMENTS:\n{safety}"

    context_block = ""
    if operational_context:
        context_block = f"\nOPERATIONAL CONTEXT:\n{operational_context}"

    dry_run_instruction = ""
    if needs_dry_run:
        dry_run_instruction = """
DRY-RUN REQUIREMENT (MANDATORY):
This script is classified as destructive or deployment.
You MUST include a --dry-run flag that:
1. When enabled: PREVENTS all destructive/write operations
2. When enabled: PRINTS what WOULD happen instead of executing
3. Destructive commands MUST be inside if/else blocks checking dry-run state"""

    confirm_instruction = ""
    if needs_confirmation:
        confirm_instruction = """
CONFIRMATION REQUIREMENT (MANDATORY):
This script is destructive. You MUST include:
1. A confirmation prompt before destructive actions ("Are you sure? [y/N]")
2. A --force flag that skips the confirmation
3. Default behavior WITHOUT --force: prompt and require explicit "y" """

    logging_instruction = ""
    if needs_logging:
        logging_instruction = """
LOGGING REQUIREMENT:
This script type requires status logging. Include:
1. Timestamped log messages for major operations
2. Clear success/failure indicators
3. Summary at completion"""

    format_instruction = ""
    if output_format == "script_plus_config":
        format_instruction = """
OUTPUT FORMAT: script + config file
Produce TWO code blocks:
1. The main script
2. A config file (YAML, JSON, or .env) with configurable values"""

    system = f"""{EXECUTION_ROLE}

TARGET SHELL: {target_shell}
SCRIPT TYPES: {', '.join(script_types)}
{context_block}
{safety_block}
{dry_run_instruction}
{confirm_instruction}
{logging_instruction}
{format_instruction}

OUTPUT STRUCTURE:
1. A markdown section "## Script" with the complete {target_shell} script in a code block
2. A markdown section "## Usage Examples" showing 2-3 invocation examples
{"3. A markdown section '## Config' with the config file" if output_format == "script_plus_config" else ""}

RULES:
1. Argument parsing for ALL configurable values.
2. Usage/help via --help.
3. Error handling on file I/O, subprocess, and network calls ONLY.
4. No embedded secrets — use env vars or arguments.
5. Exit 0 on success, non-zero on failure.
6. {"Bash: start with #!/usr/bin/env bash and set -euo pipefail" if target_shell == "bash" else ""}
7. Script should be idempotent where applicable.

Output ONLY the markdown. No preamble, no explanation outside the code."""

    user = f"""TASK:
{task}

Generate the complete {target_shell} automation script."""

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    content, error = call_resolved(messages, context, max_tokens=8000)
    if error:
        content, error = call_openai(messages, model="gpt-5.4-mini", max_tokens=8000)
    if error:
        return None, error

    return {"output": content}, None


def step_3_critic(inputs, context):
    """Two-layer validation: deterministic then LLM."""
    analysis = context.get("step_1_output", {})
    plan = analysis
    target_shell = analysis.get("target_shell", "bash")
    operational_context = analysis.get("operational_context", "")

    script = context.get("improved_script", context.get("generated_script",
             context.get("step_2_output", "")))
    if isinstance(script, dict):
        script = str(script)
    if not script:
        return None, "No script to evaluate"

    # Rebuild script_types as set for validation
    plan_copy = dict(plan)
    plan_copy["script_types"] = set(plan.get("script_types", []))

    # ── Layer 1: Deterministic validation ─────────────────────────────────
    det_issues = validate_script(script, plan_copy, target_shell, operational_context)

    det_penalty = len(det_issues)
    structural_score = max(0, 10 - (det_penalty * 2))

    if structural_score <= 2:
        return {"output": {
            "quality_score": structural_score,
            "structural_score": structural_score,
            "safety_score": 0,
            "robustness_score": 0,
            "deterministic_issues": det_issues,
            "llm_feedback": "Too many structural issues — fix deterministic failures first",
            "feedback": f"STRUCTURAL ({len(det_issues)} issues): " + " | ".join(det_issues[:8]),
        }}, None

    # ── Layer 2: LLM quality evaluation ───────────────────────────────────
    system = """You are a strict automation script reviewer.

Score these dimensions (each 0-10):

- safety_score: Does the script handle failure cases? Are destructive
  operations properly guarded? Is data loss prevented? Are credentials
  handled securely? Is --force behavior safe?

- robustness_score: Would this script work reliably in production? Does
  it handle edge cases (empty files, missing dirs, network timeouts)?
  Is it idempotent? Are exit codes correct?

Respond with JSON ONLY — no markdown, no backticks:
{"safety_score": N, "robustness_score": N, "llm_feedback": "Specific notes"}"""

    user = f"""TASK: {analysis.get('task_description', '')[:1000]}

GENERATED SCRIPT:
{script[:5000]}

Evaluate safety and robustness."""

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    content, error = call_resolved(messages, context, max_tokens=1500)
    if error:
        content, error = call_openai(messages, model="gpt-5.4-mini", max_tokens=1500)

    llm_scores = {"safety_score": 5, "robustness_score": 5, "llm_feedback": ""}
    if not error and content:
        try:
            cleaned = content.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
                cleaned = re.sub(r'\s*```$', '', cleaned)
            llm_scores = json.loads(cleaned)
        except (json.JSONDecodeError, TypeError):
            llm_scores["llm_feedback"] = content

    safety = llm_scores.get("safety_score", 5)
    robustness = llm_scores.get("robustness_score", 5)
    quality_score = min(structural_score, safety, robustness)

    feedback_parts = []
    if det_issues:
        feedback_parts.append(
            f"STRUCTURAL ({len(det_issues)}): " + " | ".join(det_issues[:8]))
    llm_fb = llm_scores.get("llm_feedback", "")
    if llm_fb:
        feedback_parts.append(f"QUALITY: {llm_fb}")

    return {"output": {
        "quality_score": quality_score,
        "structural_score": structural_score,
        "safety_score": safety,
        "robustness_score": robustness,
        "deterministic_issues": det_issues,
        "llm_feedback": llm_fb,
        "feedback": " || ".join(feedback_parts) if feedback_parts else "All checks passed",
    }}, None


def step_4_llm(inputs, context):
    """Strengthen script based on critic feedback."""
    analysis = context.get("step_1_output", {})
    task = analysis.get("task_description", "")
    target_shell = analysis.get("target_shell", "bash")
    script_types = analysis.get("script_types", [])

    script = context.get("improved_script", context.get("generated_script",
             context.get("step_2_output", "")))
    if isinstance(script, dict):
        script = str(script)

    critic = context.get("step_3_output", {})
    if isinstance(critic, str):
        try:
            critic = json.loads(critic)
        except (json.JSONDecodeError, TypeError):
            critic = {"feedback": critic}

    feedback = critic.get("feedback", "No specific feedback")
    det_issues = critic.get("deterministic_issues", [])

    det_section = ""
    if det_issues:
        det_section = "\nCRITICAL FIXES:\n" + "\n".join(
            f"  - {i}" for i in det_issues[:10])

    system = f"""{EXECUTION_ROLE}

You are improving a {target_shell} automation script based on critic feedback.
SCRIPT TYPES: {', '.join(script_types)}
{det_section}

RULES:
1. Fix ALL structural issues listed above first.
2. Add argument parsing if missing.
3. Add error handling on risk paths only.
4. Add dry-run behavioral enforcement if required.
5. Add confirmation prompt if destructive.
6. Ensure explicit exit codes.
7. No embedded secrets.
8. Output ONLY the improved markdown. No preamble."""

    user = f"""TASK (reference): {task[:1000]}

CURRENT SCRIPT:
{script}

CRITIC FEEDBACK: {feedback}

Fix all issues. Output ONLY the improved markdown."""

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    content, error = call_resolved(messages, context, max_tokens=8000)
    if error:
        content, error = call_openai(messages, model="gpt-5.4-mini", max_tokens=8000)
    if error:
        return None, error

    return {"output": content}, None


def _select_best_output(context):
    for key in ("improved_script", "generated_script", "step_2_output"):
        v = context.get(key, "")
        if v and isinstance(v, str) and v.strip():
            return v
    return context.get("generated_script", "")


def step_5_write(inputs, context):
    """Full deterministic gate — hard-fail on critical violations."""
    best = _select_best_output(context)
    if isinstance(best, dict):
        best = str(best)
    if not best or not best.strip():
        return None, "No script to write"

    analysis = context.get("step_1_output", {})
    plan = dict(analysis)
    plan["script_types"] = set(analysis.get("script_types", []))
    target_shell = analysis.get("target_shell", "bash")
    operational_context = analysis.get("operational_context", "")

    issues = validate_script(best, plan, target_shell, operational_context)

    critical_keywords = [
        "no code blocks", "no argument parsing", "no usage",
        "embedded secret", "no dry-run flag", "not wrapped",
        "missing confirmation", "no explicit exit codes",
        "fake completeness",
    ]
    critical = [i for i in issues if any(k in i.lower() for k in critical_keywords)]

    if critical:
        summary = "; ".join(critical[:5])
        return None, f"SCRIPT INTEGRITY FAILURE ({len(critical)} critical): {summary}"

    return {"output": "artifact_written"}, None


STEP_HANDLERS = {
    "step_1": step_1_local,
    "step_2": step_2_llm,
    "step_3": step_3_critic,
    "step_4": step_4_llm,
    "step_5": step_5_write,
}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--step", required=True)
    parser.add_argument("--input", required=True)
    a = parser.parse_args()
    with open(a.input) as f:
        spec = json.load(f)
    h = STEP_HANDLERS.get(spec["step_id"])
    if not h:
        print(json.dumps({"error": f"Unknown step: {spec['step_id']}"}))
        sys.exit(1)
    result, error = h(spec["inputs"], spec["context"])
    if error:
        print(json.dumps({"error": error}))
        sys.exit(1)
    print(json.dumps(result))
