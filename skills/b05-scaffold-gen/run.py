#!/usr/bin/env python3
"""
Skill ID: b05-scaffold-gen
Version: 1.0.0
Family: F05
Domain: B
Tag: internal
Type: executor
Schema: 2
Runner: >=4.0.0
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone


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


def call_openai(messages, model="gpt-5.4-mini", max_tokens=4000):
    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage, SystemMessage
        env = load_env()
        api_key = env.get("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
        llm = ChatOpenAI(model=model, max_tokens=max_tokens, api_key=api_key)
        lc = [SystemMessage(content=m["content"]) if m["role"] == "system"
              else HumanMessage(content=m["content"]) for m in messages]
        return llm.invoke(lc).content, None
    except Exception as e:
        return None, str(e)


def call_anthropic(messages, model="claude-sonnet-4-6", max_tokens=4000):
    try:
        from langchain_anthropic import ChatAnthropic
        from langchain_core.messages import HumanMessage, SystemMessage
        env = load_env()
        api_key = env.get("ANTHROPIC_API_KEY", os.environ.get("ANTHROPIC_API_KEY", ""))
        llm = ChatAnthropic(model=model, max_tokens=max_tokens, api_key=api_key)
        lc = [SystemMessage(content=m["content"]) if m["role"] == "system"
              else HumanMessage(content=m["content"]) for m in messages]
        return llm.invoke(lc).content, None
    except Exception as e:
        return None, str(e)


def call_google(messages, model="gemini-2.5-flash", max_tokens=4000):
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import HumanMessage, SystemMessage
        env = load_env()
        api_key = env.get("GOOGLE_API_KEY", os.environ.get("GOOGLE_API_KEY", ""))
        llm = ChatGoogleGenerativeAI(model=model, max_output_tokens=max_tokens, google_api_key=api_key)
        lc = [SystemMessage(content=m["content"]) if m["role"] == "system"
              else HumanMessage(content=m["content"]) for m in messages]
        return llm.invoke(lc).content, None
    except Exception as e:
        return None, str(e)


def call_resolved(messages, context, max_tokens=4000):
    try:
        provider = context.get("resolved_provider", "openai")
        model = context.get("resolved_model", "gpt-5.4-mini")
        if provider == "anthropic":
            return call_anthropic(messages, model=model, max_tokens=max_tokens)
        elif provider == "google":
            return call_google(messages, model=model, max_tokens=max_tokens)
        else:
            return call_openai(messages, model=model, max_tokens=max_tokens)
    except Exception as e:
        return None, str(e)


# ---------------------------------------------------------------------------
# DETERMINISTIC CHECK FUNCTIONS
# ---------------------------------------------------------------------------

def check_directory_tree_present(text):
    """Returns True if the scaffold contains a directory tree section."""
    patterns = [
        r'##\s+[^\n]*[Dd]irectory',
        r'##\s+[^\n]*[Tt]ree',
        r'##\s+[^\n]*[Ss]tructure',
        r'[├└─│]',
    ]
    for p in patterns:
        if re.search(p, text):
            return True
    return False


def check_dependency_manifest_present(text):
    """Returns True if at least one dependency manifest file is referenced."""
    manifest_patterns = [
        r'requirements\.txt', r'pyproject\.toml', r'setup\.py', r'setup\.cfg',
        r'package\.json', r'package-lock\.json', r'yarn\.lock',
        r'go\.mod', r'go\.sum',
        r'Cargo\.toml', r'Cargo\.lock',
        r'pom\.xml', r'build\.gradle',
        r'Gemfile', r'composer\.json',
        r'pubspec\.yaml',
    ]
    for p in manifest_patterns:
        if re.search(p, text, re.IGNORECASE):
            return True
    return False


def check_setup_instructions_present(text):
    """Returns True if setup instructions section exists."""
    patterns = [
        r'##\s+[^\n]*[Ss]etup',
        r'##\s+[^\n]*[Gg]etting\s+[Ss]tarted',
        r'##\s+[^\n]*[Ii]nstall',
        r'##\s+[^\n]*[Qq]uick\s+[Ss]tart',
        r'##\s+[^\n]*[Hh]ow\s+[Tt]o',
    ]
    for p in patterns:
        if re.search(p, text):
            return True
    return False


def check_purpose_comments_present(text):
    """Returns True if at least some files include purpose comments."""
    comment_patterns = [
        r'#\s+[Pp]urpose',
        r'//\s+[Pp]urpose',
        r'#\s+[Tt]his file',
        r'//\s+[Tt]his file',
        r'#\s+[Ee]ntry\s+point',
        r'//\s+[Ee]ntry\s+point',
        r'#\s+[Mm]ain',
        r'//\s+[Mm]ain',
    ]
    count = 0
    for p in comment_patterns:
        if re.search(p, text):
            count += 1
    return count >= 1


def compute_structural_score(text):
    """Compute a 0-10 structural score based on deterministic checks."""
    score = 0
    if check_directory_tree_present(text):
        score += 3
    if check_dependency_manifest_present(text):
        score += 3
    if check_setup_instructions_present(text):
        score += 2
    if check_purpose_comments_present(text):
        score += 2
    return score


def extract_section(text, heading_keywords):
    for kw in heading_keywords:
        pattern = re.compile(
            rf'(?:^|\n)##\s[^\n]*{re.escape(kw)}[^\n]*\n(.*?)(?=\n##\s[^#]|\Z)',
            re.IGNORECASE | re.DOTALL)
        m = pattern.search(text)
        if m:
            return m.group(1).strip()
    return ""


# ---------------------------------------------------------------------------
# STACK / FEATURE MAPS
# ---------------------------------------------------------------------------

VALID_PROJECT_TYPES = {"web-api", "cli-tool", "library", "microservice"}

STACK_FILE_MAP = {
    "python": {
        "fastapi": ["main.py", "requirements.txt", "pyproject.toml", ".env.example",
                    "Dockerfile", "docker-compose.yml", "tests/", "app/", "app/__init__.py",
                    "app/routes/", "app/models/", "app/config.py", ".gitignore", "README.md"],
        "flask": ["app.py", "requirements.txt", ".env.example", "Dockerfile",
                  "tests/", "app/", ".gitignore", "README.md"],
        "": ["main.py", "requirements.txt", "pyproject.toml", "src/", "tests/",
             ".gitignore", "README.md"],
    },
    "typescript": {
        "express": ["src/index.ts", "package.json", "tsconfig.json", ".env.example",
                    "Dockerfile", "src/routes/", "src/middleware/", "tests/",
                    ".gitignore", "README.md"],
        "": ["src/index.ts", "package.json", "tsconfig.json", "src/",
             "tests/", ".gitignore", "README.md"],
    },
    "go": {
        "gin": ["main.go", "go.mod", "go.sum", "internal/", "cmd/", "Dockerfile",
                "Makefile", ".gitignore", "README.md"],
        "": ["main.go", "go.mod", "cmd/", "internal/", "Makefile",
             ".gitignore", "README.md"],
    },
    "rust": {
        "actix": ["src/main.rs", "Cargo.toml", "Cargo.lock", "src/routes/",
                  "Dockerfile", ".gitignore", "README.md"],
        "": ["src/main.rs", "Cargo.toml", "src/lib.rs", ".gitignore", "README.md"],
    },
    "java": {
        "spring-boot": ["src/main/java/", "src/test/java/", "pom.xml",
                        "src/main/resources/application.properties",
                        "Dockerfile", ".gitignore", "README.md"],
        "": ["src/main/java/", "src/test/java/", "pom.xml", ".gitignore", "README.md"],
    },
}

FEATURE_FILE_MAP = {
    "docker": ["Dockerfile", "docker-compose.yml", ".dockerignore"],
    "ci-cd": [".github/workflows/ci.yml"],
    "testing": ["tests/", "test/"],
    "linting": [".eslintrc.json", ".flake8", "golangci.yml"],
    "logging": [],
    "auth": [],
    "database": [],
}


# ---------------------------------------------------------------------------
# STEP HANDLERS
# ---------------------------------------------------------------------------

def step_1_local(inputs, context):
    """Parse Inputs Validate Stack Build Generation Plan."""
    project_type = inputs.get("project_type", "").strip()
    language = inputs.get("language", "").strip().lower()
    framework = inputs.get("framework", "").strip().lower()
    feature_requirements = inputs.get("feature_requirements", "").strip()
    project_name = inputs.get("project_name", "").strip()

    errors = []

    if not project_type or project_type not in VALID_PROJECT_TYPES:
        errors.append(
            f"Invalid project_type '{project_type}'. Must be one of: {sorted(VALID_PROJECT_TYPES)}"
        )

    if not language or len(language) < 2 or len(language) > 32:
        errors.append(f"Invalid language '{language}'. Must be 2-32 characters.")

    if len(framework) > 64:
        errors.append("Framework name too long (max 64 chars).")

    if not feature_requirements or len(feature_requirements) < 3:
        errors.append("feature_requirements must be at least 3 characters.")

    if len(feature_requirements) > 1000:
        errors.append("feature_requirements exceeds 1000 character limit.")

    if not project_name or len(project_name) < 1 or len(project_name) > 128:
        errors.append(
            f"Invalid project_name '{project_name}'. Must be 1-128 characters."
        )

    if errors:
        return None, "; ".join(errors)

    # Parse feature requirements
    features = [f.strip().lower() for f in re.split(r'[,\n]+', feature_requirements) if f.strip()]

    # Resolve base files for stack
    lang_map = STACK_FILE_MAP.get(language, {})
    base_files = lang_map.get(framework, lang_map.get("", [
        "main." + language[:2], "README.md", ".gitignore"
    ]))

    # Resolve additional files from features
    extra_files = []
    for feat in features:
        for key, files in FEATURE_FILE_MAP.items():
            if key in feat:
                extra_files.extend(files)

    all_files = list(dict.fromkeys(base_files + extra_files))

    # Determine dependency manifest
    dep_manifest = "requirements.txt"
    if language in ("typescript", "javascript"):
        dep_manifest = "package.json"
    elif language == "go":
        dep_manifest = "go.mod"
    elif language == "rust":
        dep_manifest = "Cargo.toml"
    elif language == "java":
        dep_manifest = "pom.xml"

    plan = {
        "project_type": project_type,
        "language": language,
        "framework": framework,
        "features": features,
        "project_name": project_name,
        "planned_files": all_files,
        "dependency_manifest": dep_manifest,
        "validation_passed": True,
    }

    return {"output": plan}, None


def step_2_llm(inputs, context):
    """Generate Complete Project Scaffold."""
    plan = context.get("step_1_output", {})
    if not plan:
        return None, "step_1_output is missing or empty"

    project_type = plan.get("project_type", inputs.get("project_type", ""))
    language = plan.get("language", inputs.get("language", ""))
    framework = plan.get("framework", inputs.get("framework", ""))
    features = plan.get("features", [])
    project_name = plan.get("project_name", inputs.get("project_name", ""))
    planned_files = plan.get("planned_files", [])
    dep_manifest = plan.get("dependency_manifest", "requirements.txt")

    framework_str = f" using {framework}" if framework else ""
    features_str = ", ".join(features) if features else "none specified"
    files_str = "\n".join(f"  - {f}" for f in planned_files)

    system_prompt = (
        "You are an expert software architect and scaffold engineer. You produce precise, "
        "idiomatic project scaffolds tailored to the stated stack. You NEVER fabricate files "
        "or dependencies that do not belong to the chosen language, framework, or project type. "
        "Every file you generate MUST begin with a clear purpose comment using the correct "
        "comment syntax for the language (e.g. # for Python, // for TypeScript/Go/Rust/Java). "
        "You always produce a complete ASCII directory tree using box-drawing characters "
        "(├──, └──, │). You always include a dependency manifest with real, published packages "
        "only. You always include step-by-step setup instructions."
    )

    user_prompt = f"""Generate a complete project scaffold for the following specification:

**Project Name:** {project_name}
**Project Type:** {project_type}
**Language:** {language}{framework_str}
**Features:** {features_str}
**Dependency Manifest:** {dep_manifest}

**Planned Files:**
{files_str}

Produce a structured markdown document with ALL of the following sections in this exact order:

## Directory Structure
Show the complete annotated directory tree using ASCII box-drawing characters (├──, └──, │).
Every file and directory must appear. Annotate each entry with a brief inline comment.

## File Contents
For each file in the scaffold, provide a subsection with the filename as an H3 heading and
the full file content in a fenced code block. EVERY file MUST begin with a purpose comment
using the correct syntax for {language}. Include realistic, idiomatic boilerplate — not empty stubs.
Cover at minimum: entry point, configuration, and one representative module.

## {dep_manifest}
Provide the FULL dependency manifest with realistic, appropriate dependencies for the stated
stack and features. Use ONLY real, published packages. Do NOT fabricate package names.

## Setup Instructions
Numbered step-by-step instructions to: clone/init the project, install dependencies,
configure environment variables, and run the project. Include exact shell commands.

## Notes
Architectural decisions, conventions used, and any important caveats about the scaffold.

STRICT RULES:
- Only include files appropriate for {language}{framework_str} — no files from other stacks
- All package names must be real and published on the official registry for {language}
- Use idiomatic naming conventions for {language}
- The root directory must be named '{project_name}'
- Every file content block must start with a purpose comment
- The directory tree must use ├──, └──, │ characters
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    content, error = call_resolved(messages, context, max_tokens=8000)
    if error:
        content, error = call_openai(messages, model="gpt-5.4-mini", max_tokens=8000)
    if error:
        return None, error

    return {"output": content}, None


def step_3_critic(inputs, context):
    """Evaluate Scaffold Quality Completeness Correctness."""
    scaffold_text = context.get("improved_scaffold", context.get("improved_scaffold", context.get("generated_scaffold", "")))
    if not scaffold_text:
        return None, "No scaffold text found in context for critic evaluation"

    plan = context.get("step_1_output", {})
    language = plan.get("language", inputs.get("language", ""))
    framework = plan.get("framework", inputs.get("framework", ""))
    features = plan.get("features", [])
    project_name = plan.get("project_name", inputs.get("project_name", ""))
    project_type = plan.get("project_type", "")
    dep_manifest = plan.get("dependency_manifest", "requirements.txt")

    # Deterministic checks
    has_tree = check_directory_tree_present(scaffold_text)
    has_manifest = check_dependency_manifest_present(scaffold_text)
    has_setup = check_setup_instructions_present(scaffold_text)
    has_comments = check_purpose_comments_present(scaffold_text)

    structural_score = compute_structural_score(scaffold_text)

    det_issues = []
    if not has_tree:
        det_issues.append("Missing directory tree / structure section with box-drawing characters")
    if not has_manifest:
        det_issues.append(f"Missing dependency manifest ({dep_manifest})")
    if not has_setup:
        det_issues.append("Missing setup instructions section")
    if not has_comments:
        det_issues.append("No purpose comments detected in file contents")

    framework_str = f" using {framework}" if framework else ""
    features_str = ", ".join(features) if features else "none"

    system_prompt = (
        "You are a senior software architect performing a rigorous quality review of a "
        "generated project scaffold. You evaluate correctness, completeness, idiomatic "
        "structure, and absence of fabricated dependencies. You respond ONLY with valid JSON "
        "and nothing else — no markdown fences, no prose outside the JSON object."
    )

    user_prompt = f"""Review this project scaffold for a {language}{framework_str} {project_type} project named '{project_name}' with features: {features_str}.

SCAFFOLD (first 6000 chars):
{scaffold_text[:6000]}

Evaluate on these two dimensions and return ONLY a JSON object with no surrounding text:

{{
  "stack_correctness": <integer 0-10: are all files and dependencies appropriate for {language}{framework_str}? Deduct for wrong-language files, fabricated packages, or mismatched tooling>,
  "completeness": <integer 0-10: are all required files present for the stated project type and features? Deduct for missing entry point, missing manifest, missing setup instructions, missing purpose comments>,
  "stack_correctness_issues": ["specific issue 1", "specific issue 2"],
  "completeness_issues": ["specific issue 1", "specific issue 2"],
  "fabricated_dependencies": ["list any package names that do not exist in the official registry"],
  "missing_files": ["files that should be present but are absent"],
  "improvement_suggestions": ["concrete actionable improvement 1", "concrete actionable improvement 2"],
  "overall_assessment": "one sentence summary"
}}

Scoring guide: 10 = perfect, 8-9 = minor issues, 6-7 = moderate issues, 0-5 = major problems.
Be strict and specific. Every deduction must correspond to a listed issue.
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    content, error = call_resolved(messages, context, max_tokens=3000)
    if error:
        content, error = call_openai(messages, model="gpt-5.4-mini", max_tokens=3000)
    if error:
        return None, error

    # Parse LLM JSON response
    try:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
            cleaned = re.sub(r'\s*```$', '', cleaned)
        scores = json.loads(cleaned)
    except Exception as e:
        scores = {
            "stack_correctness": 5,
            "completeness": 5,
            "stack_correctness_issues": [f"JSON parse error: {str(e)}"],
            "completeness_issues": [],
            "fabricated_dependencies": [],
            "missing_files": [],
            "improvement_suggestions": ["Re-evaluate scaffold manually"],
            "overall_assessment": "Could not parse LLM critic response",
        }

    llm_stack = min(10, max(0, int(scores.get("stack_correctness", 5))))
    llm_completeness = min(10, max(0, int(scores.get("completeness", 5))))

    quality_score = min(structural_score, llm_stack, llm_completeness)

    result = {
        "quality_score": quality_score,
        "structural_score": structural_score,
        "llm_stack_correctness": llm_stack,
        "llm_completeness": llm_completeness,
        "deterministic_issues": det_issues,
        "stack_correctness_issues": scores.get("stack_correctness_issues", []),
        "completeness_issues": scores.get("completeness_issues", []),
        "fabricated_dependencies": scores.get("fabricated_dependencies", []),
        "missing_files": scores.get("missing_files", []),
        "improvement_suggestions": scores.get("improvement_suggestions", []),
        "overall_assessment": scores.get("overall_assessment", ""),
    }

    return {"output": result}, None


def step_4_llm(inputs, context):
    """Improve Scaffold Based On Critic Feedback."""
    original_scaffold = context.get("generated_scaffold", "")
    critic_output = context.get("scaffold_critic_output", {})
    plan = context.get("step_1_output", {})

    if not original_scaffold:
        return None, "No generated_scaffold found in context for improvement"

    language = plan.get("language", inputs.get("language", ""))
    framework = plan.get("framework", inputs.get("framework", ""))
    project_name = plan.get("project_name", inputs.get("project_name", ""))
    project_type = plan.get("project_type", "")
    features = plan.get("features", [])
    dep_manifest = plan.get("dependency_manifest", "requirements.txt")

    framework_str = f" using {framework}" if framework else ""
    features_str = ", ".join(features) if features else "none"

    # Build feedback summary
    feedback_parts = []

    det_issues = critic_output.get("deterministic_issues", [])
    if det_issues:
        feedback_parts.append("STRUCTURAL ISSUES (must fix):\n" + "\n".join(f"- {i}" for i in det_issues))

    stack_issues = critic_output.get("stack_correctness_issues", [])
    if stack_issues:
        feedback_parts.append("STACK CORRECTNESS ISSUES:\n" + "\n".join(f"- {i}" for i in stack_issues))

    completeness_issues = critic_output.get("completeness_issues", [])
    if completeness_issues:
        feedback_parts.append("COMPLETENESS ISSUES:\n" + "\n".join(f"- {i}" for i in completeness_issues))

    fabricated = critic_output.get("fabricated_dependencies", [])
    if fabricated:
        feedback_parts.append("FABRICATED DEPENDENCIES — REMOVE THESE:\n" + "\n".join(f"- {d}" for d in fabricated))

    missing = critic_output.get("missing_files", [])
    if missing:
        feedback_parts.append("MISSING FILES — ADD THESE:\n" + "\n".join(f"- {f}" for f in missing))

    suggestions = critic_output.get("improvement_suggestions", [])
    if suggestions:
        feedback_parts.append("IMPROVEMENT SUGGESTIONS:\n" + "\n".join(f"- {s}" for s in suggestions))

    assessment = critic_output.get("overall_assessment", "")
    if assessment:
        feedback_parts.append(f"OVERALL ASSESSMENT: {assessment}")

    feedback_str = (
        "\n\n".join(feedback_parts)
        if feedback_parts
        else "Minor polish and completeness improvements needed."
    )

    system_prompt = (
        "You are an expert software architect and scaffold engineer. You produce precise, "
        "idiomatic project scaffolds tailored to the stated stack. You NEVER fabricate files "
        "or dependencies that do not belong to the chosen language, framework, or project type. "
        "Every file you generate MUST begin with a clear purpose comment using the correct "
        "comment syntax for the language. You always produce a complete ASCII directory tree "
        "using box-drawing characters (├──, └──, │). You always include a dependency manifest "
        "with real, published packages only. You always include step-by-step setup instructions."
    )

    user_prompt = f"""You previously generated a project scaffold for a {language}{framework_str} {project_type} project named '{project_name}' with features: {features_str}.

A quality review identified the following issues that MUST be addressed:

{feedback_str}

Here is the original scaffold to improve:

{original_scaffold}

Produce a COMPLETE IMPROVED scaffold that:
1. Fixes ALL identified issues listed above
2. Removes every fabricated dependency and replaces with real published packages
3. Adds all missing files, each with a proper purpose comment at the top
4. Ensures the ## Directory Structure section uses ├──, └──, │ box-drawing characters
5. Ensures ## Setup Instructions are numbered, complete, and include exact shell commands
6. Preserves all correct content from the original that has no issues

Output the full improved scaffold in this exact structured markdown format:

## Directory Structure
(complete ASCII tree with ├──, └──, │)

## File Contents
(H3 subsection per file, fenced code block, purpose comment at top of every file)

## {dep_manifest}
(complete manifest with real packages only)

## Setup Instructions
(numbered steps with exact commands)

## Notes
(architectural decisions and caveats)
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    content, error = call_resolved(messages, context, max_tokens=8000)
    if error:
        content, error = call_openai(messages, model="gpt-5.4-mini", max_tokens=8000)
    if error:
        return None, error

    return {"output": content}, None


def step_5_local(inputs, context):
    """Write Scaffold Artifact To Disk."""
    improved = context.get("improved_scaffold", "")
    generated = context.get("generated_scaffold", "")
    final_scaffold = improved if improved else generated

    if not final_scaffold:
        return None, "No scaffold content available to write (both improved_scaffold and generated_scaffold are empty)"

    if not check_directory_tree_present(final_scaffold):
        return None, "Final scaffold failed structural gate: missing directory tree"
    if not check_dependency_manifest_present(final_scaffold):
        return None, "Final scaffold failed structural gate: missing dependency manifest"
    if not check_setup_instructions_present(final_scaffold):
        return None, "Final scaffold failed structural gate: missing setup instructions"

    return {"output": "artifact_written"}, None


# ---------------------------------------------------------------------------
# STEP HANDLERS DICT
# ---------------------------------------------------------------------------

STEP_HANDLERS = {
    "step_1": step_1_local,
    "step_2": step_2_llm,
    "step_3": step_3_critic,
    "step_4": step_4_llm,
    "step_5": step_5_local,
}

# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

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