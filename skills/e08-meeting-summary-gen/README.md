# e08-meeting-summary-gen

**ID:** `e08-meeting-summary-gen`
**Version:** 1.0.0
**Type:** executor
**Family:** F08 | **Domain:** E | **Tag:** dual-use

## Description

Generates structured meeting summaries from transcripts or notes. Produces key decisions, action items with owners and deadlines, discussion topics with outcomes, open questions, follow-up meetings needed, and an executive summary. Supports standup, planning, review, and general meeting types. Anti-fabrication enforced: all decisions and action items must be traceable to transcript content.


## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `transcript` | string | Yes | Full meeting transcript or detailed notes. Must contain sufficient content to ex |
| `attendees` | list | Yes | List of meeting attendees. Used to validate action item ownership and attribute  |
| `meeting_type` | string | Yes | Type of meeting being summarized. Determines summary structure and emphasis.
 |
| `meeting_title` | string | No | Optional title or subject of the meeting for header context. |
| `meeting_date` | string | No | Date of the meeting in ISO 8601 format (YYYY-MM-DD). Included in the artifact he |
| `focus_areas` | list | No | Optional list of topics or themes to emphasize during extraction. When provided, |

## Execution Steps

1. **Parse Inputs and Build Extraction Plan** (local) — Validates transcript length and content sufficiency. Parses attendee list, normalizes meeting type, and constructs a structured extraction plan that guides the LLM generation step with meeting-type-specific section priorities. Incorporates focus_areas into the extraction plan when provided, flagging them as high-priority topics for step_2. Records meeting_title and meeting_date for inclusion in the artifact header.

2. **Generate Structured Meeting Summary** (llm) — Generates a comprehensive structured meeting summary from the transcript using the extraction plan produced by step_1. Extracts key decisions with attribution, action items with owners drawn from the attendees list and deadlines, discussion topics with outcomes, open questions, follow-up meetings, and an executive summary. When focus_areas are specified in the extraction plan, those topics receive elevated coverage and appear prominently in discussion topics and decisions. Applies meeting-type-specific formatting and emphasis (standup: blockers and progress; planning: goals and assignments; review: outcomes and retrospective items; general: balanced coverage). Includes meeting_title and meeting_date in the artifact header when provided. Strict anti-fabrication: every decision and action item must cite evidence from the transcript.

3. **Evaluate Summary Quality and Fidelity** (critic) — Two-layer validation of the generated summary. Deterministic checks verify: (1) presence of all required sections — executive summary, key decisions, action items, discussion topics, open questions; (2) every action item has an owner drawn from the attendees list; (3) every action item has a deadline or explicit "TBD" marker; (4) summary length is between 300 and 20000 characters; (5) no section header is empty or placeholder text. LLM evaluation scores completeness, accuracy relative to transcript, anti-fabrication compliance, clarity, and actionability on a 1–10 scale. Final quality_score is the minimum of the deterministic gate score and the LLM score to ensure both layers must pass.

4. **Improve Summary Based on Critic Feedback** (llm) — Revises the meeting summary based on specific critic feedback. Addresses identified gaps in section completeness, improves action item attribution, removes any fabricated content not traceable to the transcript, and enhances clarity and actionability of decisions and follow-ups.

5. **Write Final Summary Artifact** (local) — Final deterministic gate that confirms the selected summary output is non-empty and well-formed. Writes the artifact to the designated storage location and returns the artifact path confirmation.


## Outputs

- `result`
- `result_file`
- `envelope_file`

## Usage

```bash
.venv313/bin/python3 skills/e08-meeting-summary-gen/run.py --force --input transcript "value" --input attendees "value"
```

## Quality

- Minimum quality score: **9.0/10**
- Critic loop: enabled (up to 4 retries)
- LLM routing: via `lib/routing.py` (L-003 compliant)
