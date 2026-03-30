#!/usr/bin/env python3
"""
Tier 3 Batch Skill Builder v1.0

Generates skills via meta-skills, applies known fixes automatically,
tests each skill, reports results.

Usage: python3 scripts/tier3-batch-build.py
"""

import json
import os
import re
import shutil
import subprocess
import sys
import time
import yaml
from pathlib import Path

REPO = Path.home() / "nemoclaw-local-foundation"
SKILLS_DIR = REPO / "skills"
PYTHON = str(REPO / ".venv313" / "bin" / "python3")
RUNNER = str(SKILLS_DIR / "skill-runner.py")
CHECKPOINT_DB = Path.home() / ".nemoclaw" / "checkpoints" / "langgraph.db"

# ═══════════════════════════════════════════════════════════════════════════════
# TIER 3 SKILL DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════════

TIER3_SKILLS = [
    {
        "skill_id": "a01-sys-context-mapper",
        "skill_name": "System Context Mapper",
        "family": "F01",
        "domain": "A",
        "tag": "internal",
        "concept": "A system context mapper that takes a system name, description, and known integrations. Produces a structured system context document with external actors (users, systems, services), data flows between actors and the system (direction, format, frequency), trust boundaries, system capabilities summary, constraints and assumptions, and a C4-style context narrative. Anti-fabrication: all actors and flows must be traceable to input description or marked as inferred.",
        "test_inputs": {
            "subsystem_name": "NemoClaw Skill Engine",
            "subsystem_concept": "A LangGraph-based skill execution engine that routes LLM calls through a 9-alias budget-enforced system, executes 5-step skill pipelines with critic loops, and writes markdown artifacts with JSON envelopes. Integrates with Anthropic, OpenAI, and Google APIs. Uses SQLite for checkpointing.",
            "boundaries": "Local MacBook runtime, no cloud deployment, API keys via .env file",
            "integration_context": "Connects to 3 LLM providers via LangChain wrappers, reads YAML skill specs, writes to local filesystem"
        },
    },
    {
        "skill_id": "a01-api-surface-designer",
        "skill_name": "API Surface Designer",
        "family": "F01",
        "domain": "A",
        "tag": "internal",
        "concept": "An API surface designer that takes a service description, target consumers, and design constraints. Produces a structured API specification with endpoint inventory (method, path, purpose), request/response schemas with field types, authentication and authorization model, error response taxonomy, rate limiting and pagination strategy, versioning approach, and backwards compatibility notes. Anti-fabrication: all endpoints must be traceable to stated service capabilities.",
        "test_inputs": {
            "subsystem_name": "Skill Execution API",
            "subsystem_concept": "A REST API that allows external clients to submit skill execution requests, check status, retrieve results, and manage skill configurations. Supports async execution with webhook callbacks. Must authenticate via API keys and enforce per-client rate limits.",
            "constraints": "Must support JSON request/response only, no GraphQL, max 100 requests per minute per client"
        },
    },
    {
        "skill_id": "b05-scaffold-gen",
        "skill_name": "Scaffold Generator",
        "family": "F05",
        "domain": "B",
        "tag": "internal",
        "concept": "A scaffold generator that takes a project type, language, framework, and feature requirements. Produces a complete project scaffold with directory structure, boilerplate files, configuration templates, dependency manifest, and setup instructions. Supports web-api, cli-tool, library, and microservice project types. Each generated file includes purpose comments. Anti-fabrication: only generates files appropriate for the stated stack.",
        "test_inputs": {
            "feature_spec": "A Python CLI tool that reads YAML configuration files, validates them against a JSON schema, and reports violations with line numbers and fix suggestions. Must support stdin piping and glob patterns for multiple files.",
            "language": "python",
            "integration_context": "Standalone CLI, no web framework, uses click for argument parsing and jsonschema for validation"
        },
    },
    {
        "skill_id": "b05-bug-fix-impl",
        "skill_name": "Bug Fix Implementer",
        "family": "F05",
        "domain": "B",
        "tag": "internal",
        "concept": "A bug fix implementer that takes a bug description, affected code snippet, expected behavior, and actual behavior. Produces a structured fix with root cause analysis, minimal code changes with before/after diff, explanation of why the fix works, regression risk assessment, and suggested test cases to prevent recurrence. Anti-fabrication: fix must address only the stated bug without introducing unrelated changes.",
        "test_inputs": {
            "feature_spec": "Bug: the extract_section function matches H1 headings when it should only match H2. The regex uses ##? which matches both # and ##. Expected: only match ## headings. Actual: also matches # document title, returning wrong section content.",
            "language": "python",
            "integration_context": "Part of a markdown processing pipeline in a skill validation system"
        },
    },
    {
        "skill_id": "c07-api-doc-gen",
        "skill_name": "API Documentation Generator",
        "family": "F07",
        "domain": "C",
        "tag": "dual-use",
        "concept": "An API documentation generator that takes an API specification or endpoint descriptions and target audience. Produces structured API documentation with endpoint reference (method, path, description, parameters, request/response examples), authentication guide, error handling reference, rate limiting documentation, quick start guide with curl examples, and SDK usage patterns. Anti-fabrication: all examples must be consistent with the stated API specification.",
        "test_inputs": {
            "system_description": "A REST API for managing AI skill executions. Endpoints: POST /skills/run (submit execution), GET /skills/status/{id} (check status), GET /skills/result/{id} (get result), GET /skills (list available skills). Auth via X-API-Key header. Returns JSON. Rate limited to 60 requests per minute.",
            "target_environment": "Developer documentation for external API consumers using Python or curl",
            "audience": "developer"
        },
    },
    {
        "skill_id": "c07-decision-record-writer",
        "skill_name": "Decision Record Writer",
        "family": "F07",
        "domain": "C",
        "tag": "internal",
        "concept": "A decision record writer that takes a decision title, context, and options considered. Produces a structured ADR (Architecture Decision Record) with status, context and problem statement, decision drivers, options considered with pros and cons, chosen option with justification, consequences (positive, negative, neutral), compliance notes, and review date. Format follows Michael Nygard ADR template. Anti-fabrication: consequences must be logically derived from the chosen option.",
        "test_inputs": {
            "system_description": "Decision: Route all LLM calls through a budget-enforced proxy instead of direct API calls. Context: Need cost control across 3 providers (Anthropic, OpenAI, Google) with per-provider spending limits. Options: direct API calls with manual tracking, centralized budget proxy, per-skill cost limits.",
            "target_environment": "Internal architecture decision records for the NemoClaw skill system",
            "audience": "developer"
        },
    },
    {
        "skill_id": "b06-cicd-designer",
        "skill_name": "CI/CD Pipeline Designer",
        "family": "F06",
        "domain": "B",
        "tag": "dual-use",
        "concept": "A CI/CD pipeline designer that takes a project description, deployment targets, and quality gates. Produces a structured pipeline specification with stages (lint, test, build, deploy), trigger conditions, environment matrix, artifact management, secret handling strategy, rollback procedures, notification rules, and estimated pipeline duration. Supports GitHub Actions, GitLab CI, and generic YAML formats. Anti-fabrication: all stages must be justified by project requirements.",
        "test_inputs": {
            "feature_spec": "Design a GitHub Actions CI/CD pipeline for a Python LangGraph application. Quality gates: linting with ruff, type checking with mypy, unit tests with pytest, integration test that runs one skill end-to-end. Deploy target: none yet, just validation. Secrets: API keys for Anthropic, OpenAI, Google stored in GitHub Secrets.",
            "language": "yaml",
            "integration_context": "GitHub Actions, Python 3.12, pip dependencies, no Docker build needed"
        },
    },
    {
        "skill_id": "b06-release-notes-gen",
        "skill_name": "Release Notes Generator",
        "family": "F06",
        "domain": "B",
        "tag": "dual-use",
        "concept": "A release notes generator that takes git commit history, version number, and audience type. Produces structured release notes with version header, summary of changes, categorized sections (features, fixes, improvements, breaking changes), migration notes if applicable, known issues, and contributor acknowledgments. Anti-fabrication: all listed changes must be traceable to provided commit messages.",
        "test_inputs": {
            "feature_spec": "Generate release notes for v2.0.0 from these commits: feat: add 10 Tier 2 skills with meta-skill automation; fix: reroute premium from Opus to Sonnet saving 5x cost; feat: regression test suite with 20/20 passing; fix: checkpoint DB backup before every run; feat: skill chaining via --input-from validated; fix: Path B external review improvements applied. Audience: developers using the skill system.",
            "language": "markdown",
            "integration_context": "Internal project release notes for the NemoClaw skill system"
        },
    },
    {
        "skill_id": "e08-meeting-summary-gen",
        "skill_name": "Meeting Summary Generator",
        "family": "F08",
        "domain": "E",
        "tag": "dual-use",
        "concept": "A meeting summary generator that takes meeting transcript or notes, attendees, and meeting type. Produces a structured summary with key decisions made, action items with owners and deadlines, discussion topics with outcomes, open questions, follow-up meetings needed, and executive summary. Supports standup, planning, review, and general meeting types. Anti-fabrication: all decisions and action items must be traceable to transcript content.",
        "test_inputs": {
            "competitor_data": "Meeting notes: Discussed Q3 roadmap priorities. Sarah proposed focusing on API stability over new features. John disagreed, wants to ship 3 new integrations by end of Q3. Team voted 4-2 in favor of stability-first approach. Action: Sarah to draft stability roadmap by Friday. John to identify which integrations can wait until Q4. Next review meeting scheduled for July 15.",
            "focus_company": "Internal Engineering Team",
            "industry_context": "Weekly engineering leadership meeting for a SaaS startup"
        },
    },
    {
        "skill_id": "e08-kb-article-writer",
        "skill_name": "Knowledge Base Article Writer",
        "family": "F08",
        "domain": "E",
        "tag": "dual-use",
        "concept": "A knowledge base article writer that takes a topic, target audience, and source material. Produces a structured KB article with clear title, problem statement, step-by-step solution, troubleshooting tips, related articles suggestions, and metadata tags. Supports how-to, troubleshooting, reference, and conceptual article types. Anti-fabrication: all solutions must be grounded in provided source material.",
        "test_inputs": {
            "competitor_data": "Topic: How to add a new skill to the NemoClaw system. Source: Use g26-skill-spec-writer to generate the spec, then g26-skill-template-gen for the code. Deploy files to skills/skill-id/ directory. Run skill-runner.py to test. Fix any context key mismatches. Ensure step_3 and step_4 have cached:false. Run validate.py for 31/31. Commit with descriptive message.",
            "focus_company": "NemoClaw Documentation",
            "industry_context": "Internal knowledge base for developers using the NemoClaw skill system"
        },
    },
]


def generate_spec(skill):
    """Generate skill.yaml via g26-skill-spec-writer."""
    if CHECKPOINT_DB.exists():
        shutil.copy2(CHECKPOINT_DB, str(CHECKPOINT_DB) + ".bak")
    
    cmd = [PYTHON, RUNNER, "--skill", "g26-skill-spec-writer",
           "--input", "skill_concept", skill["concept"],
           "--input", "skill_name", skill["skill_name"],
           "--input", "skill_id", skill["skill_id"],
           "--input", "family", skill["family"],
           "--input", "domain", skill["domain"],
           "--input", "tag", skill["tag"]]
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=str(REPO))
    if "Skill complete" not in (result.stdout + result.stderr):
        return None, result.stdout + result.stderr
    
    # Find latest spec output
    outputs = sorted(Path(SKILLS_DIR / "g26-skill-spec-writer" / "outputs").glob("*.md"), key=os.path.getmtime)
    if not outputs:
        return None, "No spec output found"
    
    with open(outputs[-1]) as f:
        return f.read(), None


def generate_code(spec_content):
    """Generate run.py via g26-skill-template-gen."""
    if CHECKPOINT_DB.exists():
        shutil.copy2(CHECKPOINT_DB, str(CHECKPOINT_DB) + ".bak")
    
    cmd = [PYTHON, RUNNER, "--skill", "g26-skill-template-gen",
           "--input", "skill_yaml", spec_content]
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=str(REPO))
    if "Skill complete" not in (result.stdout + result.stderr):
        return None, result.stdout + result.stderr
    
    outputs = sorted(Path(SKILLS_DIR / "g26-skill-template-gen" / "outputs").glob("*.md"), key=os.path.getmtime)
    if not outputs:
        return None, "No code output found"
    
    with open(outputs[-1]) as f:
        return f.read(), None


def apply_known_fixes(skill_id, spec_content, code_content):
    """Apply all known integration fixes from Tier 2 experience."""
    fixes = []
    
    # Parse YAML to get output_keys
    try:
        spec = yaml.safe_load(spec_content)
        output_keys = {}
        for step in spec.get("steps", []):
            output_keys[step["id"]] = step.get("output_key", step["id"] + "_output")
    except:
        output_keys = {}
    
    # FIX 1: Context key mismatches — replace step_2_output with actual output_key
    step2_key = output_keys.get("step_2", "generated_output")
    if "step_2_output" in code_content and step2_key != "step_2_output":
        code_content = code_content.replace("step_2_output", step2_key)
        fixes.append(f"context key: step_2_output → {step2_key}")
    
    step4_key = output_keys.get("step_4", "improved_output")
    if "step_4_output" in code_content and step4_key != "step_4_output":
        code_content = code_content.replace("step_4_output", step4_key)
        fixes.append(f"context key: step_4_output → {step4_key}")
    
    # FIX 2: Cache on step_3/step_4 — must be false
    for key in output_keys.values():
        old = f"    output_key: {key}\n    idempotency:\n      rerunnable: true\n      cached: true"
        new = f"    output_key: {key}\n    idempotency:\n      rerunnable: true\n      cached: false"
        if old in spec_content and key in [output_keys.get("step_3", ""), output_keys.get("step_4", "")]:
            spec_content = spec_content.replace(old, new)
            fixes.append(f"uncached: {key}")
    
    # FIX 3: step_3 should read improved version first
    step2_ok = output_keys.get("step_2", "generated_output")
    step4_ok = output_keys.get("step_4", "improved_output")
    
    # Pattern: context.get("generated_X", "") → context.get("improved_X", context.get("generated_X", ""))
    old_pattern = f'context.get("{step2_ok}", "")'
    new_pattern = f'context.get("{step4_ok}", context.get("{step2_ok}", ""))'
    
    # Only replace in step_3 function, not everywhere
    step3_idx = code_content.find("def step_3")
    step4_idx = code_content.find("def step_4")
    if step3_idx >= 0 and step4_idx >= 0:
        step3_code = code_content[step3_idx:step4_idx]
        # Only fix the first occurrence in step_3 (the main input read)
        if old_pattern in step3_code:
            fixed_step3 = step3_code.replace(old_pattern, new_pattern, 1)
            code_content = code_content[:step3_idx] + fixed_step3 + code_content[step4_idx:]
            fixes.append(f"step_3 reads {step4_ok} first")
    
    return spec_content, code_content, fixes


def deploy_skill(skill_id, spec_content, code_content):
    """Write files to skills directory."""
    skill_dir = SKILLS_DIR / skill_id
    skill_dir.mkdir(exist_ok=True)
    (skill_dir / "outputs").mkdir(exist_ok=True)
    
    with open(skill_dir / "outputs" / ".gitignore", "w") as f:
        f.write("*\n!.gitignore\n")
    
    with open(skill_dir / "skill.yaml", "w") as f:
        f.write(spec_content)
    
    with open(skill_dir / "run.py", "w") as f:
        f.write(code_content)


def test_skill(skill_id, test_inputs):
    """Run skill with test inputs."""
    if CHECKPOINT_DB.exists():
        CHECKPOINT_DB.unlink()
    
    cmd = [PYTHON, RUNNER, "--skill", skill_id]
    for key, value in test_inputs.items():
        cmd.extend(["--input", key, str(value)])
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600, cwd=str(REPO))
    output = result.stdout + result.stderr
    
    if "Skill complete" in output:
        return True, None
    else:
        # Extract error
        for line in output.split("\n"):
            if '"error"' in line or "ERROR:" in line:
                return False, line.strip()[:200]
        return False, output.strip().split("\n")[-1][:200]


def create_test_input(skill_id, test_inputs):
    """Write test-input.json for regression suite."""
    path = SKILLS_DIR / skill_id / "test-input.json"
    with open(path, "w") as f:
        json.dump({"skill_id": skill_id, "inputs": test_inputs}, f, indent=2)


def main():
    print("=" * 60)
    print("  Tier 3 Batch Skill Builder v1.0")
    print(f"  {len(TIER3_SKILLS)} skills to build")
    print("=" * 60)
    print()
    
    results = []
    
    for i, skill in enumerate(TIER3_SKILLS, 1):
        sid = skill["skill_id"]
        print(f"[{i}/{len(TIER3_SKILLS)}] {sid}")
        print(f"  Generating spec...", end="", flush=True)
        
        start = time.time()
        spec, err = generate_spec(skill)
        if not spec:
            print(f" FAILED ({err[:100]})")
            results.append(("SPEC_FAIL", sid, 0, err))
            continue
        print(f" OK ({int(time.time()-start)}s)")
        
        print(f"  Generating code...", end="", flush=True)
        start = time.time()
        code, err = generate_code(spec)
        if not code:
            print(f" FAILED ({err[:100]})")
            results.append(("CODE_FAIL", sid, 0, err))
            continue
        print(f" OK ({int(time.time()-start)}s)")
        
        print(f"  Applying known fixes...", end="", flush=True)
        spec, code, fixes = apply_known_fixes(sid, spec, code)
        print(f" {len(fixes)} fixes")
        for fix in fixes:
            print(f"    - {fix}")
        
        # Compile check
        try:
            deploy_skill(sid, spec, code)
            import py_compile
            py_compile.compile(str(SKILLS_DIR / sid / "run.py"), doraise=True)
        except Exception as e:
            print(f"  COMPILE FAILED: {e}")
            results.append(("COMPILE_FAIL", sid, 0, str(e)))
            continue
        
        create_test_input(sid, skill["test_inputs"])
        
        print(f"  Testing...", end="", flush=True)
        start = time.time()
        passed, err = test_skill(sid, skill["test_inputs"])
        elapsed = int(time.time() - start)
        
        if passed:
            print(f" ✅ PASS ({elapsed}s)")
            results.append(("PASS", sid, elapsed, None))
        else:
            print(f" ❌ FAIL ({elapsed}s)")
            print(f"    {err}")
            results.append(("FAIL", sid, elapsed, err))
        
        print()
    
    # Summary
    print("=" * 60)
    passed = sum(1 for r in results if r[0] == "PASS")
    failed = len(results) - passed
    print(f"  Results: {passed} passed  {failed} failed")
    print("=" * 60)
    for status, sid, elapsed, err in results:
        if status == "PASS":
            print(f"  ✅ {sid} ({elapsed}s)")
        else:
            print(f"  ❌ {sid} — {status}: {err[:80] if err else ''}")
    
    # Write results
    with open(REPO / "scripts" / "tier3-batch-results.json", "w") as f:
        json.dump({"results": [{"status": s, "skill": sid, "elapsed": e, "error": err} 
                               for s, sid, e, err in results]}, f, indent=2)
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
