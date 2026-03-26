#!/usr/bin/env python3
"""
NemoClaw Skill: b05-feature-impl-writer
Feature Implementation Writer v1.0.0
F05 | B | dual-use | executor
Schema v2 | Runner v4.0+

Generates implementation code from feature specifications.
Step 1 extracts a structured implementation plan (functions, classes,
modules, test targets). Steps 3/5 validate against that plan.

Deterministic validation:
- Implementation plan coverage (each planned unit has a definition)
- Separate test block present
- Error handling on risk paths (external input, I/O, integration)
- No fake completeness patterns
- No unspecified dependencies
- Language-aware structural checks
- React-specific component validation
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


# ── Language Profiles ─────────────────────────────────────────────────────────
LANGUAGE_PROFILES = {
    "python": {
        "function_patterns": [
            re.compile(r'^\s*def\s+(\w+)\s*\(', re.MULTILINE),
            re.compile(r'^\s*async\s+def\s+(\w+)\s*\(', re.MULTILINE),
        ],
        "class_patterns": [
            re.compile(r'^\s*class\s+(\w+)\s*[:\(]', re.MULTILINE),
        ],
        "error_patterns": [
            re.compile(r'\btry\s*:', re.MULTILINE),
            re.compile(r'\bexcept\b', re.MULTILINE),
            re.compile(r'\braise\b', re.MULTILINE),
            re.compile(r'\bif\s+not\b', re.MULTILINE),
        ],
        "test_patterns": [
            re.compile(r'\bdef\s+test_', re.MULTILINE),
            re.compile(r'\bassert\b', re.MULTILINE),
            re.compile(r'\bpytest\b', re.IGNORECASE),
            re.compile(r'\bunittest\b', re.IGNORECASE),
        ],
        "import_pattern": re.compile(r'^\s*(?:import|from)\s+(\S+)', re.MULTILINE),
        "is_react": False,
    },
    "javascript": {
        "function_patterns": [
            re.compile(r'(?:function|const|let|var)\s+(\w+)\s*(?:=\s*(?:async\s*)?\(|=\s*(?:async\s*)?function|\()', re.MULTILINE),
            re.compile(r'(?:export\s+(?:default\s+)?)?(?:function|const)\s+(\w+)', re.MULTILINE),
        ],
        "class_patterns": [
            re.compile(r'\bclass\s+(\w+)', re.MULTILINE),
        ],
        "error_patterns": [
            re.compile(r'\btry\s*\{', re.MULTILINE),
            re.compile(r'\bcatch\s*\(', re.MULTILINE),
            re.compile(r'\bthrow\b', re.MULTILINE),
            re.compile(r'\.catch\s*\(', re.MULTILINE),
        ],
        "test_patterns": [
            re.compile(r'\b(?:describe|it|test)\s*\(', re.MULTILINE),
            re.compile(r'\bexpect\s*\(', re.MULTILINE),
            re.compile(r'\bassert\b', re.MULTILINE),
        ],
        "import_pattern": re.compile(r'(?:import\s+.*\s+from\s+[\'"](\S+)[\'"]|require\s*\(\s*[\'"](\S+)[\'"]\s*\))', re.MULTILINE),
        "is_react": False,
    },
    "typescript": None,  # Inherits from javascript
    "bash": {
        "function_patterns": [
            re.compile(r'(?:^|\n)\s*(?:function\s+)?(\w+)\s*\(\s*\)\s*\{', re.MULTILINE),
        ],
        "class_patterns": [],
        "error_patterns": [
            re.compile(r'\bset\s+-e\b', re.MULTILINE),
            re.compile(r'\bif\s+\[', re.MULTILINE),
            re.compile(r'\b\|\|\s*(?:exit|echo|die)\b', re.MULTILINE),
            re.compile(r'\btrap\b', re.MULTILINE),
        ],
        "test_patterns": [
            re.compile(r'\bassert\b', re.IGNORECASE),
            re.compile(r'\btest\b.*\bfunction\b', re.IGNORECASE),
            re.compile(r'echo\s+.*(?:PASS|FAIL|OK)', re.IGNORECASE),
        ],
        "import_pattern": re.compile(r'(?:source|\.)\s+(\S+)', re.MULTILINE),
        "is_react": False,
    },
    "react": {
        "function_patterns": [
            re.compile(r'(?:function|const|let)\s+(\w+)\s*(?:=\s*\(|[\(:])', re.MULTILINE),
            re.compile(r'export\s+(?:default\s+)?(?:function|const)\s+(\w+)', re.MULTILINE),
        ],
        "class_patterns": [
            re.compile(r'\bclass\s+(\w+)', re.MULTILINE),
        ],
        "error_patterns": [
            re.compile(r'\btry\s*\{', re.MULTILINE),
            re.compile(r'\bcatch\s*\(', re.MULTILINE),
            re.compile(r'\.catch\s*\(', re.MULTILINE),
        ],
        "test_patterns": [
            re.compile(r'\b(?:describe|it|test)\s*\(', re.MULTILINE),
            re.compile(r'\bexpect\s*\(', re.MULTILINE),
            re.compile(r'\brender\s*\(', re.MULTILINE),
        ],
        "import_pattern": re.compile(r'import\s+.*\s+from\s+[\'"](\S+)[\'"]', re.MULTILINE),
        "is_react": True,
        "react_patterns": {
            "component": re.compile(r'(?:return\s*\(|<\w+)', re.MULTILINE),
            "state": re.compile(r'\b(?:useState|useReducer|this\.state)\b', re.MULTILINE),
            "props": re.compile(r'\b(?:props|Props|defaultProps)\b', re.MULTILINE),
        },
    },
    "go": {
        "function_patterns": [
            re.compile(r'\bfunc\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)\s*\(', re.MULTILINE),
        ],
        "class_patterns": [
            re.compile(r'\btype\s+(\w+)\s+struct\b', re.MULTILINE),
        ],
        "error_patterns": [
            re.compile(r'\bif\s+err\s*!=\s*nil\b', re.MULTILINE),
            re.compile(r'\breturn\s+.*,\s*err\b', re.MULTILINE),
        ],
        "test_patterns": [
            re.compile(r'\bfunc\s+Test\w+\b', re.MULTILINE),
            re.compile(r'\bt\.(?:Error|Fatal|Run)\b', re.MULTILINE),
        ],
        "import_pattern": re.compile(r'"(\S+)"', re.MULTILINE),
        "is_react": False,
    },
}

# Aliases
LANGUAGE_PROFILES["typescript"] = LANGUAGE_PROFILES["javascript"]
LANGUAGE_PROFILES["js"] = LANGUAGE_PROFILES["javascript"]
LANGUAGE_PROFILES["ts"] = LANGUAGE_PROFILES["typescript"]
LANGUAGE_PROFILES["py"] = LANGUAGE_PROFILES["python"]
LANGUAGE_PROFILES["sh"] = LANGUAGE_PROFILES["bash"]
LANGUAGE_PROFILES["shell"] = LANGUAGE_PROFILES["bash"]
LANGUAGE_PROFILES["jsx"] = LANGUAGE_PROFILES["react"]
LANGUAGE_PROFILES["tsx"] = LANGUAGE_PROFILES["react"]


def get_language_profile(language):
    """Get the language profile, falling back to python-like defaults."""
    lang_lower = language.lower().strip()
    profile = LANGUAGE_PROFILES.get(lang_lower)
    if profile is not None:
        return profile, lang_lower
    # Fuzzy match
    for key in LANGUAGE_PROFILES:
        if key in lang_lower or lang_lower in key:
            p = LANGUAGE_PROFILES[key]
            if p is not None:
                return p, key
    return LANGUAGE_PROFILES["python"], "python"


# ── Fake Completeness Detection ───────────────────────────────────────────────
FAKE_COMPLETENESS_PATTERNS = [
    re.compile(r'//\s*implementation\s+here', re.IGNORECASE),
    re.compile(r'#\s*implementation\s+here', re.IGNORECASE),
    re.compile(r'//\s*TODO:\s*implement', re.IGNORECASE),
    re.compile(r'#\s*TODO:\s*implement', re.IGNORECASE),
    re.compile(r'^\s*pass\s*$', re.MULTILINE),  # Python pass as sole body
    re.compile(r'return\s+null\s*;?\s*//\s*(?:placeholder|todo|stub)', re.IGNORECASE),
    re.compile(r'catch\s*\([^)]*\)\s*\{\s*\}', re.MULTILINE),  # Empty catch blocks
    re.compile(r'except\s*.*:\s*\n\s*pass\b', re.MULTILINE),  # except: pass
    re.compile(r'//\s*\.\.\.\s*$', re.MULTILINE),  # // ...
    re.compile(r'#\s*\.\.\.\s*$', re.MULTILINE),  # # ...
    re.compile(r'\bNotImplementedError\b'),
]

# Banned claims
BANNED_CLAIMS = [
    re.compile(r'(?:this\s+code\s+(?:has\s+been|is|was)\s+)?tested\s+and\s+verified', re.IGNORECASE),
    re.compile(r'production[- ]ready', re.IGNORECASE),
    re.compile(r'fully\s+tested', re.IGNORECASE),
    re.compile(r'works\s+(?:correctly|perfectly|as\s+expected)', re.IGNORECASE),
]

BANNED_FLUFF = [
    "leverage synergies", "best-in-class", "paradigm shift",
    "move the needle", "low-hanging fruit",
]


# ── Implementation Plan Extraction ────────────────────────────────────────────
def extract_implementation_plan(feature_spec, language):
    """Extract structured implementation plan from feature spec.
    Returns dict with: functions, classes, modules, test_targets, file_structure."""
    spec_lower = feature_spec.lower()
    plan = {
        "functions": [],
        "classes": [],
        "modules": [],
        "test_targets": [],
        "file_structure": "single_file",
        "has_io_paths": False,
        "has_external_input": False,
        "has_integration": False,
    }

    # Detect implementation units from spec keywords
    # Functions: look for verb phrases indicating behavior
    func_indicators = re.findall(
        r'(?:should|must|will|can|needs?\s+to)\s+(\w+(?:\s+\w+){0,3})',
        spec_lower
    )
    for indicator in func_indicators:
        words = indicator.strip().split()
        if len(words) >= 1:
            # Convert to function-like name
            func_name = "_".join(words[:3])
            if func_name not in plan["functions"] and len(func_name) >= 3:
                plan["functions"].append(func_name)

    # Also look for explicit function/method mentions
    explicit_funcs = re.findall(
        r'(?:function|method|endpoint|handler|route)\s*:?\s*[`"]?(\w+)',
        spec_lower
    )
    for f in explicit_funcs:
        if f not in plan["functions"]:
            plan["functions"].append(f)

    # Classes: look for nouns with object-like structure
    class_indicators = re.findall(
        r'(?:class|model|entity|object|type|interface|component|service|manager|handler|controller)\s*:?\s*[`"]?(\w+)',
        spec_lower
    )
    for c in class_indicators:
        if c not in plan["classes"] and len(c) >= 3:
            plan["classes"].append(c)

    # Test targets: primary units to test
    plan["test_targets"] = (plan["functions"][:3] + plan["classes"][:2])[:5]
    if not plan["test_targets"]:
        plan["test_targets"] = ["main_functionality"]

    # File structure decision
    total_units = len(plan["functions"]) + len(plan["classes"])
    if total_units > 6:
        plan["file_structure"] = "multi_module"
    elif total_units > 3:
        plan["file_structure"] = "component_helper_test"
    else:
        plan["file_structure"] = "single_file"

    # Detect risk paths for error handling requirements
    io_markers = ["file", "read", "write", "disk", "path", "open", "save",
                   "load", "download", "upload", "stream"]
    external_markers = ["input", "user", "request", "param", "argument",
                         "form", "body", "query", "payload"]
    integration_markers = ["api", "http", "fetch", "request", "endpoint",
                            "database", "db", "query", "connect", "socket",
                            "webhook", "callback"]

    plan["has_io_paths"] = any(m in spec_lower for m in io_markers)
    plan["has_external_input"] = any(m in spec_lower for m in external_markers)
    plan["has_integration"] = any(m in spec_lower for m in integration_markers)

    # Cap lists to prevent bloat
    plan["functions"] = plan["functions"][:10]
    plan["classes"] = plan["classes"][:5]

    return plan


# ── Code Block Extraction ─────────────────────────────────────────────────────
CODE_BLOCK_PATTERN = re.compile(r'```(\w*)\s*\n(.*?)\n\s*```', re.DOTALL)


def extract_code_blocks(text):
    """Extract all code blocks with their language tags.
    Returns list of (lang_tag, code_content) tuples."""
    blocks = []
    for m in CODE_BLOCK_PATTERN.finditer(text):
        lang_tag = m.group(1).strip().lower()
        content = m.group(2).strip()
        blocks.append((lang_tag, content))
    return blocks


def classify_code_blocks(blocks):
    """Classify code blocks as implementation or test.
    Returns (impl_blocks, test_blocks)."""
    impl_blocks = []
    test_blocks = []

    test_indicators = re.compile(
        r'\b(?:test_|Test|describe\s*\(|it\s*\(|expect\s*\(|assert|'
        r'pytest|unittest|jest|mocha|spec\.)\b', re.IGNORECASE)

    for lang_tag, content in blocks:
        if test_indicators.search(content):
            test_blocks.append((lang_tag, content))
        else:
            impl_blocks.append((lang_tag, content))

    return impl_blocks, test_blocks


# ── Allowed Dependencies Extraction ───────────────────────────────────────────
def extract_allowed_dependencies(feature_spec, language, integration_context):
    """Build the set of allowed dependency names from inputs."""
    allowed = set()
    all_text = f"{feature_spec} {language} {integration_context}".lower()

    # Standard library modules (always allowed)
    std_libs = {
        "python": {"os", "sys", "json", "re", "datetime", "pathlib", "typing",
                    "collections", "functools", "itertools", "math", "hashlib",
                    "uuid", "time", "io", "csv", "yaml", "argparse", "logging",
                    "subprocess", "shutil", "copy", "abc", "dataclasses",
                    "contextlib", "textwrap", "unittest", "pytest"},
        "javascript": {"fs", "path", "http", "https", "crypto", "util",
                         "events", "stream", "url", "querystring", "os",
                         "child_process", "assert"},
        "react": {"react", "react-dom"},
    }

    lang_lower = language.lower().strip()
    for key, libs in std_libs.items():
        if key in lang_lower or lang_lower in key:
            allowed.update(libs)

    # Extract explicit dependencies from all input text
    dep_refs = re.findall(r'[`\'"]([\w@/.-]+)[`\'"]', all_text)
    allowed.update(r.lower().split("/")[0].lstrip("@") for r in dep_refs if len(r) >= 2)

    # Extract package names mentioned near import-like words
    import_refs = re.findall(
        r'(?:import|require|install|pip\s+install|npm\s+install|from)\s+[`\'"]*(\w[\w.-]*)',
        all_text
    )
    allowed.update(r.lower() for r in import_refs if len(r) >= 2)

    # Extract technology names
    tech_refs = re.findall(r'\b(express|flask|django|fastapi|nextjs|axios|lodash|'
                            r'pandas|numpy|sqlalchemy|prisma|mongoose|redis|'
                            r'langchain|langgraph|openai|anthropic|pydantic)\b',
                            all_text, re.IGNORECASE)
    allowed.update(r.lower() for r in tech_refs)

    return allowed


# ── Validation ────────────────────────────────────────────────────────────────
def validate_implementation(code_text, plan, profile, lang_key, allowed_deps):
    """Full deterministic validation. Returns list of issues."""
    issues = []

    # ── Code blocks present ───────────────────────────────────────────────
    blocks = extract_code_blocks(code_text)
    if not blocks:
        issues.append("No code blocks found in output")
        return issues  # Can't validate further without code

    impl_blocks, test_blocks = classify_code_blocks(blocks)
    all_code = "\n".join(content for _, content in blocks)
    impl_code = "\n".join(content for _, content in impl_blocks)
    test_code = "\n".join(content for _, content in test_blocks)

    # ── Separate test block present ───────────────────────────────────────
    if not test_blocks:
        # Check if test code is embedded in an impl block
        has_inline_test = any(
            pat.search(impl_code) for pat in profile.get("test_patterns", [])
        )
        if not has_inline_test:
            issues.append(
                "No separate test block found — need a code block with "
                "test functions, assertions, or test framework usage")

    # ── Implementation block minimum length ───────────────────────────────
    if len(impl_code) < 100:
        issues.append(
            f"Implementation code is only {len(impl_code)} chars "
            f"(minimum 100 for meaningful implementation)")

    # ── Plan coverage: check each planned unit has a definition ────────────
    defined_names = set()
    for pat in profile.get("function_patterns", []):
        for m in pat.finditer(all_code):
            defined_names.add(m.group(1).lower())
    for pat in profile.get("class_patterns", []):
        for m in pat.finditer(all_code):
            defined_names.add(m.group(1).lower())

    total_planned = len(plan.get("functions", [])) + len(plan.get("classes", []))
    if total_planned > 0:
        covered = 0
        for name in plan.get("functions", []) + plan.get("classes", []):
            name_lower = name.lower().replace(" ", "_")
            # Fuzzy match: check if any defined name contains the planned name or vice versa
            matched = any(
                name_lower in dn or dn in name_lower
                for dn in defined_names
            )
            if matched:
                covered += 1

        # Require at least 50% coverage — plan extraction is heuristic,
        # so we can't demand exact match
        coverage_pct = covered / total_planned if total_planned > 0 else 1.0
        if coverage_pct < 0.5 and total_planned > 1:
            issues.append(
                f"Implementation covers {covered}/{total_planned} planned units "
                f"({coverage_pct:.0%}) — minimum 50% required")

    # At least one structural definition must exist regardless of plan
    if not defined_names and len(impl_code) > 50:
        issues.append(
            "No function or class definitions found in implementation code")

    # ── Error handling on risk paths ──────────────────────────────────────
    needs_error_handling = (
        plan.get("has_io_paths", False) or
        plan.get("has_external_input", False) or
        plan.get("has_integration", False)
    )
    if needs_error_handling:
        has_error = any(
            pat.search(all_code) for pat in profile.get("error_patterns", [])
        )
        if not has_error:
            risk_types = []
            if plan.get("has_io_paths"): risk_types.append("I/O")
            if plan.get("has_external_input"): risk_types.append("external input")
            if plan.get("has_integration"): risk_types.append("integration")
            issues.append(
                f"No error handling found but spec has risk paths: "
                f"{', '.join(risk_types)}")

    # ── Fake completeness patterns ────────────────────────────────────────
    for pat in FAKE_COMPLETENESS_PATTERNS:
        matches = pat.findall(impl_code)
        if matches:
            # Allow pass in test stubs only
            if pat.pattern == r'^\s*pass\s*$' and not test_code:
                # Check if pass is in implementation, not in a test
                issues.append(
                    f"Fake completeness detected in implementation: "
                    f"'{matches[0].strip()}'")
            elif 'pass' not in pat.pattern:
                issues.append(
                    f"Fake completeness detected: '{matches[0].strip()[:60]}'")

    # ── Banned claims ─────────────────────────────────────────────────────
    for pat in BANNED_CLAIMS:
        if pat.search(code_text):
            issues.append(
                f"Banned claim detected: code must not claim to be tested or verified")
            break

    # ── Unspecified dependencies ──────────────────────────────────────────
    import_pat = profile.get("import_pattern")
    if import_pat:
        found_imports = set()
        for m in import_pat.finditer(all_code):
            # Get the first non-None group
            imp = next((g for g in m.groups() if g), None)
            if imp:
                # Normalize: take first component of dotted path
                base = imp.lower().split(".")[0].split("/")[0].lstrip("@")
                if len(base) >= 2:
                    found_imports.add(base)

        unspecified = found_imports - allowed_deps
        # Filter out very common modules unlikely to be problematic
        common_safe = {"os", "sys", "json", "re", "path", "fs", "util",
                        "http", "https", "crypto", "math", "time", "io",
                        "typing", "datetime", "collections", "abc",
                        "dataclasses", "logging", "argparse", "copy",
                        "react", "react-dom"}
        unspecified = unspecified - common_safe

        if unspecified:
            issues.append(
                f"Unspecified dependencies not in feature_spec or integration_context: "
                f"{sorted(unspecified)[:5]}")

    # ── React-specific validation ─────────────────────────────────────────
    if profile.get("is_react"):
        react_pats = profile.get("react_patterns", {})
        has_component = react_pats.get("component") and react_pats["component"].search(all_code)
        if not has_component:
            issues.append("React output missing component structure (return/JSX)")

    # ── Banned fluff ──────────────────────────────────────────────────────
    code_text_lower = code_text.lower()
    for phrase in BANNED_FLUFF:
        if phrase in code_text_lower:
            issues.append(f"Banned fluff: '{phrase}'")

    return issues


# ── Step Handlers ─────────────────────────────────────────────────────────────

EXECUTION_ROLE = """You are a senior software engineer who writes precise, reviewable implementation
code. You follow these absolute rules:

1. Every function has REAL logic — not stubs, placeholders, or pass statements.
2. Error handling covers external-input, parsing, I/O, and integration paths.
   Do NOT add ceremonial try/catch around trivial operations.
3. You NEVER claim the code is tested, verified, or production-ready.
4. You NEVER introduce dependencies not specified in the feature_spec, language,
   or integration_context inputs.
5. Test stubs include meaningful assertions — not just "assert True".
6. Code style follows the requested level: minimal, documented, or defensive.
7. The output is a FIRST DRAFT intended to be runnable after human review
   and integration — not a polished production release."""


def step_1_local(inputs, context):
    """Parse feature spec and build structured implementation plan."""
    feature_spec = inputs.get("feature_spec", "").strip()
    if not feature_spec or len(feature_spec) < 30:
        return None, "feature_spec too short (minimum 30 characters)"

    language = inputs.get("language", "").strip()
    if not language:
        return None, "language is required"

    integration = inputs.get("integration_context", "").strip()
    constraints = inputs.get("constraints", "").strip()
    code_style = inputs.get("code_style", "documented").strip()
    if code_style not in ("minimal", "documented", "defensive"):
        code_style = "documented"

    profile, lang_key = get_language_profile(language)

    # Extract structured implementation plan
    plan = extract_implementation_plan(feature_spec, language)

    # Extract allowed dependencies
    allowed_deps = extract_allowed_dependencies(feature_spec, language, integration)

    result = {
        "feature_spec": feature_spec,
        "language": language,
        "lang_key": lang_key,
        "integration_context": integration,
        "constraints": constraints,
        "code_style": code_style,
        "is_react": profile.get("is_react", False),
        "plan": plan,
        "allowed_deps": sorted(allowed_deps),
        "file_structure": plan["file_structure"],
    }

    return {"output": result}, None


def step_2_llm(inputs, context):
    """Generate complete implementation with error handling and documentation."""
    analysis = context.get("step_1_output", context.get("_resolved_input", {}))
    if not analysis or not isinstance(analysis, dict):
        return None, "No analysis from step 1"

    feature_spec = analysis.get("feature_spec", "")
    language = analysis.get("language", "")
    integration = analysis.get("integration_context", "")
    constraints = analysis.get("constraints", "")
    code_style = analysis.get("code_style", "documented")
    is_react = analysis.get("is_react", False)
    plan = analysis.get("plan", {})
    file_structure = analysis.get("file_structure", "single_file")

    style_instructions = {
        "minimal": "Write lean code. No comments except where logic is non-obvious. No docstrings.",
        "documented": "Write code with docstrings for every function/class, inline comments for complex logic, and type hints where applicable.",
        "defensive": "Write heavily validated code. Check every input. Validate every return. Log every decision point. Include type hints and docstrings.",
    }

    plan_summary = []
    if plan.get("functions"):
        plan_summary.append(f"Functions to implement: {', '.join(plan['functions'][:8])}")
    if plan.get("classes"):
        plan_summary.append(f"Classes to implement: {', '.join(plan['classes'][:5])}")
    plan_summary.append(f"File structure: {file_structure}")
    if plan.get("has_io_paths"):
        plan_summary.append("Has I/O paths — error handling required for file/network operations")
    if plan.get("has_external_input"):
        plan_summary.append("Has external input — validation and error handling required")
    if plan.get("has_integration"):
        plan_summary.append("Has integration paths — error handling required for API/DB calls")

    plan_block = "\n".join(f"  - {s}" for s in plan_summary)

    react_instruction = ""
    if is_react:
        react_instruction = """
REACT-SPECIFIC RULES:
- Output must include component structure with JSX return
- Separate UI rendering from business logic
- If the spec implies state, use useState/useReducer
- If the spec implies props, define a Props type/interface
- Export the component as default export"""

    constraint_block = ""
    if constraints:
        constraint_block = f"\nCONSTRAINTS (must be reflected in implementation):\n{constraints}"

    integration_block = ""
    if integration:
        integration_block = f"\nINTEGRATION CONTEXT (use these imports/APIs only):\n{integration}"

    system = f"""{EXECUTION_ROLE}

LANGUAGE: {language}
CODE STYLE: {code_style} — {style_instructions.get(code_style, '')}
{react_instruction}
{constraint_block}
{integration_block}

IMPLEMENTATION PLAN (from analysis):
{plan_block}

OUTPUT STRUCTURE:
1. A markdown section "## Implementation" with one or more code blocks
   containing the complete implementation.
2. A separate markdown section "## Tests" with a code block containing
   test stubs with meaningful assertions (not just assert True).

RULES:
1. Implement ALL planned functions/classes with real logic.
2. Add error handling for I/O, external input, and integration paths ONLY.
   Do NOT wrap trivial operations in try/catch.
3. Do NOT import or use any package not mentioned in the feature spec or
   integration context. Standard library imports are always allowed.
4. Do NOT include: "// implementation here", empty catch blocks, pass as
   sole function body, return null as placeholder.
5. Do NOT claim the code is tested or verified.
6. Test stubs should call the primary functions and assert expected behavior.

Output ONLY the markdown. No preamble, no explanation outside code comments."""

    user = f"""FEATURE SPECIFICATION:
{feature_spec}

Generate the complete {language} implementation."""

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
    plan = analysis.get("plan", {})
    lang_key = analysis.get("lang_key", "python")
    allowed_deps = set(analysis.get("allowed_deps", []))

    profile, _ = get_language_profile(lang_key)

    code = context.get("improved_code", context.get("generated_code",
           context.get("step_2_output", "")))
    if isinstance(code, dict):
        code = str(code)
    if not code:
        return None, "No code to evaluate"

    # ── Layer 1: Deterministic validation ─────────────────────────────────
    det_issues = validate_implementation(code, plan, profile, lang_key, allowed_deps)

    det_penalty = len(det_issues)
    structural_score = max(0, 10 - (det_penalty * 2))

    if structural_score <= 2:
        return {"output": {
            "quality_score": structural_score,
            "structural_score": structural_score,
            "logic_quality": 0,
            "spec_coverage": 0,
            "deterministic_issues": det_issues,
            "llm_feedback": "Too many structural issues — fix deterministic failures first",
            "feedback": f"STRUCTURAL ({len(det_issues)} issues): " + " | ".join(det_issues[:8]),
        }}, None

    # ── Layer 2: LLM quality evaluation ───────────────────────────────────
    feature_spec = analysis.get("feature_spec", "")

    system = """You are a strict code reviewer.

Score these dimensions (each 0-10):

- logic_quality: Does the code logic actually implement the spec? Are edge
  cases considered? Are return values meaningful? Is control flow correct?
  Would this code work if compiled/run (ignoring missing dependencies)?

- spec_coverage: Does the code address ALL requirements in the feature spec?
  Are any behaviors mentioned in the spec missing from the implementation?
  Are test stubs testing the right things?

Respond with JSON ONLY — no markdown, no backticks:
{"logic_quality": N, "spec_coverage": N, "llm_feedback": "Specific notes"}"""

    user = f"""FEATURE SPEC:
{feature_spec[:2000]}

GENERATED CODE:
{code[:5000]}

Evaluate logic quality and spec coverage."""

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    content, error = call_resolved(messages, context, max_tokens=1500)
    if error:
        content, error = call_openai(messages, model="gpt-5.4-mini", max_tokens=1500)

    llm_scores = {"logic_quality": 5, "spec_coverage": 5, "llm_feedback": ""}
    if not error and content:
        try:
            cleaned = content.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
                cleaned = re.sub(r'\s*```$', '', cleaned)
            llm_scores = json.loads(cleaned)
        except (json.JSONDecodeError, TypeError):
            llm_scores["llm_feedback"] = content

    logic = llm_scores.get("logic_quality", 5)
    coverage = llm_scores.get("spec_coverage", 5)
    quality_score = min(structural_score, logic, coverage)

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
        "logic_quality": logic,
        "spec_coverage": coverage,
        "deterministic_issues": det_issues,
        "llm_feedback": llm_fb,
        "feedback": " || ".join(feedback_parts) if feedback_parts else "All checks passed",
    }}, None


def step_4_llm(inputs, context):
    """Strengthen implementation based on critic feedback."""
    analysis = context.get("step_1_output", {})
    feature_spec = analysis.get("feature_spec", "")
    language = analysis.get("language", "")
    plan = analysis.get("plan", {})

    code = context.get("improved_code", context.get("generated_code",
           context.get("step_2_output", "")))
    if isinstance(code, dict):
        code = str(code)

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

You are improving {language} implementation code based on critic feedback.
{det_section}

RULES:
1. Fix ALL structural issues listed above first.
2. Replace any placeholder code with real implementations.
3. Add error handling ONLY where the spec has risk paths (I/O, external input, integration).
4. Strengthen test stubs with meaningful assertions.
5. Do NOT introduce new dependencies not in the feature spec.
6. Do NOT claim the code is tested or verified.
7. Output ONLY the improved markdown with code blocks. No preamble."""

    user = f"""FEATURE SPEC (reference):
{feature_spec[:2000]}

CURRENT CODE:
{code}

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
    """Latest surviving candidate."""
    for key in ("improved_code", "generated_code", "step_2_output"):
        v = context.get(key, "")
        if v and isinstance(v, str) and v.strip():
            return v
    return context.get("generated_code", "")


def step_5_write(inputs, context):
    """Full deterministic gate — hard-fail on critical violations."""
    best = _select_best_output(context)
    if isinstance(best, dict):
        best = str(best)
    if not best or not best.strip():
        return None, "No code to write"

    analysis = context.get("step_1_output", {})
    plan = analysis.get("plan", {})
    lang_key = analysis.get("lang_key", "python")
    allowed_deps = set(analysis.get("allowed_deps", []))

    profile, _ = get_language_profile(lang_key)
    issues = validate_implementation(best, plan, profile, lang_key, allowed_deps)

    critical_keywords = [
        "no code blocks", "no function or class definitions",
        "no separate test block", "fake completeness",
        "implementation code is only", "banned claim",
    ]
    critical = [i for i in issues if any(k in i.lower() for k in critical_keywords)]

    if critical:
        summary = "; ".join(critical[:5])
        return None, f"CODE INTEGRITY FAILURE ({len(critical)} critical): {summary}"

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
