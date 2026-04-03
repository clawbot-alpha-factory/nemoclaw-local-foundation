# Meeting Summary Generator

**ID:** `e08-meeting-summary-gen` | **Version:** 1.0.0 | **Family:** F08 | **Domain:** E | **Type:** executor | **Tag:** dual-use

## Description

Generates structured meeting summaries from transcripts or notes. Produces key decisions, action items with owners and deadlines, discussion topics with outcomes, open questions, follow-up meetings needed, and an executive summary. Supports standup, planning, review, and general meeting types. Anti-fabrication enforced: all decisions and action items must be traceable to transcript content.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `transcript` | string | Yes | Full meeting transcript or detailed notes. Must contain sufficient content to extract decisions, action items, and discussion topics.  |
| `attendees` | list | Yes | List of meeting attendees. Used to validate action item ownership and attribute decisions to participants present in the meeting.  |
| `meeting_type` | string | Yes | Type of meeting being summarized. Determines summary structure and emphasis.  |
| `meeting_title` | string | No | Optional title or subject of the meeting for header context. |
| `meeting_date` | string | No | Date of the meeting in ISO 8601 format (YYYY-MM-DD). Included in the artifact header when provided; left blank if not supplied.  |
| `focus_areas` | list | No | Optional list of topics or themes to emphasize during extraction. When provided, step_2 prioritizes these areas in discussion topic coverage and elevates related decisions and action items in the summary structure.  |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | Structured meeting summary in markdown format including executive summary, key decisions, action items with owners and deadlines, discussion topics, open questions, and follow-up meetings.  |
| `result_file` | file_path | Path to the written markdown artifact file. |
| `envelope_file` | file_path | Path to the JSON envelope containing metadata and quality scores. |

## Steps

- **step_1** — Parse Inputs and Build Extraction Plan (`local`, `general_short`)
- **step_2** — Generate Structured Meeting Summary (`llm`, `premium`)
- **step_3** — Evaluate Summary Quality and Fidelity (`critic`, `moderate`)
- **step_4** — Improve Summary Based on Critic Feedback (`llm`, `premium`)
- **step_5** — Write Final Summary Artifact (`local`, `general_short`)

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=10, max_improvements=5
- **Max Execution:** 120s
- **Max Cost:** $0.35

## Declarative Guarantees

- All decisions and action items are traceable to explicit content in the source transcript.
- Action items include owner attribution drawn from the provided attendees list.
- Summary structure adapts to the specified meeting type (standup, planning, review, general).
- No content is fabricated or inferred beyond what is present in the transcript.
- Executive summary is always present and reflects the most critical outcomes.
- Open questions and follow-up meetings are surfaced when present in the transcript.
- Quality score of 7 or above is required before artifact is written.

## Composability

- **Output Type:** structured_meeting_summary
- **Can Feed Into:** d11-copywriting-specialist

## Example Usage

```json
{
  "skill_id": "e08-meeting-summary-gen",
  "inputs": {
    "transcript": "Meeting notes: Discussed Q3 roadmap priorities. Sarah proposed focusing on API stability over new features. John disagreed, wants to ship 3 new integrations by end of Q3. Team voted 4-2 in favor of stability-first approach. Action: Sarah to draft stability roadmap by Friday. John to identify which integrations can wait until Q4. Next review meeting scheduled for July 15. Budget discussion: current API spend is 5 dollars per day, need to reduce to 3 dollars per day.",
    "attendees": "Sarah (VP Engineering), John (Product Lead), Mike (DevOps), Lisa (QA Lead), Tom (Backend), Amy (Frontend)",
    "meeting_type": "planning"
  }
}
```
