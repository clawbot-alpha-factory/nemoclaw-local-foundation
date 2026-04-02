#!/usr/bin/env python3
"""
Skill ID: e08-kb-article-writer
Version: 1.0.0
Family: F08
Domain: E
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



# ── LLM Helpers (routed through lib/routing.py — L-003 compliant) ────────────
def call_openai(messages, model=None, max_tokens=6000):
    from lib.routing import call_llm_or_chain
    return call_llm_or_chain(messages, task_class="general_short", task_domain="research", max_tokens=max_tokens)

def call_anthropic(messages, model=None, max_tokens=6000):
    from lib.routing import call_llm, resolve_alias
    if model is None:
        _, model, _ = resolve_alias("complex_reasoning")
    return call_llm(messages, task_class="complex_reasoning", max_tokens=max_tokens)

def call_google(messages, model=None, max_tokens=6000):
    from lib.routing import call_llm, resolve_alias
    if model is None:
        _, model, _ = resolve_alias("moderate")
    return call_llm(messages, task_class="moderate", max_tokens=max_tokens)

def call_resolved(messages, context, max_tokens=6000):
    from lib.routing import call_llm
    return call_llm(messages, task_class="moderate", max_tokens=max_tokens)


def check_required_sections(article_text):
    """Check that the article contains key structural sections."""
    checks = {
        "title": bool(re.search(r'^#\s+.+', article_text, re.MULTILINE)),
        "overview_or_problem": bool(re.search(r'##\s+(overview|problem|introduction|background)', article_text, re.IGNORECASE)),
        "steps_or_content": bool(re.search(r'##\s+(step|solution|procedure|how|definition|concept|parameter|use case)', article_text, re.IGNORECASE)),
        "troubleshooting_or_tips": bool(re.search(r'##\s+(troubleshoot|tip|common issue|faq|note)', article_text, re.IGNORECASE)),
        "tags_or_metadata": bool(re.search(r'##\s+(metadata|tags?|keywords?)', article_text, re.IGNORECASE)),
        "related": bool(re.search(r'##\s+(related|see also|further reading)', article_text, re.IGNORECASE)),
    }
    found = sum(1 for v in checks.values() if v)
    return found, checks


def check_minimum_word_count(article_text, minimum=150):
    words = len(article_text.split())
    return words >= minimum, words


def step_1_local(inputs, context):
    """Parse Inputs Validate Source Build Article Plan"""
    topic = inputs.get("topic", "").strip()
    article_type = inputs.get("article_type", "how-to").strip()
    target_audience = inputs.get("target_audience", "").strip()
    source_material = inputs.get("source_material", "").strip()
    related_article_hints = inputs.get("related_article_hints", "").strip()
    tone = inputs.get("tone", "professional").strip()

    errors = []

    if not topic or len(topic) < 5:
        errors.append("topic must be at least 5 characters.")
    if len(topic) > 300:
        errors.append("topic exceeds 300 characters.")

    allowed_types = ["how-to", "troubleshooting", "reference", "conceptual"]
    if article_type not in allowed_types:
        errors.append(f"article_type must be one of: {allowed_types}. Got: '{article_type}'")
        article_type = "how-to"

    if not target_audience or len(target_audience) < 3:
        errors.append("target_audience must be at least 3 characters.")
    if len(target_audience) > 200:
        errors.append("target_audience exceeds 200 characters.")

    if not source_material or len(source_material) < 50:
        errors.append("source_material must be at least 50 characters.")
    if len(source_material) > 20000:
        errors.append("source_material exceeds 20000 characters.")

    allowed_tones = ["professional", "friendly", "technical", "concise"]
    if tone not in allowed_tones:
        tone = "professional"

    if errors:
        return None, "Input validation failed: " + "; ".join(errors)

    sections = ARTICLE_TYPE_SECTIONS.get(article_type, ARTICLE_TYPE_SECTIONS["how-to"])
    tone_directive = TONE_DIRECTIVES.get(tone, TONE_DIRECTIVES["professional"])
    audience_framing = f"Write for {target_audience}. Calibrate complexity and terminology accordingly."

    source_word_count = len(source_material.split())

    related_hints_list = []
    if related_article_hints:
        related_hints_list = [h.strip() for h in related_article_hints.split(",") if h.strip()]

    plan = {
        "topic": topic,
        "article_type": article_type,
        "target_audience": target_audience,
        "tone": tone,
        "tone_directive": tone_directive,
        "audience_framing": audience_framing,
        "required_sections": sections,
        "related_hints": related_hints_list,
        "source_word_count": source_word_count,
        "source_substance_ok": source_word_count >= 20,
        "validation_passed": True,
    }

    return {"output": plan}, None


def step_2_llm(inputs, context):
    """Generate Structured KB Article Draft"""
    plan = context.get("step_1_output", {})
    if not plan:
        return None, "step_1_output not found in context."

    topic = plan.get("topic", inputs.get("topic", ""))
    article_type = plan.get("article_type", inputs.get("article_type", "how-to"))
    target_audience = plan.get("target_audience", inputs.get("target_audience", ""))
    tone = plan.get("tone", "professional")
    tone_directive = plan.get("tone_directive", TONE_DIRECTIVES["professional"])
    audience_framing = plan.get("audience_framing", "")
    required_sections = plan.get("required_sections", [])
    related_hints = plan.get("related_hints", [])
    source_material = inputs.get("source_material", "")

    related_hints_str = ""
    if related_hints:
        related_hints_str = f"\nSuggested related articles to reference in the Related Articles section: {', '.join(related_hints)}"

    sections_str = ", ".join(required_sections)
    article_type_guidance = ARTICLE_TYPE_GUIDANCE.get(article_type, ARTICLE_TYPE_GUIDANCE["how-to"])

    system_prompt = (
        "You are a senior technical writer specializing in knowledge base content. "
        "You produce accurate, well-structured articles grounded strictly in provided source material. "
        "You never fabricate solutions, steps, commands, parameters, or references not present in the source. "
        "Every factual claim in your article must be directly supported by the source material provided."
    )

    user_prompt = f"""Write a complete knowledge base article on the following topic.

TOPIC: {topic}
ARTICLE TYPE: {article_type}
TARGET AUDIENCE: {target_audience}
TONE: {tone}

TONE DIRECTIVE: {tone_directive}
AUDIENCE FRAMING: {audience_framing}

STRUCTURE REQUIREMENTS:
{article_type_guidance}

Required sections to include: {sections_str}

ANTI-FABRICATION RULE: Every solution, step, definition, parameter, command, or claim in the article MUST be grounded in the source material below. Do not invent steps, commands, options, or facts not present in the source. If the source material does not cover a required section fully, note the limitation rather than fabricating content.

SOURCE MATERIAL:
---
{source_material}
---
{related_hints_str}

OUTPUT FORMAT:
- Use H1 (#) for the article title only
- Use H2 (##) for all major sections
- Use H3 (###) for subsections within major sections
- Use numbered lists for sequential steps
- Use bullet points for non-sequential items
- End with a ## Metadata/Tags section containing 5-10 relevant keyword tags as a comma-separated list

Write the complete article now:"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    content, error = call_resolved(messages, context, max_tokens=6000)
    if error:
        content, error = call_openai(messages, max_tokens=6000)
    if error:
        return None, error

    return {"output": content}, None


def step_3_critic(inputs, context):
    """Evaluate Article Quality Anti-Fabrication Compliance"""
    article = context.get("improved_article", context.get("generated_article", ""))
    if not article:
        return None, "generated_article not found in context."

    plan = context.get("step_1_output", {})
    source_material = inputs.get("source_material", "")
    article_type = plan.get("article_type", inputs.get("article_type", "how-to")) if plan else inputs.get("article_type", "how-to")
    target_audience = plan.get("target_audience", inputs.get("target_audience", "")) if plan else inputs.get("target_audience", "")

    # Deterministic structural checks
    sections_found, section_checks = check_required_sections(article)
    word_count_ok, word_count = check_minimum_word_count(article, minimum=150)
    has_title = bool(re.search(r'^#\s+.+', article, re.MULTILINE))
    has_tags = bool(re.search(r'##\s+(metadata|tags?|keywords?)', article, re.IGNORECASE))

    if sections_found >= 5:
        structural_score = 10
    elif sections_found >= 4:
        structural_score = 8
    elif sections_found >= 3:
        structural_score = 6
    elif sections_found >= 2:
        structural_score = 4
    else:
        structural_score = 2

    if not word_count_ok:
        structural_score = min(structural_score, 4)
    if not has_title:
        structural_score = min(structural_score, 3)
    if not has_tags:
        structural_score = max(structural_score - 1, 0)

    structural_details = {
        "sections_found": sections_found,
        "section_checks": section_checks,
        "word_count": word_count,
        "word_count_ok": word_count_ok,
        "has_title": has_title,
        "has_tags": has_tags,
        "structural_score": structural_score,
    }

    system_prompt = (
        "You are a senior knowledge base quality reviewer. "
        "You evaluate articles for grounding accuracy (no fabricated content) and clarity. "
        "You return only valid JSON with no additional commentary."
    )

    user_prompt = f"""Evaluate the following knowledge base article on two dimensions. Return ONLY valid JSON with no markdown fences.

ARTICLE TYPE: {article_type}
TARGET AUDIENCE: {target_audience}

SOURCE MATERIAL (ground truth — all article content must be traceable here):
---
{source_material}
---

ARTICLE TO EVALUATE:
---
{article}
---

Evaluate on these two dimensions:

1. grounding_score (1-10): Are all solutions, steps, definitions, commands, and claims grounded in the source material above? Score 10 if everything is supported. Deduct 2 points for each fabricated claim, step, or command not present in the source. Score 1 if the article is largely fabricated.

2. clarity_score (1-10): Is the article clear, well-organized, and appropriate for the target audience ({target_audience})? Does it follow the expected structure for a {article_type} article? Score 10 for excellent structure and clarity. Deduct points for missing sections, poor organization, or inappropriate language level.

Also provide:
- grounding_issues: list of specific fabricated or unsupported claims found (empty list if none)
- clarity_issues: list of specific clarity or structure problems found (empty list if none)
- improvement_suggestions: list of 3-5 specific, actionable improvements

Return ONLY this JSON structure (no markdown, no explanation):
{{
  "grounding_score": <integer 1-10>,
  "clarity_score": <integer 1-10>,
  "grounding_issues": ["issue1", "issue2"],
  "clarity_issues": ["issue1", "issue2"],
  "improvement_suggestions": ["suggestion1", "suggestion2", "suggestion3"]
}}"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    content, error = call_resolved(messages, context, max_tokens=3000)
    if error:
        content, error = call_openai(messages, max_tokens=3000)
    if error:
        return None, error

    try:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
            cleaned = re.sub(r'\s*```$', '', cleaned)
        scores = json.loads(cleaned)
    except Exception as e:
        return None, f"Failed to parse critic JSON: {e}. Raw: {content[:500]}"

    grounding_score = max(1, min(10, int(scores.get("grounding_score", 5))))
    clarity_score = max(1, min(10, int(scores.get("clarity_score", 5))))
    quality_score = min(structural_score, grounding_score, clarity_score)

    result = {
        "quality_score": quality_score,
        "structural_score": structural_score,
        "grounding_score": grounding_score,
        "clarity_score": clarity_score,
        "structural_details": structural_details,
        "grounding_issues": scores.get("grounding_issues", []),
        "clarity_issues": scores.get("clarity_issues", []),
        "improvement_suggestions": scores.get("improvement_suggestions", []),
        "passes_threshold": quality_score >= 7,
    }

    return {"output": result}, None


def step_4_llm(inputs, context):
    """Improve Article Based On Critic Feedback"""
    critic_output = context.get("article_quality_report", {})
    original_article = context.get("generated_article", "")

    if not original_article:
        return None, "generated_article not found in context."

    plan = context.get("step_1_output", {})
    source_material = inputs.get("source_material", "")
    topic = plan.get("topic", inputs.get("topic", "")) if plan else inputs.get("topic", "")
    article_type = plan.get("article_type", inputs.get("article_type", "how-to")) if plan else inputs.get("article_type", "how-to")
    target_audience = plan.get("target_audience", inputs.get("target_audience", "")) if plan else inputs.get("target_audience", "")
    tone_directive = plan.get("tone_directive", TONE_DIRECTIVES["professional"]) if plan else TONE_DIRECTIVES["professional"]

    grounding_issues = critic_output.get("grounding_issues", []) if critic_output else []
    clarity_issues = critic_output.get("clarity_issues", []) if critic_output else []
    improvement_suggestions = critic_output.get("improvement_suggestions", []) if critic_output else []
    quality_score = critic_output.get("quality_score", 0) if critic_output else 0

    grounding_issues_str = "\n".join(f"- {i}" for i in grounding_issues) if grounding_issues else "None identified."
    clarity_issues_str = "\n".join(f"- {i}" for i in clarity_issues) if clarity_issues else "None identified."
    suggestions_str = "\n".join(f"- {s}" for s in improvement_suggestions) if improvement_suggestions else "Apply general quality improvements."

    article_type_guidance = ARTICLE_TYPE_GUIDANCE.get(article_type, ARTICLE_TYPE_GUIDANCE["how-to"])

    system_prompt = (
        "You are a senior technical writer specializing in knowledge base content. "
        "You revise articles to fix grounding issues, improve clarity, and ensure complete structure. "
        "You never fabricate solutions, steps, commands, parameters, or references not present in the source material. "
        "Every factual claim in your revised article must be directly supported by the source material provided."
    )

    user_prompt = f"""Revise the following knowledge base article based on the critic feedback below.

TOPIC: {topic}
ARTICLE TYPE: {article_type}
TARGET AUDIENCE: {target_audience}
TONE DIRECTIVE: {tone_directive}
CURRENT QUALITY SCORE: {quality_score}/10

STRUCTURE REQUIREMENTS (ensure the revised article meets these):
{article_type_guidance}

CRITIC FEEDBACK TO ADDRESS:

Grounding Issues (content not supported by source material — REMOVE or CORRECT these):
{grounding_issues_str}

Clarity Issues (structure or readability problems — FIX these):
{clarity_issues_str}

Improvement Suggestions (implement where applicable):
{suggestions_str}

SOURCE MATERIAL (ground truth — all content must be traceable here):
---
{source_material}
---

ORIGINAL ARTICLE TO REVISE:
---
{original_article}
---

REVISION INSTRUCTIONS:
1. Remove or correct every item listed under Grounding Issues — these are fabricated or unsupported claims.
2. Fix all Clarity Issues identified above.
3. Implement the Improvement Suggestions where applicable.
4. Ensure the article has: H1 title, H2 major sections, H3 subsections as needed.
5. Ensure the ## Metadata/Tags section contains 5-10 relevant keyword tags as a comma-separated list.
6. Do NOT add any new facts, steps, commands, or claims not present in the source material.
7. Preserve all content from the original that is correctly grounded in the source.

Write the complete revised article in clean markdown:"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    content, error = call_resolved(messages, context, max_tokens=6000)
    if error:
        content, error = call_openai(messages, max_tokens=6000)
    if error:
        return None, error

    return {"output": content}, None


def step_5_local(inputs, context):
    """Write Final Article Artifact"""
    improved = context.get("improved_article", "")
    generated = context.get("generated_article", "")
    final_article = improved if improved else generated

    if not final_article or len(final_article.strip()) < 50:
        return None, "Final article is empty or too short to write."

    has_title = bool(re.search(r'^#\s+.+', final_article, re.MULTILINE))
    if not has_title:
        return None, "Final article is missing a title (H1 heading). Structural validation failed."

    word_count = len(final_article.split())
    if word_count < 100:
        return None, f"Final article has only {word_count} words. Minimum is 100."

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