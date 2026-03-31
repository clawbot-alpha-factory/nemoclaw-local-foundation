#!/usr/bin/env python3
"""
Skill ID: b06-release-notes-gen
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
        llm = ChatGoogleGenerativeAI(model=model, max_output_tokens=max_tokens, google_api_key=api_key)
        lc = [SystemMessage(content=m["content"]) if m["role"] == "system"
              else HumanMessage(content=m["content"]) for m in messages]
        return llm.invoke(lc).content, None
    except Exception as e:
        return None, str(e)


def call_resolved(messages, context, max_tokens=4000):
    try:
        provider = context.get("resolved_provider", __import__("lib.routing", fromlist=["resolve_alias"]).resolve_alias("moderate")[0])
        model = context.get("resolved_model", "gpt-5.4-mini")
        if provider == "anthropic":
            return call_anthropic(messages, model=model, max_tokens=max_tokens)
        elif provider == "google":
            return call_google(messages, model=model, max_tokens=max_tokens)
        else:
            return call_openai(messages, model=model, max_tokens=max_tokens)
    except Exception as e:
        return None, str(e)


# --- Deterministic helpers ---

CONVENTIONAL_PREFIXES = {
    "feat": "features",
    "feature": "features",
    "fix": "bug_fixes",
    "bugfix": "bug_fixes",
    "bug": "bug_fixes",
    "hotfix": "bug_fixes",
    "refactor": "improvements",
    "refact": "improvements",
    "perf": "improvements",
    "improve": "improvements",
    "improvement": "improvements",
    "chore": "chores",
    "docs": "chores",
    "style": "chores",
    "test": "chores",
    "ci": "chores",
    "build": "chores",
    "revert": "chores",
    "breaking": "breaking_changes",
}

CATEGORY_SECTION_KEYWORDS = [
    "feature", "bug fix", "fix", "improvement", "breaking change",
    "migration", "known issue", "chore", "what's new",
]


def parse_commits(commit_history):
    """Parse raw commit history into structured list of commit dicts."""
    commits = []
    if not commit_history or not commit_history.strip():
        return commits
    lines = commit_history.strip().splitlines()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 2)
        commit = {"raw": line, "hash": "", "author": "", "message": line, "category": "chores"}
        if len(parts) >= 1:
            if re.match(r'^[0-9a-f]{7,40}$', parts[0], re.IGNORECASE):
                commit["hash"] = parts[0]
                if len(parts) >= 2:
                    commit["message"] = " ".join(parts[1:])
            else:
                commit["message"] = line

        msg = commit["message"]
        try:
            prefix_match = re.match(r'^(\w+)(?:\([^)]*\))?[!:]?\s*', msg, re.IGNORECASE)
            if prefix_match:
                prefix = prefix_match.group(1).lower()
                if prefix in CONVENTIONAL_PREFIXES:
                    commit["category"] = CONVENTIONAL_PREFIXES[prefix]
        except Exception:
            pass

        if "BREAKING CHANGE" in msg or "breaking change" in msg.lower():
            commit["category"] = "breaking_changes"
        try:
            if re.match(r'^\w+!:', msg):
                commit["category"] = "breaking_changes"
        except Exception:
            pass

        try:
            author_match = re.search(r'\(([^)]+)\)\s*$', msg)
            if author_match:
                commit["author"] = author_match.group(1).strip()
            else:
                by_match = re.search(r'\bby\s+(@?\w[\w.-]*)', msg, re.IGNORECASE)
                if by_match:
                    commit["author"] = by_match.group(1).strip()
        except Exception:
            pass

        commits.append(commit)
    return commits


def check_required_sections_present(text):
    """Check that the release notes contain required structural sections."""
    if not text:
        return {
            "version_header": False,
            "summary": False,
            "categorized_section": False,
            "contributors": False,
        }, 0.0
    text_lower = text.lower()
    checks = {
        "version_header": bool(re.search(r'#\s*(release|version|v\d)', text_lower)),
        "summary": (
            "summary" in text_lower
            or "overview" in text_lower
            or "what's new" in text_lower
            or "whats new" in text_lower
        ),
        "categorized_section": any(kw in text_lower for kw in CATEGORY_SECTION_KEYWORDS),
        "contributors": (
            "contributor" in text_lower
            or "acknowledgment" in text_lower
            or "thanks" in text_lower
            or "thank you" in text_lower
        ),
    }
    score = sum(1 for v in checks.values() if v) / len(checks)
    return checks, score


def check_traceability(text, commits):
    """Check that changes mentioned in release notes are traceable to commits."""
    if not commits:
        return 1.0, []
    commit_words = set()
    for c in commits:
        try:
            words = re.findall(r'\b\w{4,}\b', c["message"].lower())
            commit_words.update(words)
        except Exception:
            pass

    bullet_lines = re.findall(r'^\s*[-*•]\s+(.+)$', text, re.MULTILINE)
    if not bullet_lines:
        return 1.0, []

    traceable = 0
    untraceable = []
    for bl in bullet_lines:
        try:
            bl_words = set(re.findall(r'\b\w{4,}\b', bl.lower()))
            overlap = bl_words & commit_words
            if overlap:
                traceable += 1
            else:
                untraceable.append(bl)
        except Exception:
            traceable += 1

    ratio = traceable / len(bullet_lines) if bullet_lines else 1.0
    return ratio, untraceable


# --- Step handlers ---

def step_1_local(inputs, context):
    """Parse Commits and Build Generation Plan."""
    commit_history = inputs.get("commit_history", "").strip()
    version_number = inputs.get("version_number", "").strip()
    audience_type = inputs.get("audience_type", "developers").strip()
    product_name = inputs.get("product_name", "").strip()
    previous_version = inputs.get("previous_version", "").strip()
    known_issues = inputs.get("known_issues", "").strip()

    if not commit_history:
        return None, "commit_history is required and cannot be empty."
    if len(commit_history) < 20:
        return None, "commit_history is too short (minimum 20 characters)."
    if not version_number:
        return None, "version_number is required and cannot be empty."
    if len(version_number) < 3:
        return None, "version_number is too short (minimum 3 characters)."
    if audience_type not in ("developers", "end-users", "internal", "mixed"):
        return None, f"audience_type must be one of: developers, end-users, internal, mixed. Got: {audience_type}"

    commits = parse_commits(commit_history)
    if not commits:
        return None, "Could not parse any commits from commit_history."

    categories = {
        "features": [],
        "bug_fixes": [],
        "improvements": [],
        "breaking_changes": [],
        "chores": [],
    }
    authors = set()
    for c in commits:
        cat = c.get("category", "chores")
        if cat not in categories:
            cat = "chores"
        categories[cat].append(c["message"])
        if c.get("author"):
            authors.add(c["author"])

    tone_guidance = {
        "developers": "Use technical language, include API changes, reference commit hashes where helpful, detail migration steps precisely.",
        "end-users": "Use plain language, focus on user-visible changes, avoid internal jargon, emphasize benefits.",
        "internal": "Include all technical details, internal ticket references, deployment notes, and team-specific context.",
        "mixed": "Balance technical accuracy with accessible language. Provide a high-level summary followed by technical details.",
    }

    plan = {
        "version_number": version_number,
        "product_name": product_name,
        "previous_version": previous_version,
        "audience_type": audience_type,
        "tone_guidance": tone_guidance.get(audience_type, tone_guidance["developers"]),
        "known_issues": known_issues,
        "commit_count": len(commits),
        "categories": categories,
        "authors": sorted(authors),
        "has_breaking_changes": len(categories.get("breaking_changes", [])) > 0,
        "has_known_issues": bool(known_issues),
        "raw_commits": [c["message"] for c in commits],
    }

    return {"output": plan}, None


def step_2_llm(inputs, context):
    """Generate Structured Release Notes Document."""
    plan = context.get("step_1_output", {})
    if not plan:
        return None, "step_1_output is missing from context."

    version_number = plan.get("version_number", "")
    product_name = plan.get("product_name", "")
    previous_version = plan.get("previous_version", "")
    audience_type = plan.get("audience_type", "developers")
    tone_guidance = plan.get("tone_guidance", "")
    known_issues = plan.get("known_issues", "")
    categories = plan.get("categories", {})
    authors = plan.get("authors", [])
    raw_commits = plan.get("raw_commits", [])
    has_breaking_changes = plan.get("has_breaking_changes", False)

    product_label = product_name if product_name else "Project"
    version_context = (
        f"from {previous_version} to {version_number}" if previous_version
        else f"version {version_number}"
    )

    categories_text = ""
    for cat, items in categories.items():
        if items:
            cat_label = cat.replace("_", " ").title()
            categories_text += f"\n{cat_label}:\n"
            for item in items:
                categories_text += f"  - {item}\n"

    authors_text = ", ".join(authors) if authors else "See commit history"
    known_issues_text = known_issues if known_issues else "None reported."

    system_prompt = (
        "You are a senior technical writer and release engineer specializing in developer-facing "
        "and end-user release documentation. You produce clear, accurate, and well-structured "
        "release notes in Markdown format that faithfully reflect only the changes present in the "
        "provided commit history. You never fabricate or invent changes not present in the commits."
    )

    user_prompt = f"""Generate complete, structured release notes in Markdown format for the following release.

RELEASE DETAILS:
- Product: {product_label}
- Version: {version_number}
- Version context: {version_context}
- Audience: {audience_type}
- Tone guidance: {tone_guidance}

CATEGORIZED COMMITS (use ONLY these — do not fabricate changes):
{categories_text}

ALL RAW COMMITS (for reference and traceability):
{chr(10).join(f'- {c}' for c in raw_commits)}

KNOWN ISSUES (include verbatim if provided):
{known_issues_text}

CONTRIBUTORS:
{authors_text}

REQUIRED DOCUMENT STRUCTURE (use these exact headings):
1. # {product_label} {version_number} Release Notes  (H1 version header)
2. ## Summary  (2-4 sentence executive overview of this release)
3. ## What's New / Features  (only if there are feature commits)
4. ## Bug Fixes  (only if there are bug fix commits)
5. ## Improvements  (only if there are improvement/refactor commits)
6. ## Breaking Changes  (only if breaking changes exist — include migration instructions)
7. ## Migration Guide  (only if breaking changes exist — step-by-step upgrade instructions)
8. ## Known Issues  (always include; use provided content or "None reported.")
9. ## Contributors  (list all identified contributors; if none detected, acknowledge the team)

RULES:
- Every listed change MUST be traceable to a provided commit message. Do NOT invent changes.
- Omit sections that have no relevant commits (except Summary, Known Issues, Contributors).
- Audience is {audience_type}: {tone_guidance}
- Use clear, concise bullet points for individual changes.
- If breaking changes exist, the Migration Guide MUST provide actionable steps.
- Do not include internal implementation details unless audience is "developers" or "internal".
- Output ONLY the Markdown document. No preamble, no explanation, no code fences."""

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
    """Evaluate Release Notes Quality and Traceability."""
    release_notes = context.get("improved_release_notes", context.get("generated_release_notes", ""))
    plan = context.get("step_1_output", {})

    if not release_notes:
        return None, "generated_release_notes is missing from context."

    raw_commits = plan.get("raw_commits", [])
    has_breaking_changes = plan.get("has_breaking_changes", False)

    # --- Deterministic layer ---
    section_checks, section_score_raw = check_required_sections_present(release_notes)
    structural_score = int(round(section_score_raw * 10))

    breaking_ok = True
    if has_breaking_changes:
        breaking_ok = "breaking change" in release_notes.lower()
        if not breaking_ok:
            structural_score = max(0, structural_score - 2)

    commits_for_check = [{"message": c} for c in raw_commits]
    traceability_ratio, untraceable_items = check_traceability(release_notes, commits_for_check)
    traceability_score = int(round(traceability_ratio * 10))

    structural_score = min(10, max(0, structural_score))
    traceability_score = min(10, max(0, traceability_score))

    deterministic_issues = []
    if not section_checks.get("version_header"):
        deterministic_issues.append("Missing version header (H1 with version number or 'Release' keyword).")
    if not section_checks.get("summary"):
        deterministic_issues.append("Missing Summary section.")
    if not section_checks.get("categorized_section"):
        deterministic_issues.append("Missing at least one categorized change section (Features, Bug Fixes, etc.).")
    if not section_checks.get("contributors"):
        deterministic_issues.append("Missing Contributors section.")
    if has_breaking_changes and not breaking_ok:
        deterministic_issues.append("Breaking changes detected in commits but no Breaking Changes section found.")
    if untraceable_items:
        deterministic_issues.append(
            f"Potentially fabricated items (not traceable to commits): {untraceable_items[:3]}"
        )

    # --- LLM critic layer ---
    system_prompt = (
        "You are a senior technical writer and release engineer. You evaluate release notes "
        "documents for clarity, completeness, and traceability to the original commit history. "
        "You return structured JSON assessments only."
    )

    user_prompt = f"""Evaluate the following release notes document on two dimensions. Return ONLY valid JSON.

RELEASE NOTES TO EVALUATE:
{release_notes}

ORIGINAL COMMIT MESSAGES (ground truth — all listed changes must trace to these):
{chr(10).join(f'- {c}' for c in raw_commits)}

DETERMINISTIC ISSUES ALREADY FOUND:
{json.dumps(deterministic_issues)}

Evaluate on these two dimensions (score 1-10 each):

1. clarity_score (1-10): Are the release notes clear, well-organized, and appropriate for the intended audience?
   - 9-10: Excellent clarity, professional tone, well-structured with logical flow
   - 7-8: Good clarity with minor issues (e.g., slight tone mismatch, minor formatting)
   - 5-6: Acceptable but has clarity or tone problems affecting readability
   - 1-4: Confusing, poorly structured, wrong tone, or hard to follow

2. completeness_score (1-10): Do the release notes cover all significant changes from the commits without fabrication?
   - 9-10: All significant changes covered accurately, nothing fabricated
   - 7-8: Most changes covered, minor omissions or slight over-generalization
   - 5-6: Some changes missing, unclear categorization, or minor fabrication
   - 1-4: Major omissions, significant fabricated content, or commits ignored

Also provide:
- feedback: A list of specific, actionable improvement suggestions (max 5 items). Each suggestion must be concrete and reference a specific problem.
- fabrication_risk: "low" if all listed changes clearly map to commits, "medium" if some items are vague or loosely connected, "high" if items appear invented.

Return ONLY this JSON structure (no markdown fences, no explanation):
{{
  "clarity_score": <int 1-10>,
  "completeness_score": <int 1-10>,
  "feedback": ["<specific suggestion 1>", "<specific suggestion 2>", ...],
  "fabrication_risk": "<low|medium|high>"
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

    try:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
            cleaned = re.sub(r'\s*```$', '', cleaned)
        scores = json.loads(cleaned)
    except Exception as e:
        return None, f"Failed to parse critic JSON: {e}. Raw: {content[:300]}"

    clarity_score = min(10, max(1, int(scores.get("clarity_score", 5))))
    completeness_score = min(10, max(1, int(scores.get("completeness_score", 5))))
    feedback = scores.get("feedback", [])
    fabrication_risk = scores.get("fabrication_risk", "medium")

    if fabrication_risk == "high":
        traceability_score = min(traceability_score, 4)
    elif fabrication_risk == "medium":
        traceability_score = min(traceability_score, 7)

    quality_score = min(structural_score, clarity_score, completeness_score, traceability_score)

    critic_output = {
        "quality_score": quality_score,
        "structural_score": structural_score,
        "clarity_score": clarity_score,
        "completeness_score": completeness_score,
        "traceability_score": traceability_score,
        "fabrication_risk": fabrication_risk,
        "deterministic_issues": deterministic_issues,
        "feedback": feedback,
        "section_checks": section_checks,
    }

    return {"output": critic_output}, None


def step_4_llm(inputs, context):
    """Improve Release Notes Based on Critic Feedback."""
    original_notes = context.get("generated_release_notes", "")
    critic_output = context.get("critic_evaluation", {})
    plan = context.get("step_1_output", {})

    if not original_notes:
        return None, "generated_release_notes is missing from context."
    if not critic_output:
        return None, "critic_evaluation is missing from context."

    feedback = critic_output.get("feedback", [])
    deterministic_issues = critic_output.get("deterministic_issues", [])
    quality_score = critic_output.get("quality_score", 5)
    fabrication_risk = critic_output.get("fabrication_risk", "low")

    raw_commits = plan.get("raw_commits", [])
    audience_type = plan.get("audience_type", "developers")
    tone_guidance = plan.get("tone_guidance", "")
    version_number = plan.get("version_number", "")
    product_name = plan.get("product_name", "")
    known_issues = plan.get("known_issues", "")
    authors = plan.get("authors", [])
    has_breaking_changes = plan.get("has_breaking_changes", False)

    all_issues = deterministic_issues + feedback
    issues_text = (
        "\n".join(f"- {issue}" for issue in all_issues)
        if all_issues
        else "- General quality improvement needed."
    )

    fabrication_instruction = (
        "CRITICAL: Remove any changes not traceable to the commits listed below."
        if fabrication_risk in ("medium", "high")
        else "Maintain strict traceability — only list changes present in the commits."
    )

    system_prompt = (
        "You are a senior technical writer and release engineer specializing in developer-facing "
        "and end-user release documentation. You revise release notes to address specific quality "
        "issues while maintaining strict traceability to the original commit history. "
        "You never fabricate or invent changes not present in the provided commits."
    )

    user_prompt = f"""Revise the following release notes to address all identified issues. Return ONLY the improved Markdown document.

ORIGINAL RELEASE NOTES:
{original_notes}

ISSUES TO ADDRESS:
{issues_text}

QUALITY SCORE (current): {quality_score}/10 — improvement required.
FABRICATION RISK: {fabrication_risk} — {fabrication_instruction}

GROUND TRUTH COMMITS (only these changes may be listed — do not invent others):
{chr(10).join(f'- {c}' for c in raw_commits)}

AUDIENCE: {audience_type}
TONE: {tone_guidance}
VERSION: {version_number}
PRODUCT: {product_name if product_name else "Project"}
KNOWN ISSUES: {known_issues if known_issues else "None reported."}
CONTRIBUTORS: {", ".join(authors) if authors else "See commit history"}
HAS BREAKING CHANGES: {has_breaking_changes}

REVISION RULES:
1. Fix ALL issues listed above — address each one explicitly.
2. Do NOT add any changes not present in the ground truth commits.
3. Ensure all required sections are present: H1 version header, ## Summary, at least one change section, ## Known Issues, ## Contributors.
4. If breaking changes exist, ensure ## Breaking Changes and ## Migration Guide sections are present with actionable steps.
5. Maintain appropriate tone and depth for {audience_type} audience: {tone_guidance}
6. Use clear, concise bullet points for individual changes.
7. Output ONLY the complete revised Markdown document. No preamble, no explanation, no code fences."""

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
    """Write Final Release Notes Artifact."""
    improved = context.get("improved_release_notes", "")
    generated = context.get("generated_release_notes", "")
    final_notes = improved if improved else generated

    if not final_notes or not final_notes.strip():
        return None, "No release notes content available to write."

    section_checks, section_score = check_required_sections_present(final_notes)
    if section_score < 0.5:
        missing = [k for k, v in section_checks.items() if not v]
        return None, (
            f"Final release notes failed structural validation (score {section_score:.2f}). "
            f"Missing sections: {missing}"
        )

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