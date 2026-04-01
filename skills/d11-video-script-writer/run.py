#!/usr/bin/env python3
"""
Skill: d11-video-script-writer
Version: 1.0.0
Family: F11
Domain: D
Tag: customer-facing
Type: transformer
Schema: 2
Runner: >=4.0.0

Transforms script briefs into structured video scripts for marketing and
educational content. Produces platform-optimized scripts with hooks, scene
breakdowns with timing, on-screen text callouts, B-roll/visual direction
cues, CTA placement, and brand voice consistency.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone



# ── LLM Helpers (routed through lib/routing.py — L-003 compliant) ────────────
def call_openai(messages, model=None, max_tokens=6000):
    from lib.routing import call_llm, resolve_alias, get_api_key
    if model is None:
        _, model, _ = resolve_alias("general_short")
    return call_llm(messages, task_class="general_short", max_tokens=max_tokens)

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


def parse_duration_target(duration_str, platform):
    """Parse user-provided duration target into seconds range, or use platform default."""
    constraints = PLATFORM_CONSTRAINTS.get(platform, PLATFORM_CONSTRAINTS["general"])
    if not duration_str or not duration_str.strip():
        return constraints["duration_seconds_range"], constraints["duration_default"]

    dt = duration_str.strip().lower()
    range_match = re.match(
        r'(\d+)\s*-\s*(\d+)\s*(min|minute|minutes|sec|second|seconds|s|m)?', dt
    )
    if range_match:
        lo, hi = int(range_match.group(1)), int(range_match.group(2))
        unit = range_match.group(3) or ""
        if unit.startswith("m"):
            lo, hi = lo * 60, hi * 60
        return (lo, hi), duration_str.strip()

    single_match = re.match(r'(\d+)\s*(min|minute|minutes|sec|second|seconds|s|m)?', dt)
    if single_match:
        val = int(single_match.group(1))
        unit = single_match.group(2) or ""
        if unit.startswith("m"):
            val = val * 60
        margin = max(int(val * 0.15), 10)
        return (val - margin, val + margin), duration_str.strip()

    return constraints["duration_seconds_range"], duration_str.strip()


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
# Step 1: Parse brief and build generation plan (local)
# ---------------------------------------------------------------------------

def step_1_local(inputs, context):
    """Parse brief and build generation plan."""
    script_brief = inputs.get("script_brief", "")
    target_audience = inputs.get("target_audience", "")
    video_format = inputs.get("video_format", "")
    brand_voice = inputs.get("brand_voice", "")
    reference_material = inputs.get("reference_material", "")
    video_duration_target = inputs.get("video_duration_target", "")

    if not script_brief or len(script_brief.strip()) < 50:
        return None, "script_brief is required and must be at least 50 characters."
    if not target_audience or len(target_audience.strip()) < 10:
        return None, "target_audience is required and must be at least 10 characters."
    if video_format not in PLATFORM_CONSTRAINTS:
        return None, (
            f"video_format must be one of: {list(PLATFORM_CONSTRAINTS.keys())}. "
            f"Got: '{video_format}'"
        )
    if not brand_voice or len(brand_voice.strip()) < 10:
        return None, "brand_voice is required and must be at least 10 characters."

    constraints = PLATFORM_CONSTRAINTS[video_format]
    duration_range, duration_label = parse_duration_target(
        video_duration_target, video_format
    )

    sentences = [
        s.strip() for s in re.split(r'[.!?\n]', script_brief) if len(s.strip()) > 15
    ]
    key_messages = sentences[:10]

    ref_facts = []
    if reference_material and reference_material.strip():
        ref_sentences = [
            s.strip()
            for s in re.split(r'[.!?\n]', reference_material)
            if len(s.strip()) > 10
        ]
        ref_facts = ref_sentences[:30]

    generation_plan = {
        "platform": video_format,
        "hook_window_seconds": constraints["hook_window_seconds"],
        "duration_range_seconds": list(duration_range),
        "duration_label": duration_label,
        "min_scenes": constraints["min_scenes"],
        "max_scenes": constraints["max_scenes"],
        "structural_notes": constraints["structural_notes"],
        "key_messages": key_messages,
        "reference_fact_count": len(ref_facts),
        "reference_facts": ref_facts,
        "has_reference_material": bool(
            reference_material and reference_material.strip()
        ),
        "script_brief": script_brief.strip(),
        "target_audience": target_audience.strip(),
        "brand_voice": brand_voice.strip(),
        "reference_material": (
            reference_material.strip() if reference_material else ""
        ),
    }

    return {"output": generation_plan}, None


# ---------------------------------------------------------------------------
# Step 2: Generate structured video script draft (LLM)
# ---------------------------------------------------------------------------

def step_2_llm(inputs, context):
    """Generate structured video script draft."""
    plan = context.get("step_1_output", {})
    if not plan:
        return None, "Missing generation plan from step 1."

    platform = plan.get("platform", "general")
    hook_window = plan.get("hook_window_seconds", 10)
    duration_label = plan.get("duration_label", "3-5 minutes")
    duration_range = plan.get("duration_range_seconds", [180, 300])
    min_scenes = plan.get("min_scenes", 4)
    max_scenes = plan.get("max_scenes", 12)
    structural_notes = plan.get("structural_notes", "")
    script_brief = plan.get("script_brief", "")
    target_audience = plan.get("target_audience", "")
    brand_voice = plan.get("brand_voice", "")
    reference_material = plan.get("reference_material", "")
    has_ref = plan.get("has_reference_material", False)
    key_messages = plan.get("key_messages", [])

    if has_ref:
        anti_fabrication = (
            "\n\nCRITICAL ANTI-FABRICATION RULE: You MUST only include statistics, "
            "quotes, data points, and specific claims that are directly traceable to "
            "the Reference Material or the Script Brief provided below. Do NOT invent "
            "or fabricate any facts, numbers, percentages, or quotes. If the reference "
            "material is insufficient for a claim you want to make, insert a placeholder "
            "like [INSERT STAT] or [VERIFY CLAIM] instead of fabricating data."
        )
    else:
        anti_fabrication = (
            "\n\nCRITICAL ANTI-FABRICATION RULE: No reference material was provided. "
            "Do NOT fabricate any specific statistics, percentages, quotes, or data "
            "points. Use general descriptive language or insert placeholders like "
            "[INSERT STAT], [ADD DATA POINT], or [CITE SOURCE] where specific claims "
            "would strengthen the script. The viewer must never encounter a made-up number."
        )

    key_msg_text = ""
    if key_messages:
        key_msg_text = "\n## Key Messages to Incorporate\n"
        for i, msg in enumerate(key_messages, 1):
            key_msg_text += f"{i}. {msg}\n"

    system_prompt = (
        "You are an expert video script writer specializing in marketing and "
        "educational content across YouTube, TikTok/Reels, LinkedIn, and general "
        "video platforms. You have deep expertise in:\n"
        "- Crafting attention-grabbing hooks calibrated to platform-specific timing windows\n"
        "- Structuring scenes with precise second-level timing that maintains viewer retention\n"
        "- Writing specific, actionable visual direction cues (camera angles, B-roll, graphics)\n"
        "- Embedding on-screen text callouts that reinforce spoken content\n"
        "- Placing CTAs at psychologically optimal moments in the viewer journey\n"
        "- Maintaining strict brand voice consistency throughout every line of script\n"
        "- Pacing content to match platform audience expectations and attention spans\n"
        "You never fabricate statistics, quotes, or claims not grounded in provided material."
        f"{anti_fabrication}"
    )

    ref_section = ""
    if has_ref:
        ref_section = f"## Reference Material (Ground Truth for Claims)\n{reference_material}"
    else:
        ref_section = (
            "## Reference Material\nNone provided. Do not fabricate specific claims, "
            "statistics, or quotes. Use placeholders where data would strengthen the script."
        )

    user_prompt = f"""Write a complete, production-ready structured video script based on the following inputs.

## Script Brief
{script_brief}

## Target Audience
{target_audience}

## Brand Voice Guidelines
{brand_voice}
{key_msg_text}
## Platform & Format Constraints
- Platform: {platform}
- Target Duration: {duration_label} ({duration_range[0]}-{duration_range[1]} seconds total)
- Hook Window: First {hook_window} seconds (viewer decides to stay or leave)
- Scene/Segment Count: {min_scenes}-{max_scenes} scenes
- Platform-Specific Notes: {structural_notes}

{ref_section}

## Required Output Structure

Produce the script in markdown with EXACTLY these sections in this order:

## Hook
Write the opening hook that must capture attention within {hook_window} seconds.
- Include a [TIMING: Xs] tag showing the hook duration
- Include at least one [VISUAL: description] tag with specific camera/visual direction
- Include at least one [ON-SCREEN TEXT: text] tag if appropriate for the platform
- The hook must create curiosity, urgency, or emotional resonance for the target audience
- Match the brand voice from the very first word

## Scene Breakdown
For each scene, use this exact format:

### Scene N: [Descriptive Scene Title] [TIMING: Xs-Ys]
**Narration/Dialogue:**
The exact words to be spoken, written in the brand voice.

**[VISUAL: Specific visual direction]** — describe camera angle, B-roll footage, graphics, animations, or on-screen demonstrations. Be specific enough for a production team to execute.

**[ON-SCREEN TEXT: Exact text overlay]** — any text that appears on screen during this scene.

**[TRANSITION: Type of transition]** — how this scene connects to the next (cut, dissolve, swipe, etc.)

CRITICAL: Scene timings MUST sum to approximately {duration_range[0]}-{duration_range[1]} seconds total. Each scene needs a [TIMING:] tag showing its start and end time.

## CTA Placement
- Specify exactly ONE primary call-to-action
- State which scene it appears in and why that placement is optimal
- Write the exact CTA script text (narration)
- Include [VISUAL:] and [ON-SCREEN TEXT:] tags for the CTA moment

## On-Screen Text Summary
List ALL on-screen text callouts from the entire script in chronological order, numbered.

## Visual Direction Summary
List ALL B-roll, visual, camera, and graphic direction cues from the entire script in chronological order, numbered.

## Brand Voice Notes
Explain specifically how the brand voice guidelines were applied:
- Which tone descriptors guided word choices
- How vocabulary preferences were honored
- Any phrases used or avoided per the guidelines

Write the complete script now. Be precise with timing, specific with visual direction, and consistent with brand voice throughout."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    token_budget = 6000
    if platform == "youtube_longform":
        token_budget = 10000
    elif platform in ("tiktok_reels_shortform", "linkedin"):
        token_budget = 5000

    content, error = call_resolved(messages, context, max_tokens=token_budget)
    if error:
        content, error = call_openai(
            messages, model="gpt-4.1-mini", max_tokens=token_budget
        )
    if error:
        return None, error

    return {"output": content}, None


# ---------------------------------------------------------------------------
# Step 3: Evaluate script quality and compliance (critic)
# ---------------------------------------------------------------------------

def check_structural_compliance(script_text, plan):
    """Deterministic structural checks on the generated script."""
    issues = []
    score = 10

    hook_section = extract_section(script_text, ["Hook"])
    if not hook_section:
        issues.append("Missing ## Hook section.")
        score -= 3
    else:
        timing_match = re.search(r'\[TIMING:\s*(\d+)', hook_section, re.IGNORECASE)
        if not timing_match:
            issues.append("Hook section missing [TIMING: Xs] tag.")
            score -= 1
        else:
            hook_time = int(timing_match.group(1))
            hook_window = plan.get("hook_window_seconds", 10)
            if hook_time > hook_window:
                issues.append(
                    f"Hook timing ({hook_time}s) exceeds hook window ({hook_window}s)."
                )
                score -= 2

    scene_section = extract_section(script_text, ["Scene Breakdown", "Scene"])
    if not scene_section:
        issues.append("Missing ## Scene Breakdown section.")
        score -= 3
    else:
        scene_headings = re.findall(
            r'###\s+Scene\s+\d+', scene_section, re.IGNORECASE
        )
        min_scenes = plan.get("min_scenes", 3)
        max_scenes = plan.get("max_scenes", 12)
        if len(scene_headings) < min_scenes:
            issues.append(
                f"Too few scenes: {len(scene_headings)} (minimum {min_scenes})."
            )
            score -= 2
        elif len(scene_headings) > max_scenes:
            issues.append(
                f"Too many scenes: {len(scene_headings)} (maximum {max_scenes})."
            )
            score -= 1

        timing_tags = re.findall(r'\[TIMING:\s*[\d]', script_text, re.IGNORECASE)
        if len(timing_tags) < 2:
            issues.append("Insufficient [TIMING:] tags in scenes.")
            score -= 1

    cta_section = extract_section(script_text, ["CTA Placement", "CTA"])
    if not cta_section:
        issues.append("Missing ## CTA Placement section.")
        score -= 2

    visual_cues = re.findall(r'\[VISUAL:', script_text, re.IGNORECASE)
    if len(visual_cues) < 2:
        issues.append(
            f"Insufficient [VISUAL:] direction cues (found {len(visual_cues)}, need >=2)."
        )
        score -= 1

    onscreen_cues = re.findall(r'\[ON-SCREEN TEXT:', script_text, re.IGNORECASE)
    if len(onscreen_cues) < 1:
        issues.append("No [ON-SCREEN TEXT:] callouts found.")
        score -= 1

    ost_summary = extract_section(
        script_text, ["On-Screen Text Summary", "On-Screen Text"]
    )
    if not ost_summary:
        issues.append("Missing ## On-Screen Text Summary section.")
        score -= 1

    vis_summary = extract_section(
        script_text, ["Visual Direction Summary", "Visual Direction"]
    )
    if not vis_summary:
        issues.append("Missing ## Visual Direction Summary section.")
        score -= 1

    bv_section = extract_section(
        script_text, ["Brand Voice Notes", "Brand Voice"]
    )
    if not bv_section:
        issues.append("Missing ## Brand Voice Notes section.")
        score -= 1

    score = max(1, score)
    return score, issues


def step_3_critic(inputs, context):
    """Evaluate script quality and compliance."""
    plan = context.get("step_1_output", {})
    script_text = context.get("improved_script", context.get("generated_script", ""))

    if not script_text:
        return None, "No generated script found for evaluation."

    structural_score, structural_issues = check_structural_compliance(
        script_text, plan
    )

    platform = plan.get("platform", "general")
    brand_voice = plan.get("brand_voice", "")
    target_audience = plan.get("target_audience", "")
    has_ref = plan.get("has_reference_material", False)

    system_prompt = (
        "You are a senior video script quality evaluator with expertise in "
        "marketing video production across YouTube, TikTok/Reels, LinkedIn, and "
        "general formats. You assess scripts rigorously on hook effectiveness, "
        "narrative flow and pacing, brand voice adherence, visual direction "
        "specificity and quality, audience appropriateness, and factual integrity. "
        "You score strictly — a 10 means broadcast-ready, a 5 means significant "
        "revision needed, a 1 means fundamentally broken. You identify specific "
        "line-level issues and provide actionable improvement suggestions."
    )

    issues_json = json.dumps(structural_issues) if structural_issues else "None"

    user_prompt = f"""Evaluate this video script on the following dimensions. Score each 1-10 with strict standards.

## Platform: {platform}
## Target Audience: {target_audience}
## Brand Voice Guidelines: {brand_voice}
## Reference Material Provided: {"Yes — all claims must be traceable to it" if has_ref else "No — script should not contain fabricated statistics or quotes"}

## Script to Evaluate:
{script_text}

## Structural Issues Already Identified by Automated Checks:
{issues_json}

## Scoring Dimensions (1-10 each, be strict):
1. **hook_effectiveness**: Is the hook compelling and attention-grabbing? Does it fit within the platform timing window? Would the target audience stop scrolling?
2. **narrative_flow**: Does the script flow logically from hook through scenes to CTA? Is pacing appropriate for the platform? Are transitions smooth?
3. **brand_voice_adherence**: Does every line consistently match the brand voice guidelines? Are tone, vocabulary, and personality traits maintained throughout?
4. **visual_direction_quality**: Are [VISUAL:] cues specific enough for a production team to execute? Do they enhance the narrative? Is there sufficient visual variety?
5. **audience_appropriateness**: Is the language complexity, tone, examples, and cultural references right for the target audience?
6. **factual_integrity**: Are all claims grounded in provided material? Any fabricated stats, percentages, or quotes? Any unsupported superlatives?

Return ONLY a JSON object with this exact structure:
{{
  "hook_effectiveness": <int 1-10>,
  "narrative_flow": <int 1-10>,
  "brand_voice_adherence": <int 1-10>,
  "visual_direction_quality": <int 1-10>,
  "audience_appropriateness": <int 1-10>,
  "factual_integrity": <int 1-10>,
  "issues": ["specific issue 1", "specific issue 2"],
  "strengths": ["specific strength 1", "specific strength 2"],
  "improvement_suggestions": ["actionable suggestion 1", "actionable suggestion 2"]
}}"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    content, error = call_resolved(messages, context, max_tokens=3000)
    if error:
        content, error = call_openai(
            messages, model="gpt-4.1-mini", max_tokens=3000
        )
    if error:
        return None, error

    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
        cleaned = re.sub(r'\s*```$', '', cleaned)

    try:
        scores = json.loads(cleaned)
    except json.JSONDecodeError:
        json_match = re.search(r'\{[^{}]*\}', cleaned, re.DOTALL)
        if json_match:
            try:
                scores = json.loads(json_match.group(0))
            except json.JSONDecodeError:
                return None, f"Failed to parse critic JSON: {cleaned[:300]}"
        else:
            return None, f"No JSON found in critic response: {cleaned[:300]}"

    hook_eff = int(scores.get("hook_effectiveness", 5))
    narrative = int(scores.get("narrative_flow", 5))
    brand_adh = int(scores.get("brand_voice_adherence", 5))
    visual_q = int(scores.get("visual_direction_quality", 5))
    audience_app = int(scores.get("audience_appropriateness", 5))
    factual_int = int(scores.get("factual_integrity", 5))

    quality_score = min(
        structural_score,
        hook_eff,
        narrative,
        brand_adh,
        visual_q,
        audience_app,
        factual_int,
    )

    all_issues = structural_issues + scores.get("issues", [])

    result = {
        "output": {
            "quality_score": quality_score,
            "structural_score": structural_score,
            "hook_effectiveness": hook_eff,
            "narrative_flow": narrative,
            "brand_voice_adherence": brand_adh,
            "visual_direction_quality": visual_q,
            "audience_appropriateness": audience_app,
            "factual_integrity": factual_int,
            "issues": all_issues,
            "strengths": scores.get("strengths", []),
            "improvement_suggestions": scores.get("improvement_suggestions", []),
        }
    }

    return result, None


# ---------------------------------------------------------------------------
# Step 4: Improve script based on critic feedback (LLM)
# ---------------------------------------------------------------------------

def step_4_llm(inputs, context):
    """Improve script based on critic feedback."""
    plan = context.get("step_1_output", {})
    script_text = context.get(
        "improved_script", context.get("generated_script", "")
    )
    critic_output = context.get("step_3_output", {})

    if not script_text:
        return None, "No script found for improvement."
    if not critic_output:
        return None, "No critic feedback found for improvement."

    quality_score = critic_output.get("quality_score", 10)
    issues = critic_output.get("issues", [])
    suggestions = critic_output.get("improvement_suggestions", [])

    if quality_score >= 8 and not issues:
        return {"output": script_text}, None

    platform = plan.get("platform", "general")
    hook_window = plan.get("hook_window_seconds", 10)
    duration_label = plan.get("duration_label", "3-5 minutes")
    duration_range = plan.get("duration_range_seconds", [180, 300])
    brand_voice = plan.get("brand_voice", "")
    target_audience = plan.get("target_audience", "")
    has_ref = plan.get("has_reference_material", False)
    reference_material = plan.get("reference_material", "")

    if has_ref:
        anti_fabrication = (
            "CRITICAL ANTI-FABRICATION RULE: Only include statistics, quotes, and "
            "claims traceable to the Reference Material below. Use [INSERT STAT] or "
            "[VERIFY CLAIM] placeholders for any claim you cannot ground in the material."
        )
    else:
        anti_fabrication = (
            "CRITICAL ANTI-FABRICATION RULE: No reference material provided. Do NOT "
            "fabricate specific statistics, percentages, or quotes. Use placeholders "
            "like [INSERT STAT] or [ADD DATA POINT] where data would strengthen the script."
        )

    system_prompt = (
        "You are an expert video script writer performing a targeted revision based "
        "on detailed quality feedback from a senior evaluator. Your task is to fix "
        "every identified issue while preserving all strengths and working elements. "
        "You maintain the original structure, intent, and brand voice while making "
        "surgical improvements to weak areas. You are meticulous about timing accuracy, "
        "visual direction specificity, and factual integrity.\n\n"
        f"{anti_fabrication}"
    )

    issues_text = (
        "\n".join(f"- {issue}" for issue in issues) if issues else "None identified"
    )
    suggestions_text = (
        "\n".join(f"- {s}" for s in suggestions) if suggestions else "None provided"
    )

    score_details = (
        f"- Overall Quality Score: {quality_score}/10\n"
        f"- Structural Score: {critic_output.get('structural_score', 'N/A')}/10\n"
        f"- Hook Effectiveness: {critic_output.get('hook_effectiveness', 'N/A')}/10\n"
        f"- Narrative Flow: {critic_output.get('narrative_flow', 'N/A')}/10\n"
        f"- Brand Voice Adherence: {critic_output.get('brand_voice_adherence', 'N/A')}/10\n"
        f"- Visual Direction Quality: {critic_output.get('visual_direction_quality', 'N/A')}/10\n"
        f"- Audience Appropriateness: {critic_output.get('audience_appropriateness', 'N/A')}/10\n"
        f"- Factual Integrity: {critic_output.get('factual_integrity', 'N/A')}/10"
    )

    strengths_text = ""
    strengths = critic_output.get("strengths", [])
    if strengths:
        strengths_text = "\n## Strengths to Preserve:\n"
        strengths_text += "\n".join(f"- {s}" for s in strengths)

    ref_section = ""
    if has_ref and reference_material:
        ref_section = (
            f"\n## Reference Material (Ground Truth for Claims)\n{reference_material}"
        )

    user_prompt = f"""Revise the following video script to address ALL identified issues while preserving its strengths.

## Critic Evaluation Scores:
{score_details}

## Issues That MUST Be Fixed:
{issues_text}

## Improvement Suggestions:
{suggestions_text}
{strengths_text}

## Platform Constraints (must be maintained):
- Platform: {platform}
- Hook Window: {hook_window}s
- Target Duration: {duration_label} ({duration_range[0]}-{duration_range[1]}s)
- Brand Voice: {brand_voice}
- Target Audience: {target_audience}
{ref_section}

## Current Script to Revise:
{script_text}

## Revision Requirements:
1. Fix EVERY issue listed above — do not skip any.
2. Preserve all identified strengths and working elements.
3. Maintain the required markdown structure exactly:
   - ## Hook (with [TIMING:], [VISUAL:], [ON-SCREEN TEXT:] tags)
   - ## Scene Breakdown (with ### Scene N headings, each having [TIMING:], narration, [VISUAL:], [ON-SCREEN TEXT:], [TRANSITION:] tags)
   - ## CTA Placement (exactly ONE primary CTA with placement rationale)
   - ## On-Screen Text Summary (numbered chronological list)
   - ## Visual Direction Summary (numbered chronological list)
   - ## Brand Voice Notes (specific explanation of voice application)
4. Scene timings MUST sum to approximately {duration_range[0]}-{duration_range[1]} seconds.
5. Focus improvement effort on the lowest-scoring dimensions.
6. Do NOT remove content that was working well.

Output the COMPLETE revised script in the same markdown format. Do not truncate or summarize."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    token_budget = 6000
    if platform == "youtube_longform":
        token_budget = 10000
    elif platform in ("tiktok_reels_shortform", "linkedin"):
        token_budget = 5000

    content, error = call_resolved(messages, context, max_tokens=token_budget)
    if error:
        content, error = call_openai(
            messages, model="gpt-4.1-mini", max_tokens=token_budget
        )
    if error:
        return None, error

    return {"output": content}, None


# ---------------------------------------------------------------------------
# Step 5: Write final script artifact (local, final)
# ---------------------------------------------------------------------------

def step_5_local(inputs, context):
    """Write final script artifact to disk."""
    improved = context.get("improved_script", "")
    generated = context.get("generated_script", "")
    final_script = improved if improved else generated

    if not final_script or not final_script.strip():
        return None, "No script content available to write."

    has_hook = bool(re.search(r'##\s+Hook', final_script, re.IGNORECASE))
    has_scenes = bool(
        re.search(r'##\s+Scene\s*Breakdown', final_script, re.IGNORECASE)
    ) or bool(re.search(r'###\s+Scene\s+\d+', final_script, re.IGNORECASE))
    has_cta = bool(re.search(r'##\s+CTA', final_script, re.IGNORECASE))

    if not has_hook:
        return None, "Final script missing Hook section — cannot write artifact."
    if not has_scenes:
        return None, "Final script missing Scene Breakdown — cannot write artifact."
    if not has_cta:
        return None, "Final script missing CTA section — cannot write artifact."

    # Count distinct CTAs — flag if more than 2
    cta_section = ""
    cta_match = re.search(r'##\s+CTA.*?(?=\n##\s|\Z)', final_script, re.IGNORECASE | re.DOTALL)
    if cta_match:
        cta_section = cta_match.group()
    cta_phrases = ["sign up", "subscribe", "buy now", "get started", "try free",
                   "download", "learn more", "book a demo", "start your",
                   "join now", "claim your", "register", "order now"]
    cta_count = sum(1 for phrase in cta_phrases
                    if phrase in final_script.lower())
    if cta_count > 2:
        return None, f"SCRIPT INTEGRITY FAILURE: {cta_count} distinct CTAs detected — single CTA required."

    return {"output": "artifact_written"}, None


# ---------------------------------------------------------------------------
# Step handlers registry
# ---------------------------------------------------------------------------

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