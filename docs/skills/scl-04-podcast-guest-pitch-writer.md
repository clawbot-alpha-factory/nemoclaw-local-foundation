# Podcast Guest Pitch Writer

**ID:** `scl-04-podcast-guest-pitch-writer` | **Version:** 1.0.0 | **Type:** generator | **Tag:** scale

## Description

Personalized pitches for podcast appearances. Includes talking points, bio, value prop for host's audience.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `podcast_info` | string | Yes | Podcast name, host, audience, recent episodes |
| `expertise` | string | Yes | Your expertise and unique angle |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | The generated output |
| `result_file` | file_path | Path to the markdown artifact |
| `envelope_file` | file_path | Path to JSON envelope for skill chaining |

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=N/A, max_improvements=N/A
- **Max Execution:** 120s
- **Max Cost:** $0.35

## Composability

- **Output Type:** scale_generator_output

## Example Usage

```json
{
  "inputs": {
    "podcast_info": "Podcast: 'The SaaS Growth Show' hosted by Mike Reynolds. Audience: 15K weekly listeners, mostly B2B SaaS founders and growth leaders. Recent episodes: 'Scaling to $1M ARR with a 3-person team', 'The death of traditional outbound sales', 'Building in public: lessons from 50 founders'. Format: 45-minute conversational interviews. Mike is known for asking tactical questions and prefers guests with concrete data.",
    "expertise": "Building autonomous AI systems that run entire business operations from lead generation to payment collection. Unique angle: real results from deploying multi-agent AI systems for B2B companies in the MENA region, with specific revenue numbers and ROI data from 20+ client engagements"
  }
}
```
