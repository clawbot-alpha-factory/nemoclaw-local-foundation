#!/usr/bin/env python3
"""
Skill ID: b05-bug-fix-impl
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
    model = context.get("resolved_model", "gpt-5.4-mini")
    if provider == "anthropic":
        return call_anthropic(messages, model=model, max_tokens=max_tokens)
    elif provider == "google":
        return call_google(messages, model=model, max_tokens=max_tokens)
    else:
        return call_openai(messages, model=model, max_tokens=max_tokens)


KNOWN_LANGUAGES = {
    "python", "javascript", "typescript", "java", "c", "c++", "c#", "go",
    "rust", "ruby", "php", "swift", "kotlin", "scala", "r", "bash", "shell",
    "sql", "html", "css", "unknown", "auto-detect",
}


def detect_language(code_snippet):
    """Heuristic language detection from code snippet."""
    snippet = code_snippet.lower()
    if "def " in snippet and ("import " in snippet or "print(" in snippet):
        return "Python"
    if "public class " in snippet or "public static void main" in snippet:
        return "Java"
    if "#include" in snippet or ("int main(" in snippet and "{" in snippet):
        return "C/C++"
    if "function " in snippet and ("const " in snippet or "let " in snippet or "var " in snippet):
        return "JavaScript"
    if "func " in snippet and ("fmt." in snippet or "package " in snippet):
        return "Go"
    if "fn " in snippet and "let " in snippet and "->" in snippet:
        return "Rust"
    if "<?php" in snippet:
        return "PHP"
    if "def " in snippet and snippet.count("end") >= 1 and "class " in snippet:
        return "Ruby"
    if "using " in snippet and "namespace " in snippet:
        return "C#"
    if "fun " in snippet and ("val " in snippet or "var " in snippet):
        return "Kotlin"
    return "Unknown"


def check_fix_structure(fix_text):
    """Check that the fix contains all required sections."""
    text_lower = fix_text.lower()
    required_sections = [
        (["root cause analysis", "root cause"], "root cause analysis"),
        (["before/after diff", "```diff", "--- before", "+++ after"], "before/after diff"),
        (["why the fix works", "why the fix", "how the fix works"], "explanation"),
        (["regression risk", "regression risk assessment"], "regression risk"),
        (["suggested test cases", "test cases", "test case"], "test cases"),
    ]
    results = {}
    for keywords, label in required_sections:
        found = any(kw in text_lower for kw in keywords)
        results[label] = found
    return results


def step_1_local(inputs, context):
    """Parse Bug Context and Build Fix Plan."""
    bug_description = inputs.get("bug_description", "").strip()
    affected_code_snippet = inputs.get("affected_code_snippet", "").strip()
    expected_behavior = inputs.get("expected_behavior", "").strip()
    actual_behavior = inputs.get("actual_behavior", "").strip()
    language = inputs.get("language", "auto-detect").strip()
    severity = inputs.get("severity", "medium").strip()

    errors = []
    if len(bug_description) < 20:
        errors.append("bug_description must be at least 20 characters.")
    if len(bug_description) > 2000:
        errors.append("bug_description must not exceed 2000 characters.")
    if len(affected_code_snippet) < 10:
        errors.append("affected_code_snippet must be at least 10 characters.")
    if len(affected_code_snippet) > 8000:
        errors.append("affected_code_snippet must not exceed 8000 characters.")
    if len(expected_behavior) < 10:
        errors.append("expected_behavior must be at least 10 characters.")
    if len(expected_behavior) > 1000:
        errors.append("expected_behavior must not exceed 1000 characters.")
    if len(actual_behavior) < 10:
        errors.append("actual_behavior must be at least 10 characters.")
    if len(actual_behavior) > 1000:
        errors.append("actual_behavior must not exceed 1000 characters.")
    if errors:
        return None, "; ".join(errors)

    if not language or language.lower() in ("auto-detect", ""):
        language = detect_language(affected_code_snippet)
    elif language.lower() not in KNOWN_LANGUAGES:
        language = detect_language(affected_code_snippet)

    valid_severities = {"low", "medium", "high", "critical"}
    if severity.lower() not in valid_severities:
        severity = "medium"
    else:
        severity = severity.lower()

    scope_boundaries = [
        "Fix ONLY the stated bug — do not refactor unrelated code.",
        "Do not rename variables, functions, or classes unless directly related to the bug.",
        "Do not add new features or improve performance unless it directly fixes the bug.",
        "Do not change code style, formatting, or comments unrelated to the fix.",
        "The diff must show only lines that change to fix the stated bug.",
        "Do not fabricate behavior not described in the bug report.",
        "Do not assume additional context beyond what is provided.",
    ]

    plan = {
        "bug_description": bug_description,
        "affected_code_snippet": affected_code_snippet,
        "expected_behavior": expected_behavior,
        "actual_behavior": actual_behavior,
        "language": language,
        "severity": severity,
        "scope_boundaries": scope_boundaries,
        "analysis_plan": [
            "1. Identify the root cause by tracing the discrepancy between expected and actual behavior.",
            "2. Locate the minimal set of lines responsible for the bug.",
            "3. Produce a unified diff showing only the changed lines.",
            "4. Explain why the change resolves the root cause.",
            "5. Assess regression risk: what existing behavior could break.",
            "6. Suggest targeted test cases that would catch this bug and prevent recurrence.",
        ],
    }

    return {"output": plan}, None


def step_2_llm(inputs, context):
    """Generate Targeted Bug Fix Implementation."""
    plan = context.get("step_1_output", {})
    if not plan:
        return None, "step_1_output is missing from context."

    bug_description = plan.get("bug_description", inputs.get("bug_description", ""))
    affected_code = plan.get("affected_code_snippet", inputs.get("affected_code_snippet", ""))
    expected = plan.get("expected_behavior", inputs.get("expected_behavior", ""))
    actual = plan.get("actual_behavior", inputs.get("actual_behavior", ""))
    language = plan.get("language", inputs.get("language", "Unknown"))
    severity = plan.get("severity", inputs.get("severity", "medium"))
    scope_boundaries = plan.get("scope_boundaries", [])

    scope_text = "\n".join(f"- {b}" for b in scope_boundaries)

    system_prompt = (
        "You are a senior software engineer specializing in precise, minimal bug fixes. "
        "You analyze root causes rigorously and produce targeted, minimal code changes. "
        "ANTI-FABRICATION RULES: "
        "(1) Only fix the exact bug described — never introduce unrelated changes. "
        "(2) Do not invent behavior, context, or constraints not stated in the bug report. "
        "(3) If the root cause cannot be determined from the provided snippet alone, state that explicitly. "
        "(4) The diff must contain ONLY lines that change to fix the stated bug — nothing else. "
        "(5) Do not rename, reformat, or restructure code beyond what is strictly necessary."
    )

    user_prompt = f"""Fix the following bug with a minimal, targeted change. Adhere strictly to these scope boundaries:
{scope_text}

## Bug Report

**Language:** {language}
**Severity:** {severity}

**Bug Description:**
{bug_description}

**Affected Code Snippet:**
```{language.lower()}
{affected_code}
```

**Expected Behavior:**
{expected}

**Actual Behavior:**
{actual}

## Required Output Format

Produce a structured bug fix report with ALL of the following sections in order:

## Root Cause Analysis
Explain the precise root cause of the bug. Trace the exact logic that causes the discrepancy between expected and actual behavior. Be specific — reference line numbers or variable names from the snippet where possible.

## Before/After Diff
Show a unified diff of ONLY the changed lines. Use standard unified diff format.

```diff
--- before
+++ after
@@ ... @@
 (unchanged context line)
-(removed line)
+(added line)
 (unchanged context line)
```

## Why the Fix Works
Explain clearly and specifically why the change resolves the root cause identified above. Reference the root cause analysis.

## Regression Risk Assessment
Assess what existing behavior could be affected by this change. Rate risk as Low / Medium / High and explain the reasoning. Identify any callers or dependents that may be affected.

## Suggested Test Cases
Provide at least 2 concrete test cases with explicit inputs and expected outputs that would catch this bug and prevent recurrence. Format each test case clearly.

CRITICAL: The diff must be minimal. Do not introduce any changes unrelated to fixing the stated bug."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    content, error = call_resolved(messages, context, max_tokens=6000)
    if error:
        content, error = call_openai(messages, model="gpt-5.4-mini", max_tokens=6000)
    if error:
        return None, error

    return {"output": content}, None


def step_3_critic(inputs, context):
    """Evaluate Fix Quality and Correctness."""
    generated_fix = context.get("improved_fix", context.get("generated_fix", ""))
    if not generated_fix:
        return None, "generated_fix is missing from context."

    plan = context.get("step_1_output", {})
    bug_description = plan.get("bug_description", inputs.get("bug_description", ""))
    affected_code = plan.get("affected_code_snippet", inputs.get("affected_code_snippet", ""))
    expected = plan.get("expected_behavior", inputs.get("expected_behavior", ""))
    actual = plan.get("actual_behavior", inputs.get("actual_behavior", ""))
    language = plan.get("language", inputs.get("language", "Unknown"))

    structure_checks = check_fix_structure(generated_fix)
    structural_score = int(sum(1 for v in structure_checks.values() if v) / len(structure_checks) * 10)

    system_prompt = (
        "You are a senior software engineering reviewer specializing in code correctness, "
        "minimal bug fixes, and regression safety. "
        "You evaluate bug fix reports with rigorous precision. "
        "ANTI-FABRICATION: Score based only on what is explicitly present in the fix report. "
        "Do not award credit for sections that are vague, missing, or do not address the stated bug. "
        "A fix that introduces unrelated changes must receive a low fix_correctness score regardless of other quality."
    )

    user_prompt = f"""Evaluate the following bug fix report on two dimensions. Return ONLY valid JSON with no markdown fences.

## Original Bug Context

**Language:** {language}
**Bug Description:**
{bug_description}

**Affected Code:**
```{language.lower()}
{affected_code}
```

**Expected Behavior:** {expected}
**Actual Behavior:** {actual}

## Bug Fix Report to Evaluate
{generated_fix}

## Evaluation Criteria

Score each dimension from 1-10:

1. **fix_correctness** (1-10): Does the fix actually address the stated root cause? Is the diff minimal and targeted with no unrelated changes? Does the explanation correctly and specifically justify the fix? Deduct heavily if the diff contains unrelated changes or if the root cause analysis is vague or incorrect.

2. **completeness_and_safety** (1-10): Are all five required sections present and substantive (Root Cause Analysis, Before/After Diff, Why the Fix Works, Regression Risk Assessment, Suggested Test Cases)? Is the regression risk assessment realistic and specific? Are the test cases concrete with explicit inputs and expected outputs? Would this fix prevent recurrence?

Also provide:
- **feedback**: Specific, actionable feedback identifying the weakest areas and exactly what must be improved (2-4 sentences).
- **critical_issues**: List of critical problems that MUST be fixed before this report is acceptable (empty list if none).
- **strengths**: What the fix does well (1-2 sentences).

Return ONLY this JSON structure:
{{
  "fix_correctness": <1-10>,
  "completeness_and_safety": <1-10>,
  "feedback": "<specific actionable feedback>",
  "critical_issues": ["<issue1>", "<issue2>"],
  "strengths": "<what the fix does well>"
}}"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    content, error = call_resolved(messages, context, max_tokens=2000)
    if error:
        content, error = call_openai(messages, model="gpt-5.4-mini", max_tokens=2000)
    if error:
        return None, error

    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
        cleaned = re.sub(r'\s*```$', '', cleaned)

    try:
        scores = json.loads(cleaned)
    except json.JSONDecodeError:
        scores = {
            "fix_correctness": 5,
            "completeness_and_safety": 5,
            "feedback": content[:500],
            "critical_issues": [],
            "strengths": "Unable to parse structured feedback.",
        }

    fix_correctness = max(1, min(10, int(scores.get("fix_correctness", 5))))
    completeness_and_safety = max(1, min(10, int(scores.get("completeness_and_safety", 5))))
    quality_score = min(structural_score, fix_correctness, completeness_and_safety)

    result = {
        "quality_score": quality_score,
        "structural_score": structural_score,
        "fix_correctness": fix_correctness,
        "completeness_and_safety": completeness_and_safety,
        "feedback": scores.get("feedback", ""),
        "critical_issues": scores.get("critical_issues", []),
        "strengths": scores.get("strengths", ""),
        "structure_checks": structure_checks,
    }

    return {"output": result}, None


def step_4_llm(inputs, context):
    """Improve Fix Based on Critic Feedback."""
    generated_fix = context.get("generated_fix", "")
    critic_output = context.get("fix_evaluation", {})

    if not generated_fix:
        return None, "generated_fix is missing from context."

    plan = context.get("step_1_output", {})
    bug_description = plan.get("bug_description", inputs.get("bug_description", ""))
    affected_code = plan.get("affected_code_snippet", inputs.get("affected_code_snippet", ""))
    expected = plan.get("expected_behavior", inputs.get("expected_behavior", ""))
    actual = plan.get("actual_behavior", inputs.get("actual_behavior", ""))
    language = plan.get("language", inputs.get("language", "Unknown"))
    scope_boundaries = plan.get("scope_boundaries", [])

    feedback = critic_output.get("feedback", "No specific feedback provided.")
    critical_issues = critic_output.get("critical_issues", [])
    quality_score = critic_output.get("quality_score", 5)
    structure_checks = critic_output.get("structure_checks", {})

    missing_sections = [section for section, present in structure_checks.items() if not present]
    scope_text = "\n".join(f"- {b}" for b in scope_boundaries)

    critical_text = ""
    if critical_issues:
        critical_text = "\n**Critical Issues to Fix:**\n" + "\n".join(f"- {issue}" for issue in critical_issues)

    missing_text = ""
    if missing_sections:
        missing_text = "\n**Missing Sections (MUST add):**\n" + "\n".join(f"- {s}" for s in missing_sections)

    system_prompt = (
        "You are a senior software engineer specializing in precise, minimal bug fixes. "
        "You analyze root causes rigorously and produce targeted, minimal code changes. "
        "ANTI-FABRICATION RULES: "
        "(1) Only fix the exact bug described — never introduce unrelated changes. "
        "(2) Do not invent behavior, context, or constraints not stated in the bug report. "
        "(3) The diff must contain ONLY lines that change to fix the stated bug — nothing else. "
        "(4) Do not rename, reformat, or restructure code beyond what is strictly necessary."
    )

    user_prompt = f"""You previously generated a bug fix report that received a quality score of {quality_score}/10. Revise it to address all feedback below.

## Scope Boundaries (MUST follow)
{scope_text}

## Original Bug Context

**Language:** {language}
**Bug Description:**
{bug_description}

**Affected Code:**
```{language.lower()}
{affected_code}
```

**Expected Behavior:** {expected}
**Actual Behavior:** {actual}

## Previous Fix (to be improved)
{generated_fix}

## Critic Feedback
{feedback}
{critical_text}
{missing_text}

## Instructions
Produce an improved bug fix report that:
1. Addresses every critical issue listed above — these are mandatory fixes
2. Adds any missing sections listed above with substantive content
3. Strengthens weak areas identified in the feedback with specific details
4. Maintains the minimal, targeted nature of the fix — do NOT introduce unrelated changes
5. Includes all five required sections with full content:
   - ## Root Cause Analysis (specific, references code lines/variables)
   - ## Before/After Diff (valid ```diff block with only changed lines)
   - ## Why the Fix Works (explicitly references the root cause)
   - ## Regression Risk Assessment (rated Low/Medium/High with reasoning)
   - ## Suggested Test Cases (at least 2 with explicit inputs and expected outputs)

Produce the complete improved bug fix report now."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    content, error = call_resolved(messages, context, max_tokens=6000)
    if error:
        content, error = call_openai(messages, model="gpt-5.4-mini", max_tokens=6000)
    if error:
        return None, error

    return {"output": content}, None


def step_5_local(inputs, context):
    """Write Bug Fix Artifact to Disk."""
    improved_fix = context.get("improved_fix", "")
    generated_fix = context.get("generated_fix", "")
    final_content = improved_fix if improved_fix else generated_fix

    if not final_content or not final_content.strip():
        return None, "No fix content available to write. Both improved_fix and generated_fix are empty."

    plan = context.get("step_1_output", {})
    bug_description = plan.get("bug_description", inputs.get("bug_description", ""))
    language = plan.get("language", inputs.get("language", "Unknown"))
    severity = plan.get("severity", inputs.get("severity", "medium"))

    critic_output = context.get("fix_evaluation", {})
    quality_score = critic_output.get("quality_score", "N/A")

    workflow_id = context.get("workflow_id", "unknown")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    storage_dir = "skills/b05-bug-fix-impl/outputs"
    os.makedirs(storage_dir, exist_ok=True)

    filename = f"b05-bug-fix-impl_{workflow_id}_{timestamp}.md"
    filepath = os.path.join(storage_dir, filename)

    header = f"""# Bug Fix Report

**Skill:** b05-bug-fix-impl
**Workflow ID:** {workflow_id}
**Generated:** {timestamp}
**Language:** {language}
**Severity:** {severity}
**Quality Score:** {quality_score}/10

**Bug Description:**
{bug_description}

---

"""

    full_content = header + final_content

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(full_content)
    except Exception as e:
        return None, f"Failed to write artifact: {e}"

    envelope_filename = f"b05-bug-fix-impl_{workflow_id}_{timestamp}_envelope.json"
    envelope_path = os.path.join(storage_dir, envelope_filename)

    envelope = {
        "skill_id": "b05-bug-fix-impl",
        "version": "1.0.0",
        "workflow_id": workflow_id,
        "timestamp": timestamp,
        "artifact_path": filepath,
        "language": language,
        "severity": severity,
        "quality_score": quality_score,
        "bug_description_preview": bug_description[:200],
    }

    try:
        with open(envelope_path, "w", encoding="utf-8") as f:
            json.dump(envelope, f, indent=2)
    except Exception as e:
        return None, f"Failed to write envelope: {e}"

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