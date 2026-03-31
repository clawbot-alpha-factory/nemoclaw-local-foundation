#!/usr/bin/env python3
"""
Skill ID: b06-cicd-designer
Version: 1.0.0
Family: F06
Domain: B
Tag: dual-use
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


def call_openai(messages, model=None, max_tokens=4000):
    if model is None:
        from lib.routing import resolve_alias
        _, model, _ = resolve_alias("general_short")
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


def call_anthropic(messages, model=None, max_tokens=4000):
    if model is None:
        from lib.routing import resolve_alias
        _, model, _ = resolve_alias("complex_reasoning")
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


def call_google(messages, model=None, max_tokens=4000):
    if model is None:
        from lib.routing import resolve_alias
        _, model, _ = resolve_alias("moderate")
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import HumanMessage, SystemMessage
        env = load_env()
        api_key = env.get("GOOGLE_API_KEY", os.environ.get("GOOGLE_API_KEY", ""))
        llm = ChatGoogleGenerativeAI(model=model, max_tokens=max_tokens, google_api_key=api_key)
        lc = [SystemMessage(content=m["content"]) if m["role"] == "system"
              else HumanMessage(content=m["content"]) for m in messages]
        return llm.invoke(lc).content, None
    except Exception as e:
        return None, str(e)


def call_resolved(messages, context, max_tokens=4000):
    provider = context.get("resolved_provider", __import__("lib.routing", fromlist=["resolve_alias"]).resolve_alias("moderate")[0])
    model = context.get("resolved_model", "")
    try:
        if provider == "anthropic":
            return call_anthropic(messages, model=model, max_tokens=max_tokens)
        elif provider == "google":
            return call_google(messages, model=model, max_tokens=max_tokens)
        else:
            return call_openai(messages, model=model, max_tokens=max_tokens)
    except Exception as e:
        return None, str(e)


# --- Deterministic check functions ---

REQUIRED_SECTIONS = [
    "stages",
    "trigger",
    "environment",
    "artifact",
    "secret",
    "rollback",
    "notification",
    "duration",
]

SECTION_KEYWORDS = {
    "stages": ["stage", "job", "step"],
    "trigger": ["trigger", "on:", "rules:", "workflow_dispatch", "push", "pull_request", "branches"],
    "environment": ["environment", "env:", "matrix", "variables"],
    "artifact": ["artifact", "upload", "cache", "paths:"],
    "secret": ["secret", "SECRETS", "${{secrets", "vault", "masked", "protected"],
    "rollback": ["rollback", "revert", "undo", "previous version", "restore"],
    "notification": ["notification", "notify", "slack", "email", "webhook", "alert"],
    "duration": ["duration", "estimated", "minutes", "timeout", "time"],
}


def check_sections_present(text):
    text_lower = text.lower()
    results = {}
    for section, keywords in SECTION_KEYWORDS.items():
        found = any(kw.lower() in text_lower for kw in keywords)
        results[section] = found
    present_count = sum(1 for v in results.values() if v)
    score = round((present_count / len(REQUIRED_SECTIONS)) * 10)
    return score, results


def extract_section(text, heading_keywords):
    for kw in heading_keywords:
        pattern = re.compile(
            rf'(?:^|\n)##\s[^\n]*{re.escape(kw)}[^\n]*\n(.*?)(?=\n##\s[^#]|\Z)',
            re.IGNORECASE | re.DOTALL)
        m = pattern.search(text)
        if m:
            return m.group(1).strip()
    return ""


# --- Helper inference functions ---

def _infer_lint_tools(languages):
    tools = []
    for lang in languages:
        if lang == "python":
            tools.extend(["flake8", "black", "mypy"])
        elif lang in ("javascript", "typescript"):
            tools.extend(["eslint", "prettier"])
        elif lang in ("java", "kotlin"):
            tools.extend(["checkstyle", "spotbugs"])
        elif lang == "go":
            tools.extend(["golangci-lint"])
        elif lang == "rust":
            tools.extend(["clippy", "rustfmt"])
    return tools if tools else ["generic-linter"]


def _infer_test_tools(languages):
    for lang in languages:
        if lang == "python":
            return ["pytest"]
        elif lang in ("javascript", "typescript"):
            return ["jest"]
        elif lang == "java":
            return ["junit"]
        elif lang == "go":
            return ["go test"]
        elif lang == "rust":
            return ["cargo test"]
        elif lang == "ruby":
            return ["rspec"]
    return ["test-runner"]


def _infer_build_tools(languages, container_infra):
    tools = []
    if "docker" in container_infra:
        tools.append("docker build")
    if "python" in languages:
        tools.append("pip/wheel")
    if any(l in languages for l in ("javascript", "typescript")):
        tools.append("npm/yarn build")
    if "java" in languages:
        tools.append("maven/gradle")
    if "go" in languages:
        tools.append("go build")
    if "rust" in languages:
        tools.append("cargo build")
    return tools if tools else ["build-tool"]


def _infer_security_tools(desc_lower, gates_lower):
    tools = []
    if "snyk" in desc_lower or "snyk" in gates_lower:
        tools.append("snyk")
    if "sonar" in desc_lower or "sonar" in gates_lower:
        tools.append("sonarqube")
    if "trivy" in desc_lower or "trivy" in gates_lower:
        tools.append("trivy")
    if not tools:
        tools = ["trivy", "semgrep"]
    return tools


# --- Step handlers ---

def step_1_local(inputs, context):
    """Parse Inputs and Build Pipeline Design Plan."""
    project_description = inputs.get("project_description", "").strip()
    deployment_targets = inputs.get("deployment_targets", "").strip()
    quality_gates = inputs.get("quality_gates", "").strip()
    pipeline_format = inputs.get("pipeline_format", "github_actions").strip()
    additional_constraints = inputs.get("additional_constraints", "").strip()

    if len(project_description) < 50:
        return None, "project_description must be at least 50 characters."
    if len(deployment_targets) < 5:
        return None, "deployment_targets must be at least 5 characters."
    if len(quality_gates) < 10:
        return None, "quality_gates must be at least 10 characters."
    if pipeline_format not in ("github_actions", "gitlab_ci", "generic_yaml"):
        return None, f"pipeline_format must be one of: github_actions, gitlab_ci, generic_yaml. Got: {pipeline_format}"

    desc_lower = project_description.lower()

    language_signals = []
    for lang in ["python", "javascript", "typescript", "java", "go", "rust", "ruby", "php", "c#", "dotnet", "kotlin", "swift"]:
        if lang in desc_lower:
            language_signals.append(lang)

    framework_signals = []
    for fw in ["django", "flask", "fastapi", "react", "vue", "angular", "next.js", "spring", "express", "rails", "laravel", "gin", "fiber"]:
        if fw in desc_lower:
            framework_signals.append(fw)

    test_signals = []
    for tool in ["pytest", "jest", "mocha", "junit", "rspec", "go test", "cargo test", "unittest", "cypress", "playwright", "selenium"]:
        if tool in desc_lower:
            test_signals.append(tool)

    container_signals = []
    for c in ["docker", "kubernetes", "k8s", "helm", "terraform", "ansible", "ecs", "fargate", "lambda", "serverless"]:
        if c in desc_lower:
            container_signals.append(c)

    targets = [t.strip() for t in deployment_targets.split(",") if t.strip()]

    coverage_match = re.search(r'(\d+)\s*%?\s*(?:coverage|test coverage)', quality_gates, re.IGNORECASE)
    coverage_threshold = coverage_match.group(1) if coverage_match else None

    justified_stages = []

    justified_stages.append({
        "name": "lint",
        "justification": "Code quality enforcement required for all projects",
        "tools": _infer_lint_tools(language_signals)
    })

    justified_stages.append({
        "name": "test",
        "justification": f"Quality gate requires test execution{f' with {coverage_threshold}% coverage' if coverage_threshold else ''}",
        "tools": test_signals if test_signals else _infer_test_tools(language_signals)
    })

    if any(kw in quality_gates.lower() for kw in ["security", "sast", "scan", "vulnerability", "cve", "snyk", "sonar"]):
        justified_stages.append({
            "name": "security_scan",
            "justification": "Security scan required by quality gates",
            "tools": _infer_security_tools(desc_lower, quality_gates.lower())
        })

    justified_stages.append({
        "name": "build",
        "justification": "Artifact compilation/packaging required for deployment",
        "tools": _infer_build_tools(language_signals, container_signals)
    })

    for target in targets:
        justified_stages.append({
            "name": f"deploy_{target.lower().replace(' ', '_').replace('-', '_')}",
            "justification": f"Deployment to {target} environment as specified in deployment targets",
            "environment": target,
            "tools": []
        })

    if any(kw in quality_gates.lower() for kw in ["performance", "load", "benchmark", "latency", "throughput"]):
        justified_stages.append({
            "name": "performance_test",
            "justification": "Performance benchmarks required by quality gates",
            "tools": ["k6", "locust", "jmeter"]
        })

    plan = {
        "project_description": project_description,
        "deployment_targets": targets,
        "quality_gates": quality_gates,
        "pipeline_format": pipeline_format,
        "additional_constraints": additional_constraints,
        "detected_languages": language_signals,
        "detected_frameworks": framework_signals,
        "detected_test_tools": test_signals,
        "detected_container_infra": container_signals,
        "coverage_threshold": coverage_threshold,
        "justified_stages": justified_stages,
        "stage_count": len(justified_stages),
    }

    return {"output": plan}, None


def step_2_llm(inputs, context):
    """Generate Complete Pipeline Specification Document."""
    plan = context.get("step_1_output", {})
    if not plan:
        return None, "step_1_output not found in context."

    pipeline_format = plan.get("pipeline_format", "github_actions")
    project_description = plan.get("project_description", "")
    deployment_targets = plan.get("deployment_targets", [])
    quality_gates = plan.get("quality_gates", "")
    additional_constraints = plan.get("additional_constraints", "")
    justified_stages = plan.get("justified_stages", [])
    detected_languages = plan.get("detected_languages", [])
    detected_frameworks = plan.get("detected_frameworks", [])
    detected_container_infra = plan.get("detected_container_infra", [])
    coverage_threshold = plan.get("coverage_threshold", "")

    format_instructions = {
        "github_actions": "GitHub Actions YAML (.github/workflows/ci-cd.yml syntax)",
        "gitlab_ci": "GitLab CI YAML (.gitlab-ci.yml syntax)",
        "generic_yaml": "Generic YAML pipeline specification with clear stage definitions",
    }
    format_desc = format_instructions.get(pipeline_format, "GitHub Actions YAML")

    stages_desc = "\n".join(
        f"  - {s['name']}: {s.get('justification', '')} (tools: {', '.join(s.get('tools', [s.get('environment', '')]))})"
        for s in justified_stages
    )

    system_prompt = (
        "You are a senior DevOps architect and CI/CD pipeline specialist with deep expertise "
        "in GitHub Actions, GitLab CI, and cloud-native deployment patterns. You design "
        "production-grade pipelines that are lean, justified by actual project requirements, "
        "and follow security best practices for secret handling, artifact management, and "
        "rollback procedures. You produce complete, syntactically valid pipeline specifications "
        "with no truncation and no placeholder comments like 'add more here'."
    )

    user_prompt = f"""Design a complete CI/CD pipeline specification for the following project.

## Project Description
{project_description}

## Pipeline Format
{format_desc}

## Deployment Targets
{', '.join(deployment_targets)}

## Quality Gates
{quality_gates}

## Detected Project Signals
- Languages: {', '.join(detected_languages) if detected_languages else 'Not explicitly detected'}
- Frameworks: {', '.join(detected_frameworks) if detected_frameworks else 'Not explicitly detected'}
- Container/Infra: {', '.join(detected_container_infra) if detected_container_infra else 'Not explicitly detected'}
- Coverage Threshold: {coverage_threshold + '%' if coverage_threshold else 'Not specified'}

## Justified Stages (include ONLY these — do not add or remove stages)
{stages_desc}

## Additional Constraints
{additional_constraints if additional_constraints else 'None'}

---

Generate a COMPLETE pipeline specification document in Markdown format with ALL of the following sections. Do NOT omit or truncate any section.

## Pipeline Overview
Explain the pipeline design rationale, format choice, and how it maps to the project requirements.

## Trigger Conditions
Define all trigger conditions (push, pull_request, schedule, manual dispatch) with branch filters and conditions appropriate for {pipeline_format}.

## Environment Matrix
Define all environments ({', '.join(deployment_targets)}) with their configuration variables, runner types, and promotion rules between environments.

## Stage Definitions
For each justified stage listed above, provide:
- Stage name and purpose
- Exact commands/actions to run (no placeholders)
- Dependencies on previous stages
- Failure behavior (fail-fast vs continue)
- The {format_desc} YAML snippet for this stage

## Artifact Management
Define artifact upload/download strategy, retention policies (in days), caching strategy for dependencies, and artifact naming conventions.

## Secret Handling Strategy
Define how secrets are managed using {pipeline_format} secret syntax. List ALL required secrets by name (e.g., DOCKER_USERNAME, DEPLOY_KEY). NEVER hardcode any secret values — always use ${{{{ secrets.SECRET_NAME }}}} syntax for GitHub Actions or $SECRET_NAME for GitLab CI.

## Rollback Procedures
Define concrete rollback strategy for each deployment target: automated rollback triggers (e.g., health check failure), exact rollback commands, and manual rollback steps with specific CLI commands.

## Notification Rules
Define notification rules for pipeline success, failure, and deployment events. Include Slack webhook, email, or other notification mechanism with the exact step configuration.

## Complete Pipeline YAML
Provide the FULL, production-ready {format_desc} YAML that implements ALL stages above. This must be syntactically valid, complete, and ready to commit. Do not truncate.

## Estimated Pipeline Duration
Provide estimated duration for each stage (in minutes) and total pipeline duration under normal conditions.

## Security Checklist
List all security best practices applied in this pipeline design (minimum 8 items).

---

CRITICAL RULES:
1. Include ONLY the justified stages listed above — do not add stages not in the list.
2. Every secret reference MUST use the platform's secret syntax — NEVER hardcode values.
3. All deployment stages MUST have explicit environment protection rules.
4. Rollback procedures MUST be concrete with actual commands, not generic descriptions.
5. The Complete Pipeline YAML section MUST be syntactically valid for {pipeline_format} and complete.
6. Do NOT use placeholder comments like "# add your steps here" — provide real implementation.
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    content, error = call_resolved(messages, context, max_tokens=8000)
    if error:
        content, error = call_openai(messages, max_tokens=8000)
    if error:
        return None, error

    return {"output": content}, None


def step_3_critic(inputs, context):
    """Evaluate Pipeline Quality and Completeness."""
    generated_pipeline = context.get("improved_pipeline", context.get("generated_pipeline", ""))
    plan = context.get("step_1_output", {})

    if not generated_pipeline:
        return None, "generated_pipeline not found in context."

    structural_score, section_results = check_sections_present(generated_pipeline)

    missing_sections = [s for s, present in section_results.items() if not present]
    present_sections = [s for s, present in section_results.items() if present]

    hardcoded_secret_patterns = [
        r'password\s*=\s*["\'][^"\']{4,}["\']',
        r'api_key\s*=\s*["\'][^"\']{8,}["\']',
        r'token\s*=\s*["\'][^"\']{8,}["\']',
        r'secret\s*=\s*["\'][^"\']{8,}["\']',
    ]
    has_hardcoded_secrets = any(
        re.search(p, generated_pipeline, re.IGNORECASE)
        for p in hardcoded_secret_patterns
    )

    justified_stages = plan.get("justified_stages", [])
    pipeline_format = plan.get("pipeline_format", "github_actions")
    pipeline_lower = generated_pipeline.lower()
    stages_present = []
    stages_missing = []
    for stage in justified_stages:
        stage_name = stage["name"].lower().replace("_", "[-_]?")
        if re.search(stage_name, pipeline_lower):
            stages_present.append(stage["name"])
        else:
            stages_missing.append(stage["name"])

    stage_coverage = len(stages_present) / max(len(justified_stages), 1)
    stage_score = round(stage_coverage * 10)

    if has_hardcoded_secrets:
        structural_score = max(0, structural_score - 3)

    system_prompt = (
        "You are a senior DevOps architect and CI/CD pipeline specialist. "
        "You evaluate pipeline specifications for production readiness, security, "
        "and completeness. You are strict: a score of 8+ requires genuinely "
        "production-ready output with no placeholders, no hardcoded secrets, "
        "and all required sections fully implemented."
    )

    user_prompt = f"""Evaluate the following CI/CD pipeline specification for quality and completeness.

## Pipeline Format
{pipeline_format}

## Pipeline Specification
{generated_pipeline[:6000]}

## Deterministic Check Results
- Sections present: {', '.join(present_sections) if present_sections else 'None'}
- Sections missing: {', '.join(missing_sections) if missing_sections else 'None'}
- Justified stages present: {', '.join(stages_present) if stages_present else 'None'}
- Justified stages missing: {', '.join(stages_missing) if stages_missing else 'None'}
- Hardcoded secrets detected: {has_hardcoded_secrets}

Evaluate on these two dimensions and respond with ONLY valid JSON (no markdown fences):

{{
  "completeness_score": <integer 1-10>,
  "completeness_rationale": "<brief explanation>",
  "security_score": <integer 1-10>,
  "security_rationale": "<brief explanation>",
  "critical_issues": ["<issue1>", "<issue2>"],
  "improvement_suggestions": ["<suggestion1>", "<suggestion2>", "<suggestion3>"]
}}

Scoring guidance:
- completeness_score: 10 = all sections present with full content, all stages implemented, YAML is complete and syntactically valid, no placeholder comments
- security_score: 10 = no hardcoded secrets, all secrets use platform syntax, environments protected, rollback defined with real commands
- Deduct points for: missing sections, truncated YAML, placeholder comments, missing rollback commands, missing notification config
- Be strict: a score of 8+ requires genuinely production-ready output
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    content, error = call_resolved(messages, context, max_tokens=2000)
    if error:
        content, error = call_openai(messages, max_tokens=2000)
    if error:
        return None, error

    try:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
            cleaned = re.sub(r'\s*```$', '', cleaned)
        scores = json.loads(cleaned)
    except Exception:
        scores = {
            "completeness_score": 5,
            "completeness_rationale": "Could not parse LLM response",
            "security_score": 5,
            "security_rationale": "Could not parse LLM response",
            "critical_issues": [],
            "improvement_suggestions": [],
        }

    completeness_score = int(scores.get("completeness_score", 5))
    security_score = int(scores.get("security_score", 5))

    quality_score = min(structural_score, stage_score, completeness_score, security_score)

    result = {
        "quality_score": quality_score,
        "structural_score": structural_score,
        "stage_score": stage_score,
        "completeness_score": completeness_score,
        "security_score": security_score,
        "sections_present": present_sections,
        "sections_missing": missing_sections,
        "stages_present": stages_present,
        "stages_missing": stages_missing,
        "has_hardcoded_secrets": has_hardcoded_secrets,
        "completeness_rationale": scores.get("completeness_rationale", ""),
        "security_rationale": scores.get("security_rationale", ""),
        "critical_issues": scores.get("critical_issues", []),
        "improvement_suggestions": scores.get("improvement_suggestions", []),
    }

    return {"output": result}, None


def step_4_llm(inputs, context):
    """Improve Pipeline Based on Critic Feedback."""
    critic_output = context.get("step_3_output", {})
    generated_pipeline = context.get("generated_pipeline", "")
    plan = context.get("step_1_output", {})

    if not generated_pipeline:
        return None, "generated_pipeline not found in context."
    if not critic_output:
        return None, "step_3_output not found in context."

    pipeline_format = plan.get("pipeline_format", "github_actions")
    project_description = plan.get("project_description", "")
    deployment_targets = plan.get("deployment_targets", [])
    quality_gates = plan.get("quality_gates", "")
    justified_stages = plan.get("justified_stages", [])

    critical_issues = critic_output.get("critical_issues", [])
    improvement_suggestions = critic_output.get("improvement_suggestions", [])
    sections_missing = critic_output.get("sections_missing", [])
    stages_missing = critic_output.get("stages_missing", [])
    has_hardcoded_secrets = critic_output.get("has_hardcoded_secrets", False)
    quality_score = critic_output.get("quality_score", 5)

    stages_desc = "\n".join(
        f"  - {s['name']}: {s.get('justification', '')} (tools: {', '.join(s.get('tools', [s.get('environment', '')]))})"
        for s in justified_stages
    )

    format_instructions = {
        "github_actions": "GitHub Actions YAML (.github/workflows/ci-cd.yml syntax)",
        "gitlab_ci": "GitLab CI YAML (.gitlab-ci.yml syntax)",
        "generic_yaml": "Generic YAML pipeline specification with clear stage definitions",
    }
    format_desc = format_instructions.get(pipeline_format, "GitHub Actions YAML")

    system_prompt = (
        "You are a senior DevOps architect and CI/CD pipeline specialist with deep expertise "
        "in GitHub Actions, GitLab CI, and cloud-native deployment patterns. You produce "
        "production-grade, complete pipeline specifications with no truncation, no placeholder "
        "comments, and no hardcoded secrets. Every section must be fully implemented."
    )

    user_prompt = f"""Revise and improve the following CI/CD pipeline specification based on critic feedback.

## Original Pipeline Specification
{generated_pipeline[:5000]}

## Critic Feedback (Quality Score: {quality_score}/10)

### Critical Issues to Fix
{chr(10).join(f'- {issue}' for issue in critical_issues) if critical_issues else '- None identified'}

### Improvement Suggestions
{chr(10).join(f'- {s}' for s in improvement_suggestions) if improvement_suggestions else '- None'}

### Missing Sections to Add
{', '.join(sections_missing) if sections_missing else 'None'}

### Missing Stages to Implement
{', '.join(stages_missing) if stages_missing else 'None'}

### Security Issues
{'- Hardcoded secrets detected — replace ALL with platform secret syntax immediately' if has_hardcoded_secrets else '- No hardcoded secrets detected'}

## Project Context
- Format: {pipeline_format} ({format_desc})
- Project: {project_description[:500]}
- Deployment Targets: {', '.join(deployment_targets)}
- Quality Gates: {quality_gates}
- All Justified Stages:
{stages_desc}

---

Produce a REVISED, COMPLETE pipeline specification that addresses every issue above.

Requirements:
1. Fix ALL critical issues listed above — none may remain
2. Add ALL missing sections with complete, non-placeholder content
3. Implement ALL missing stages with real commands
4. Replace any hardcoded secrets with proper {pipeline_format} secret syntax
5. Address all improvement suggestions
6. Keep all sections that were already correct and complete

Output the full revised specification using this exact Markdown structure:

## Pipeline Overview
## Trigger Conditions
## Environment Matrix
## Stage Definitions
## Artifact Management
## Secret Handling Strategy
## Rollback Procedures
## Notification Rules
## Complete Pipeline YAML
## Estimated Pipeline Duration
## Security Checklist

The Complete Pipeline YAML section MUST contain the full, syntactically valid {format_desc} YAML — do not truncate it.
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    content, error = call_resolved(messages, context, max_tokens=8000)
    if error:
        content, error = call_openai(messages, max_tokens=8000)
    if error:
        return None, error

    return {"output": content}, None


def step_5_local(inputs, context):
    """Write Pipeline Artifact to Storage."""
    improved_pipeline = context.get("improved_pipeline", "")
    generated_pipeline = context.get("generated_pipeline", "")

    final_content = improved_pipeline if improved_pipeline else generated_pipeline

    if not final_content or len(final_content.strip()) < 100:
        return None, "Pipeline specification is empty or too short to be valid."

    content_lower = final_content.lower()
    has_stages = any(kw in content_lower for kw in ["stage", "job", "step"])
    has_yaml = "yaml" in content_lower or ":" in final_content

    if not has_stages:
        return None, "Pipeline specification does not appear to contain any stage definitions."
    if not has_yaml:
        return None, "Pipeline specification does not appear to contain YAML content."

    return {"output": "artifact_written"}, None


STEP_HANDLERS = {
    "step_1": step_1_local,
    "step_2": step_2_llm,
    "step_3": step_3_critic,
    "step_4": step_4_llm,
    "step_5": step_5_local,
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