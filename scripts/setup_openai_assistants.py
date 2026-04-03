#!/usr/bin/env python3
"""
NemoClaw OpenAI Assistants Setup v1.0.0
Creates, lists, and updates OpenAI Assistants for all 11 NemoClaw agents.

Each assistant gets:
  - System prompt built from agent context (format_for_provider "openai")
  - code_interpreter + file_search tools
  - Quality guide + skill reference uploaded as searchable docs

Usage:
    python3 scripts/setup_openai_assistants.py --create-all
    python3 scripts/setup_openai_assistants.py --list
    python3 scripts/setup_openai_assistants.py --update-all
    python3 scripts/setup_openai_assistants.py --delete-all --confirm
"""

import argparse
import io
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from lib.config_loader import load_routing_config, get_api_key, _load_yaml
from lib.agent_context import build_agent_context, format_for_provider, load_agent_schema

ASSISTANTS_JSON = REPO / "config" / "openai-assistants.json"
SKILLS_DIR = REPO / "skills"
LOG_DIR = Path.home() / ".nemoclaw" / "logs"

logger = logging.getLogger("nemoclaw.openai_setup")


def _setup_logging():
    """Configure logging to file and console."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(LOG_DIR / "openai-setup.log")
    fh.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    fh.setFormatter(fmt)
    ch.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(ch)
    logger.setLevel(logging.DEBUG)


def _get_client():
    """Create OpenAI client with API key from config."""
    try:
        from openai import OpenAI
    except ImportError:
        print("ERROR: openai package not installed. Run: pip install openai>=1.30")
        sys.exit(1)

    api_key = get_api_key("openai")
    if not api_key:
        print("ERROR: OPENAI_API_KEY not found in config/.env")
        sys.exit(1)

    return OpenAI(api_key=api_key)


def _resolve_model():
    """Resolve the OpenAI model from routing config (L-003 compliant)."""
    cfg = load_routing_config()
    providers = cfg.get("providers", {})
    # Prefer reasoning_openai for assistants
    entry = providers.get("reasoning_openai", providers.get("cheap_openai", {}))
    model = entry.get("model", "gpt-4o")
    alias = "reasoning_openai" if "reasoning_openai" in providers else "cheap_openai"
    return alias, model


def _build_quality_guide(agent, schema):
    """Build a markdown quality guide for an agent."""
    identity = agent.get("identity", {})
    auto_cap = agent.get("autonomous_capability", {})
    bounds = schema.get("domain_boundaries", {}).get(agent["agent_id"], {})

    lines = []
    lines.append(f"# {agent['display_name']} Quality Guide")
    lines.append(f"")
    lines.append(f"## Identity")
    lines.append(f"- **Name:** {identity.get('name', '')}")
    lines.append(f"- **Title:** {agent.get('title', '')}")
    lines.append(f"- **Authority Level:** {agent.get('authority_level', 0)}")
    lines.append(f"")

    lines.append(f"## Work Philosophy")
    lines.append(identity.get("work_philosophy", ""))
    lines.append(f"")

    lines.append(f"## Operating Principles")
    for p in identity.get("operating_principles", []):
        lines.append(f"- {p}")
    lines.append(f"")

    lines.append(f"## Quality Standards")
    lines.append(f"- **Target:** {auto_cap.get('quality_target', 9)}/10")
    lines.append(f"- **On quality below 8:** {auto_cap.get('on_quality_below_8', '')}")
    lines.append(f"- **Can self-improve:** {auto_cap.get('can_self_improve', False)}")
    lines.append(f"")

    lines.append(f"## Domain Boundaries")
    lines.append(f"- **Owns:** {', '.join(bounds.get('owns', []))}")
    forbidden = bounds.get("forbidden", [])
    lines.append(f"- **Forbidden:** {', '.join(forbidden) if forbidden else 'none'}")
    lines.append(f"")

    # Skill quality gates
    skills = agent.get("skills", {}).get("primary", [])
    lines.append(f"## Skill Quality Gates")
    for sid in skills:
        skill_yaml = SKILLS_DIR / sid / "skill.yaml"
        if not skill_yaml.exists():
            continue
        try:
            sk = _load_yaml(skill_yaml)
            contracts = sk.get("contracts", {})
            mv = contracts.get("machine_validated", {})
            guarantees = contracts.get("declarative_guarantees", [])
            quality = mv.get("quality", {})
            if quality or guarantees:
                lines.append(f"")
                lines.append(f"### {sid}")
                if quality.get("min_quality_score"):
                    lines.append(f"- Min quality: {quality['min_quality_score']}")
                sla = mv.get("sla", {})
                if sla.get("max_cost_usd"):
                    lines.append(f"- Max cost: ${sla['max_cost_usd']}")
                for g in guarantees[:5]:  # Top 5 guarantees
                    lines.append(f"- {g}")
        except Exception:
            continue

    return "\n".join(lines)


def _build_skill_reference(agent):
    """Concatenate relevant skill.yaml contents into a single reference doc."""
    skills = agent.get("skills", {}).get("primary", [])
    parts = []
    for sid in skills:
        skill_yaml = SKILLS_DIR / sid / "skill.yaml"
        if not skill_yaml.exists():
            continue
        try:
            content = skill_yaml.read_text()
            parts.append(f"--- SKILL: {sid} ---\n{content}\n")
        except Exception:
            continue
    return "\n".join(parts) if parts else None


def _retry_with_backoff(fn, max_retries=3):
    """Execute fn with exponential backoff on rate limit errors."""
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception as e:
            if "429" in str(e) or "rate" in str(e).lower():
                wait = 2 ** attempt
                logger.warning("Rate limited, waiting %ds (attempt %d/%d)", wait, attempt + 1, max_retries)
                time.sleep(wait)
            else:
                raise
    raise RuntimeError(f"Failed after {max_retries} retries")


def create_all():
    """Create OpenAI Assistants for all 11 agents."""
    client = _get_client()
    schema = load_agent_schema()
    agents = schema.get("agents", [])
    alias, model = _resolve_model()

    results = {}
    errors = []

    for agent in agents:
        aid = agent["agent_id"]
        display = agent.get("display_name", aid)

        try:
            logger.info("Creating assistant for %s...", aid)

            # Build system prompt
            ctx = build_agent_context(aid, "moderate")
            system_prompt = format_for_provider(ctx, "openai") if ctx else f"You are {display}."

            # Build quality guide
            quality_guide = _build_quality_guide(agent, schema)

            # Build skill reference
            skill_ref = _build_skill_reference(agent)

            # Upload files
            file_ids = []
            quality_file = _retry_with_backoff(lambda: client.files.create(
                file=io.BytesIO(quality_guide.encode()),
                purpose="assistants",
            ))
            file_ids.append(quality_file.id)
            logger.debug("Uploaded quality guide: %s", quality_file.id)

            if skill_ref:
                skills_file = _retry_with_backoff(lambda: client.files.create(
                    file=io.BytesIO(skill_ref.encode()),
                    purpose="assistants",
                ))
                file_ids.append(skills_file.id)
                logger.debug("Uploaded skill reference: %s", skills_file.id)

            # Create vector store
            vs = _retry_with_backoff(lambda: client.vector_stores.create(
                name=f"nemoclaw-{aid}",
            ))
            _retry_with_backoff(lambda: client.vector_stores.file_batches.create(
                vector_store_id=vs.id,
                file_ids=file_ids,
            ))
            logger.debug("Created vector store: %s", vs.id)

            # Create assistant
            assistant = _retry_with_backoff(lambda: client.beta.assistants.create(
                name=f"NemoClaw {display}",
                instructions=system_prompt,
                model=model,
                tools=[
                    {"type": "code_interpreter"},
                    {"type": "file_search"},
                ],
                tool_resources={
                    "file_search": {"vector_store_ids": [vs.id]},
                },
            ))

            results[aid] = {
                "assistant_id": assistant.id,
                "vector_store_id": vs.id,
                "file_ids": file_ids,
                "display_name": display,
            }
            logger.info("Created: %s -> %s", aid, assistant.id)

        except Exception as e:
            errors.append((aid, str(e)))
            logger.error("Failed to create %s: %s", aid, e)

    # Save results
    output = {
        "created": datetime.now(timezone.utc).isoformat(),
        "model_alias": alias,
        "model_resolved": model,
        "assistants": results,
    }
    ASSISTANTS_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(ASSISTANTS_JSON, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nCreated {len(results)}/{len(agents)} assistants. Saved to {ASSISTANTS_JSON}")
    if errors:
        print(f"\n{len(errors)} failures:")
        for aid, err in errors:
            print(f"  {aid}: {err}")
    return len(errors) == 0


def list_assistants():
    """List configured assistants from JSON."""
    if not ASSISTANTS_JSON.exists():
        print("No assistants configured yet.")
        print("Run --create-all to create them.")
        return True

    with open(ASSISTANTS_JSON) as f:
        data = json.load(f)

    model = data.get("model_resolved", "unknown")
    alias = data.get("model_alias", "unknown")
    assistants = data.get("assistants", {})

    print(f"Model: {model} (alias: {alias})")
    print(f"Created: {data.get('created', 'unknown')}")
    print(f"\n{'Agent ID':<30} {'Assistant ID':<30} {'Display Name'}")
    print("-" * 90)

    for aid in sorted(assistants.keys()):
        info = assistants[aid]
        print(f"{aid:<30} {info['assistant_id']:<30} {info['display_name']}")

    print(f"\nTotal: {len(assistants)} assistants")
    return True


def update_all():
    """Update instructions and model for all existing assistants."""
    if not ASSISTANTS_JSON.exists():
        print("ERROR: No assistants to update. Run --create-all first.")
        return False

    client = _get_client()
    schema = load_agent_schema()
    _, model = _resolve_model()

    with open(ASSISTANTS_JSON) as f:
        data = json.load(f)

    assistants = data.get("assistants", {})
    updated = 0
    errors = []

    for aid, info in assistants.items():
        try:
            ctx = build_agent_context(aid, "moderate")
            system_prompt = format_for_provider(ctx, "openai") if ctx else ""

            _retry_with_backoff(lambda: client.beta.assistants.update(
                info["assistant_id"],
                instructions=system_prompt,
                model=model,
            ))
            updated += 1
            logger.info("Updated: %s", aid)
        except Exception as e:
            errors.append((aid, str(e)))
            logger.error("Failed to update %s: %s", aid, e)

    # Update model in JSON
    data["model_resolved"] = model
    with open(ASSISTANTS_JSON, "w") as f:
        json.dump(data, f, indent=2)

    print(f"\nUpdated {updated}/{len(assistants)} assistants")
    if errors:
        print(f"\n{len(errors)} failures:")
        for aid, err in errors:
            print(f"  {aid}: {err}")
    return len(errors) == 0


def delete_all(confirm=False):
    """Delete all assistants, vector stores, and files."""
    if not confirm:
        print("ERROR: --delete-all requires --confirm flag for safety")
        return False

    if not ASSISTANTS_JSON.exists():
        print("Nothing to delete.")
        return True

    client = _get_client()

    with open(ASSISTANTS_JSON) as f:
        data = json.load(f)

    assistants = data.get("assistants", {})
    deleted = 0

    for aid, info in assistants.items():
        try:
            # Delete assistant
            client.beta.assistants.delete(info["assistant_id"])
            # Delete vector store
            if info.get("vector_store_id"):
                client.vector_stores.delete(info["vector_store_id"])
            # Delete files
            for fid in info.get("file_ids", []):
                try:
                    client.files.delete(fid)
                except Exception:
                    pass
            deleted += 1
            logger.info("Deleted: %s", aid)
        except Exception as e:
            logger.error("Failed to delete %s: %s", aid, e)

    # Remove JSON
    ASSISTANTS_JSON.unlink(missing_ok=True)
    print(f"Deleted {deleted}/{len(assistants)} assistants. Config removed.")
    return True


def main():
    _setup_logging()

    parser = argparse.ArgumentParser(description="OpenAI Assistants setup for NemoClaw agents")
    parser.add_argument("--create-all", action="store_true", help="Create assistants for all 11 agents")
    parser.add_argument("--list", action="store_true", help="List configured assistants")
    parser.add_argument("--update-all", action="store_true", help="Update instructions and model for all assistants")
    parser.add_argument("--delete-all", action="store_true", help="Delete all assistants (requires --confirm)")
    parser.add_argument("--confirm", action="store_true", help="Confirm destructive operations")
    args = parser.parse_args()

    if not (args.create_all or args.list or args.update_all or args.delete_all):
        parser.print_help()
        sys.exit(1)

    if args.create_all:
        ok = create_all()
    elif args.list:
        ok = list_assistants()
    elif args.update_all:
        ok = update_all()
    elif args.delete_all:
        ok = delete_all(confirm=args.confirm)
    else:
        ok = False

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
