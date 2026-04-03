# System Prompt Designer

**ID:** `g25-sys-prompt-designer` | **Version:** 1.0.0 | **Family:** F25 | **Domain:** G | **Type:** executor | **Tag:** internal

## Description

Takes a skill's purpose and LLM step descriptions (or a full skill.yaml), generates structured system prompts for each LLM step following the F35 reference pattern: role definition, explicit constraints, output format rules, and forbidden behaviors.

## Inputs

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `skill_purpose` | string | Yes | What the skill does, who it's for, what it produces |
| `skill_id` | string | Yes | Skill ID for context (e.g., e08-comp-intel-synth) |
| `tag` | string | Yes | internal, customer-facing, or dual-use — drives quality bar language |
| `skill_yaml` | string | No | Full skill.yaml content — step 1 extracts LLM steps automatically. Use this OR llm_steps. |
| `llm_steps` | string | No | JSON array of LLM step objects with step_id, step_name, step_description, step_type, input_description, output_description. Use this OR skill_yaml. |
| `execution_role` | string | No | Foundation persona. If empty, the skill generates one. |
| `domain_constraints` | string | No | Domain-specific rules the prompts must enforce |
| `output_format_preference` | string | No | What format LLM steps should output |

## Outputs

| Name | Type | Description |
|------|------|-------------|
| `result` | string | JSON object with one system prompt per LLM step |
| `result_file` | file_path | Path to the markdown artifact |
| `envelope_file` | file_path | Path to the JSON envelope |

## Steps

- **step_1** — Parse inputs and build prompt generation plan (`local`, `general_short`)
- **step_2** — Generate structured system prompts for all LLM steps (`llm`, `premium`)
- **step_3** — Evaluate prompt quality and structural completeness (`critic`, `moderate`)
- **step_4** — Improve prompts based on critic feedback (`llm`, `premium`)
- **step_5** — Validate and write prompt artifact (`local`, `general_short`)

## Quality Gate

- **Min Quality Score:** 7
- **Min Quality Score:** 10.0
- **Max Retries:** 5
- **Escalate Below:** 5.0
- **Critic Loop:** enabled, acceptance=10, max_improvements=5
- **Max Execution:** 90s
- **Max Cost:** $0.1

## Declarative Guarantees

- Every LLM step_id from input has a corresponding prompt in the output
- No prompt contains banned vague phrases
- Each prompt has role, task, constraints, and output format sections
- Each prompt explicitly references skill purpose and step-specific objective in task description
- Critic step prompts include scoring dimensions and JSON output format with quality_score
- Customer-facing tag prompts include higher quality bar language
- No prompt claims capabilities the skill does not have

## Composability

- **Output Type:** system_prompts
- **Can Feed Into:** g26-skill-template-gen
- **Accepts Input From:** g26-skill-spec-writer

## Example Usage

```json
{
  "skill_id": "g25-sys-prompt-designer",
  "inputs": {
    "skill_purpose": "An AI customer support agent that handles billing inquiries, subscription changes, and refund requests for a SaaS product. Must never promise refunds without manager approval, must always verify account ownership first.",
    "skill_id": "h40-billing-support-agent",
    "tag": "customer-facing",
    "llm_steps": "[{\"step_id\": \"step_2\", \"step_name\": \"Handle billing inquiry\", \"step_description\": \"Process the customer billing request and generate appropriate response\", \"step_type\": \"llm\", \"task_class\": \"moderate\"}]"
  }
}
```
