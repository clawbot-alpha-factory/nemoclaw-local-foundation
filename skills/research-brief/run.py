#!/usr/bin/env python3
"""
NemoClaw Skill: research-brief
Step execution logic. Phase 6: Direct API calls — no OpenShell dependency.
Called by skill-runner.py for each step.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone


def load_env():
    """Load API keys from config/.env."""
    env_path = os.path.expanduser("~/nemoclaw-local-foundation/config/.env")
    keys = {}
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    keys[k.strip()] = v.strip()
    return keys


def call_openai(messages, model="gpt-4o-mini", max_tokens=1500):
    """Direct OpenAI API call via langchain-openai."""
    from langchain_openai import ChatOpenAI
    env = load_env()
    api_key = env.get("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
    if not api_key:
        return None, "OPENAI_API_KEY not found in config/.env"
    llm = ChatOpenAI(model=model, api_key=api_key, max_tokens=max_tokens, temperature=0.3)
    from langchain_core.messages import HumanMessage, SystemMessage
    lc_messages = []
    for m in messages:
        if m["role"] == "system":
            lc_messages.append(SystemMessage(content=m["content"]))
        else:
            lc_messages.append(HumanMessage(content=m["content"]))
    response = llm.invoke(lc_messages)
    return response.content, None


def call_anthropic(messages, model="claude-sonnet-4-6", max_tokens=1500):
    """Direct Anthropic API call via langchain-anthropic."""
    from langchain_anthropic import ChatAnthropic
    env = load_env()
    api_key = env.get("ANTHROPIC_API_KEY", os.environ.get("ANTHROPIC_API_KEY", ""))
    if not api_key:
        return None, "ANTHROPIC_API_KEY not found in config/.env"
    llm = ChatAnthropic(model=model, api_key=api_key, max_tokens=max_tokens, temperature=0.3)
    from langchain_core.messages import HumanMessage, SystemMessage
    lc_messages = []
    system_content = None
    for m in messages:
        if m["role"] == "system":
            system_content = m["content"]
        else:
            lc_messages.append(HumanMessage(content=m["content"]))
    if system_content:
        llm = ChatAnthropic(
            model=model, api_key=api_key, max_tokens=max_tokens,
            temperature=0.3,
        )
        from langchain_core.messages import SystemMessage
        lc_messages.insert(0, SystemMessage(content=system_content))
    response = llm.invoke(lc_messages)
    return response.content, None


def call_google(messages, model="gemini-2.5-flash", max_tokens=1500):
    """Direct Google API call via langchain-google-genai."""
    from langchain_google_genai import ChatGoogleGenerativeAI
    env = load_env()
    api_key = env.get("GOOGLE_API_KEY", os.environ.get("GOOGLE_API_KEY", ""))
    if not api_key:
        return None, "GOOGLE_API_KEY not found in config/.env"
    llm = ChatGoogleGenerativeAI(model=model, google_api_key=api_key, max_tokens=max_tokens)
    from langchain_core.messages import HumanMessage, SystemMessage
    lc_messages = []
    for m in messages:
        if m["role"] == "system":
            lc_messages.append(SystemMessage(content=m["content"]))
        else:
            lc_messages.append(HumanMessage(content=m["content"]))
    response = llm.invoke(lc_messages)
    return response.content, None


def step_1_validate_and_plan(inputs, context):
    """Validate topic and create research plan."""
    topic = inputs.get("topic", "").strip()
    depth = inputs.get("depth", "standard")

    if not topic or len(topic) < 5:
        return None, "Topic too short or empty"

    depth_map = {
        "brief":    "Cover the main points only. 3-4 key findings.",
        "standard": "Provide a thorough overview. 5-7 key findings.",
        "deep":     "Provide comprehensive coverage. 8+ key findings with supporting detail.",
    }
    depth_instruction = depth_map.get(depth, depth_map["standard"])

    plan = f"""Research Topic: {topic}
Depth: {depth}
Instructions: {depth_instruction}

Research Plan:
1. Background — what is this topic and why does it matter
2. Key Findings — most important facts, data, and insights
3. Open Questions — what remains unresolved or debated
4. Recommendations — actionable next steps or conclusions

Please conduct thorough research on this topic following the plan above."""

    return {"output": plan}, None


def step_2_research_topic(inputs, context):
    """Deep research using reasoning model via direct Anthropic API."""
    plan = context.get("research_plan", "")
    if not plan:
        return None, "No research plan found in context"

    messages = [
        {"role": "system", "content": "You are a rigorous research analyst. Produce structured, factual research briefs with clear sections for Background, Key Findings, Open Questions, and Recommendations."},
        {"role": "user", "content": f"""{plan}

Produce a detailed research response covering all four sections: Background, Key Findings, Open Questions, and Recommendations.
Be specific and direct. Use concrete facts where possible. Be clear about what is known vs uncertain.
Format each section with a clear markdown header."""}
    ]

    content, error = call_anthropic(messages, model="claude-sonnet-4-6", max_tokens=6000)
    if error:
        # Fallback to OpenAI if Anthropic fails
        content, error = call_openai(messages, model="gpt-4o-mini", max_tokens=6000)
    if error:
        return None, error

    return {"output": content}, None


def step_3_structure_findings(inputs, context):
    """Structure raw research into clean brief format."""
    raw = context.get("raw_research", "")
    if not raw:
        return None, "No raw research found in context"

    topic_from_plan = ""
    plan = context.get("research_plan", "")
    for line in plan.split(chr(10)):
        if line.startswith("Research Topic:"):
            topic_from_plan = line.replace("Research Topic:", "").strip()
            break

    brief = f"""# Research Brief: {topic_from_plan}

**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}
**Depth:** {inputs.get('depth', 'standard')}

---

{raw}

---

*This brief was generated by the NemoClaw research-brief skill v1.0.0*"""

    return {"output": brief}, None


def step_4_validate_output(inputs, context):
    """Validate the structured brief meets quality requirements."""
    brief = context.get("structured_brief", "")
    if not brief:
        return None, "No structured brief found in context"

    required_sections = ["Background", "Key Findings", "Open Questions", "Recommendations"]
    missing = [s for s in required_sections if s not in brief]

    if missing:
        return None, f"Brief missing required sections: {missing}"

    if len(brief) < 200:
        return None, f"Brief too short: {len(brief)} chars (minimum 200)"

    return {"output": brief, "validated_brief": brief}, None


def step_5_write_artifact(inputs, context):
    """Artifact writing is handled by skill-runner.py directly."""
    return {"output": "artifact_written"}, None


STEP_HANDLERS = {
    "step_1": step_1_validate_and_plan,
    "step_2": step_2_research_topic,
    "step_3": step_3_structure_findings,
    "step_4": step_4_validate_output,
    "step_5": step_5_write_artifact,
}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--step", required=True)
    parser.add_argument("--input", required=True)
    args = parser.parse_args()

    with open(args.input) as f:
        spec = json.load(f)

    step_id = spec["step_id"]
    inputs  = spec["inputs"]
    context = spec["context"]

    handler = STEP_HANDLERS.get(step_id)
    if not handler:
        print(json.dumps({"error": f"Unknown step: {step_id}"}))
        sys.exit(1)

    result, error = handler(inputs, context)
    if error:
        print(json.dumps({"error": error}))
        sys.exit(1)

    print(json.dumps(result))
