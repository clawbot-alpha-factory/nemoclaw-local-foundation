#!/usr/bin/env python3
"""
Skill ID: e08-meeting-summary-gen
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


def call_openai(messages, model="gpt-4o-mini", max_tokens=4000):
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


def call_anthropic(messages, model="claude-3-5-sonnet-20241022", max_tokens=4000):
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


def call_google(messages, model="gemini-1.5-flash", max_tokens=4000):
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
    provider = context.get("resolved_provider", "openai")
    model = context.get("resolved_model", "gpt-4o-mini")
    if provider == "anthropic":
        return call_anthropic(messages, model=model, max_tokens=max_tokens)
    elif provider == "google":
        return call_google(messages, model=model, max_tokens=max_tokens)
    else:
        return call_openai(messages, model=model, max_tokens=max_tokens)


REQUIRED_SECTIONS = [
    "executive summary",
    "key decisions",
    "action items",
    "discussion topics",
    "open questions",
]

MEETING_TYPE_PRIORITIES = {
    "standup": ["blockers", "progress", "action items", "open questions"],
    "planning": ["key decisions", "action items", "discussion topics", "open questions"],
    "review": ["key decisions", "discussion topics", "executive summary", "open questions"],
    "general": ["executive summary", "key decisions", "action items", "discussion topics", "open questions"],
}

MEETING_TYPE_INSTRUCTIONS = {
    "standup": (
        "This is a standup meeting. Emphasize: (1) what was completed since last standup, "
        "(2) what is planned for today, (3) blockers or impediments requiring attention. "
        "Keep the Executive Summary brief (1-2 sentences). Elevate blockers prominently in Open Questions."
    ),
    "planning": (
        "This is a planning meeting. Emphasize: (1) decisions made about scope, priorities, or approach, "
        "(2) action items with clear owners and deadlines, (3) open questions that must be resolved before work begins. "
        "Be thorough in Key Decisions and Action Items sections."
    ),
    "review": (
        "This is a review meeting. Emphasize: (1) what was reviewed and the outcome (approved/rejected/needs revision), "
        "(2) specific feedback items and who raised them, (3) decisions made about next steps. "
        "Discussion Topics should capture each reviewed item as a subsection."
    ),
    "general": (
        "This is a general meeting. Provide a balanced summary covering all sections equally. "
        "Capture all decisions, action items, and unresolved questions faithfully."
    ),
}


def check_required_sections(text):
    text_lower = text.lower()
    missing = []
    for section in REQUIRED_SECTIONS:
        if section not in text_lower:
            missing.append(section)
    return missing


def check_action_items_have_owners(text, attendees):
    action_block_match = re.search(
        r'(?:^|\n)##\s[^\n]*action items[^\n]*\n(.*?)(?=\n##\s[^#]|\Z)',
        text, re.IGNORECASE | re.DOTALL
    )
    if not action_block_match:
        return True, []
    action_block = action_block_match.group(1)
    lines = [l.strip() for l in action_block.split('\n') if l.strip() and l.strip().startswith('-')]
    unowned = []
    for line in lines:
        if "none identified" in line.lower():
            continue
        has_owner = False
        for attendee in attendees:
            if isinstance(attendee, str) and attendee.lower() in line.lower():
                has_owner = True
                break
        if not has_owner and "owner:" in line.lower() and "not specified" not in line.lower():
            has_owner = True
        if not has_owner and len(line) > 10:
            unowned.append(line[:80])
    return len(unowned) == 0, unowned


def step_1_local(inputs, context):
    """Parse Inputs and Build Extraction Plan."""
    transcript = inputs.get("transcript", "")
    attendees_raw = inputs.get("attendees", [])
    if isinstance(attendees_raw, str):
        try:
            attendees = json.loads(attendees_raw)
        except (json.JSONDecodeError, TypeError):
            attendees = [a.strip() for a in attendees_raw.split(",") if a.strip()]
    else:
        attendees = attendees_raw
    meeting_type = inputs.get("meeting_type", "general")
    meeting_title = inputs.get("meeting_title", "")
    meeting_date = inputs.get("meeting_date", "")
    focus_areas = inputs.get("focus_areas", [])

    if not transcript or len(transcript.strip()) < 100:
        return None, "Transcript is too short or empty. Minimum 100 characters required."

    if len(transcript) > 80000:
        return None, "Transcript exceeds maximum length of 80000 characters."

    if not attendees or not isinstance(attendees, list):
        return None, "Attendees must be a non-empty list."

    valid_types = ["standup", "planning", "review", "general"]
    if meeting_type not in valid_types:
        meeting_type = "general"

    word_count = len(transcript.split())
    has_decisions = any(kw in transcript.lower() for kw in ["decided", "decision", "agreed", "will", "approve", "approved"])
    has_action = any(kw in transcript.lower() for kw in ["action", "todo", "follow up", "assign", "owner", "deadline", "will do", "take care"])
    has_discussion = word_count > 50

    sufficiency_warnings = []
    if not has_decisions:
        sufficiency_warnings.append("No clear decision language detected in transcript.")
    if not has_action:
        sufficiency_warnings.append("No clear action item language detected in transcript.")
    if word_count < 50:
        sufficiency_warnings.append(f"Transcript is very short ({word_count} words); summary may be sparse.")

    priorities = MEETING_TYPE_PRIORITIES.get(meeting_type, MEETING_TYPE_PRIORITIES["general"])
    type_instructions = MEETING_TYPE_INSTRUCTIONS.get(meeting_type, MEETING_TYPE_INSTRUCTIONS["general"])

    extraction_plan = {
        "meeting_type": meeting_type,
        "meeting_title": meeting_title,
        "meeting_date": meeting_date,
        "attendees": attendees,
        "focus_areas": focus_areas if isinstance(focus_areas, list) else [],
        "section_priorities": priorities,
        "type_instructions": type_instructions,
        "transcript_word_count": word_count,
        "transcript_char_count": len(transcript),
        "sufficiency_warnings": sufficiency_warnings,
        "has_decisions": has_decisions,
        "has_action_items": has_action,
        "has_discussion": has_discussion,
        "required_sections": REQUIRED_SECTIONS,
    }

    return {"output": extraction_plan}, None


def step_2_llm(inputs, context):
    """Generate Structured Meeting Summary."""
    transcript = inputs.get("transcript", "")
    attendees_raw = inputs.get("attendees", [])
    if isinstance(attendees_raw, str):
        try:
            attendees = json.loads(attendees_raw)
        except (json.JSONDecodeError, TypeError):
            attendees = [a.strip() for a in attendees_raw.split(",") if a.strip()]
    else:
        attendees = attendees_raw
    focus_areas = inputs.get("focus_areas", [])

    plan = context.get("step_1_output", {})
    meeting_type = plan.get("meeting_type", "general")
    meeting_title = plan.get("meeting_title", "")
    meeting_date = plan.get("meeting_date", "")
    section_priorities = plan.get("section_priorities", REQUIRED_SECTIONS)
    sufficiency_warnings = plan.get("sufficiency_warnings", [])
    type_instructions = plan.get("type_instructions", MEETING_TYPE_INSTRUCTIONS["general"])

    attendees_str = ", ".join(str(a) for a in attendees) if attendees else "Not specified"
    focus_str = ", ".join(str(f) for f in focus_areas) if focus_areas else "None specified"
    priorities_str = ", ".join(section_priorities)
    warnings_str = "; ".join(sufficiency_warnings) if sufficiency_warnings else "None"

    header_parts = []
    if meeting_title:
        header_parts.append(f"Meeting Title: {meeting_title}")
    if meeting_date:
        header_parts.append(f"Meeting Date: {meeting_date}")
    header_parts.append(f"Meeting Type: {meeting_type.capitalize()}")
    header_parts.append(f"Attendees: {attendees_str}")
    header_context = "\n".join(header_parts)

    system_prompt = """You are a precise meeting analyst and summarizer. You extract structured information from meeting transcripts with strict fidelity to source content.

ANTI-FABRICATION RULES — STRICTLY ENFORCED:
- Every decision listed MUST be explicitly stated or clearly implied by exact words in the transcript.
- Every action item MUST be traceable to a specific statement in the transcript.
- Every owner attribution MUST be a person who appears by name in the transcript AND in the attendees list.
- Every deadline MUST be explicitly mentioned in the transcript — do NOT infer or estimate dates.
- If a section has no content traceable to the transcript, write "- None identified in transcript" for that section.
- Do NOT paraphrase in ways that change meaning or add implications not present in the source.
- Do NOT combine separate statements into a single decision or action item.

TRACEABILITY REQUIREMENT:
For each Key Decision and Action Item, you must be able to point to the exact sentence or exchange in the transcript that supports it. If you cannot, do not include it."""

    user_prompt = f"""Generate a structured meeting summary from the transcript below.

{header_context}
Focus Areas (prioritize these topics): {focus_str}
Section Priority Order for this {meeting_type} meeting: {priorities_str}
Meeting Type Instructions: {type_instructions}
Sufficiency Notes: {warnings_str}

OUTPUT FORMAT — Use exactly these H2 sections in this order:

## Executive Summary
2-4 sentence overview of the meeting purpose, key outcomes, and next steps. Be specific — name the actual topics discussed and decisions reached.

## Key Decisions
Bullet list of decisions made. Format each as:
- [Decision statement]: [Brief rationale if explicitly stated in transcript]
Only include decisions explicitly made or clearly agreed upon. If no decisions were made, write:
- None identified in transcript

## Action Items
Bullet list with owner and deadline. Format each as:
- [Action description]: Owner: [Name from attendees list] | Deadline: [Date if stated, otherwise 'Not specified']
Only assign owners who are named in the transcript AND appear in the attendees list.
Only include deadlines explicitly mentioned in the transcript.
If no action items were identified, write:
- None identified in transcript

## Discussion Topics
For each major topic discussed, create a subsection:
### [Topic Name]
- Summary of what was discussed (2-4 bullet points)
- Outcome or conclusion reached (if any)

## Open Questions
Bullet list of questions raised but not resolved, or items requiring follow-up.
If none, write: - None identified

## Follow-up Meetings
List any follow-up meetings mentioned or explicitly scheduled.
If none, write: - None scheduled

TRANSCRIPT:
{transcript}

ATTENDEES FOR ATTRIBUTION (only assign ownership to names from this list who appear in the transcript): {attendees_str}

Generate the complete structured summary now. Every claim must be traceable to the transcript above."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    content, error = call_resolved(messages, context, max_tokens=6000)
    if error:
        content, error = call_openai(messages, model="gpt-4o-mini", max_tokens=6000)
    if error:
        return None, error

    return {"output": content}, None


def step_3_critic(inputs, context):
    """Evaluate Summary Quality and Fidelity."""
    transcript = inputs.get("transcript", "")
    attendees_raw = inputs.get("attendees", [])
    if isinstance(attendees_raw, str):
        try:
            attendees = json.loads(attendees_raw)
        except (json.JSONDecodeError, TypeError):
            attendees = [a.strip() for a in attendees_raw.split(",") if a.strip()]
    else:
        attendees = attendees_raw

    generated_summary = context.get("improved_summary", context.get("generated_summary", ""))
    if not generated_summary:
        return None, "No generated summary found in context for critic evaluation."

    missing_sections = check_required_sections(generated_summary)
    structural_score = 10 if not missing_sections else max(1, 10 - (len(missing_sections) * 2))

    owners_ok, unowned_items = check_action_items_have_owners(generated_summary, attendees)
    if not owners_ok and unowned_items:
        structural_score = max(1, structural_score - 1)

    fabrication_flags = []
    for attendee in attendees:
        if isinstance(attendee, str) and len(attendee) > 2:
            if attendee.lower() in generated_summary.lower():
                if attendee.lower() not in transcript.lower():
                    fabrication_flags.append(f"Attendee '{attendee}' attributed in summary but not found in transcript")

    if fabrication_flags:
        structural_score = max(1, structural_score - 2)

    system_prompt = """You are a quality evaluator for meeting summaries. You assess summaries for fidelity to source transcripts, completeness, and actionability. You return structured JSON scores only. Do not include any text outside the JSON object."""

    user_prompt = f"""Evaluate this meeting summary against the source transcript.

TRANSCRIPT (source of truth):
{transcript[:6000]}

GENERATED SUMMARY:
{generated_summary}

DETERMINISTIC CHECK RESULTS:
- Missing required sections: {missing_sections if missing_sections else 'None'}
- Action items without traceable owners: {unowned_items if unowned_items else 'None'}
- Fabrication flags (content in summary not in transcript): {fabrication_flags if fabrication_flags else 'None'}

Score each dimension 1-10 where 10 is perfect:

fidelity_score: Are ALL decisions and action items directly traceable to explicit statements in the transcript? No invented content, no inferred deadlines, no fabricated attributions? Deduct points for each fabricated or unverifiable claim.

completeness_score: Are all required sections present (Executive Summary, Key Decisions, Action Items, Discussion Topics, Open Questions)? Are sections substantively filled where content exists in the transcript? Deduct points for missing sections or sections that are empty when content was available.

Return ONLY valid JSON with no surrounding text or markdown:
{{
  "fidelity_score": <integer 1-10>,
  "completeness_score": <integer 1-10>,
  "fidelity_feedback": "<specific fabrication issues found, or 'Good fidelity — all claims traceable to transcript'>",
  "completeness_feedback": "<specific missing or thin sections, or 'All sections complete and substantive'>",
  "improvement_suggestions": "<prioritized list of the most important improvements needed, or 'None required'>"
}}"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    content, error = call_resolved(messages, context, max_tokens=2000)
    if error:
        content, error = call_openai(messages, model="gpt-4o-mini", max_tokens=2000)
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
            "fidelity_score": 5,
            "completeness_score": 5,
            "fidelity_feedback": "Could not parse LLM response — manual review recommended",
            "completeness_feedback": "Could not parse LLM response — manual review recommended",
            "improvement_suggestions": "Re-evaluate manually",
        }

    fidelity_score = max(1, min(10, int(scores.get("fidelity_score", 5))))
    completeness_score = max(1, min(10, int(scores.get("completeness_score", 5))))
    quality_score = min(structural_score, fidelity_score, completeness_score)

    result = {
        "quality_score": quality_score,
        "structural_score": structural_score,
        "fidelity_score": fidelity_score,
        "completeness_score": completeness_score,
        "missing_sections": missing_sections,
        "unowned_action_items": unowned_items,
        "fabrication_flags": fabrication_flags,
        "fidelity_feedback": scores.get("fidelity_feedback", ""),
        "completeness_feedback": scores.get("completeness_feedback", ""),
        "improvement_suggestions": scores.get("improvement_suggestions", ""),
    }

    return {"output": result}, None


def step_4_llm(inputs, context):
    """Improve Summary Based on Critic Feedback."""
    transcript = inputs.get("transcript", "")
    attendees_raw = inputs.get("attendees", [])
    if isinstance(attendees_raw, str):
        try:
            attendees = json.loads(attendees_raw)
        except (json.JSONDecodeError, TypeError):
            attendees = [a.strip() for a in attendees_raw.split(",") if a.strip()]
    else:
        attendees = attendees_raw
    focus_areas = inputs.get("focus_areas", [])

    plan = context.get("step_1_output", {})
    meeting_type = plan.get("meeting_type", "general")
    meeting_title = plan.get("meeting_title", "")
    meeting_date = plan.get("meeting_date", "")
    type_instructions = plan.get("type_instructions", MEETING_TYPE_INSTRUCTIONS["general"])

    generated_summary = context.get("generated_summary", "")
    critic_output = context.get("step_3_output", {})

    missing_sections = critic_output.get("missing_sections", [])
    unowned_items = critic_output.get("unowned_action_items", [])
    fabrication_flags = critic_output.get("fabrication_flags", [])
    fidelity_feedback = critic_output.get("fidelity_feedback", "")
    completeness_feedback = critic_output.get("completeness_feedback", "")
    improvement_suggestions = critic_output.get("improvement_suggestions", "")

    attendees_str = ", ".join(str(a) for a in attendees) if attendees else "Not specified"
    focus_str = ", ".join(str(f) for f in focus_areas) if focus_areas else "None"

    header_parts = []
    if meeting_title:
        header_parts.append(f"Meeting Title: {meeting_title}")
    if meeting_date:
        header_parts.append(f"Meeting Date: {meeting_date}")
    header_parts.append(f"Meeting Type: {meeting_type.capitalize()}")
    header_context = "\n".join(header_parts)

    system_prompt = """You are a precise meeting analyst and summarizer. You extract structured information from meeting transcripts with strict fidelity to source content.

ANTI-FABRICATION RULES — STRICTLY ENFORCED:
- Every decision listed MUST be explicitly stated or clearly implied by exact words in the transcript.
- Every action item MUST be traceable to a specific statement in the transcript.
- Every owner attribution MUST be a person who appears by name in the transcript AND in the attendees list.
- Every deadline MUST be explicitly mentioned in the transcript — do NOT infer or estimate dates.
- If a section has no content traceable to the transcript, write "- None identified in transcript" for that section.
- Remove any content from the original summary that cannot be traced to the transcript."""

    user_prompt = f"""Revise the meeting summary below to address all critic feedback. Your goal is a faithful, complete, and actionable summary.

{header_context}
Attendees: {attendees_str}
Focus Areas: {focus_str}
Meeting Type Instructions: {type_instructions}

CRITIC FEEDBACK — ADDRESS EVERY ITEM:
- Missing required sections: {missing_sections if missing_sections else 'None — all sections present'}
- Action items lacking traceable owners: {unowned_items if unowned_items else 'None'}
- Fabrication flags to remove: {fabrication_flags if fabrication_flags else 'None'}
- Fidelity issues: {fidelity_feedback if fidelity_feedback else 'None'}
- Completeness issues: {completeness_feedback if completeness_feedback else 'None'}
- Priority improvements: {improvement_suggestions if improvement_suggestions else 'None'}

ORIGINAL SUMMARY TO REVISE:
{generated_summary}

TRANSCRIPT (source of truth — only use content explicitly present here):
{transcript[:8000]}

OUTPUT FORMAT — Use exactly these H2 sections in this order:

## Executive Summary
## Key Decisions
## Action Items
## Discussion Topics
## Open Questions
## Follow-up Meetings

REVISION INSTRUCTIONS:
1. Add any missing sections listed in the critic feedback.
2. Remove any content flagged as fabricated or not traceable to the transcript.
3. Add owners to action items ONLY if the owner is named in the transcript AND in the attendees list.
4. Fill thin sections with content from the transcript where available.
5. Preserve all correct content from the original summary.
6. Return the complete revised summary — do not truncate any section."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    content, error = call_resolved(messages, context, max_tokens=6000)
    if error:
        content, error = call_openai(messages, model="gpt-4o-mini", max_tokens=6000)
    if error:
        return None, error

    return {"output": content}, None


def step_5_local(inputs, context):
    """Write Final Summary Artifact."""
    improved_summary = context.get("improved_summary", "")
    generated_summary = context.get("generated_summary", "")
    final_summary = improved_summary if improved_summary else generated_summary

    if not final_summary or len(final_summary.strip()) < 50:
        return None, "Final summary is empty or too short to write as artifact."

    missing = check_required_sections(final_summary)
    if len(missing) > 3:
        return None, f"Final summary is missing too many required sections: {missing}"

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