#!/usr/bin/env python3
"""
NemoClaw Skill Documentation Generator v1.0.0
Generates docs/skills/{skill_id}.md for each skill from its skill.yaml.

Usage:
    python3 scripts/generate_skill_docs.py --all
    python3 scripts/generate_skill_docs.py --skill SKILL_ID
    python3 scripts/generate_skill_docs.py --dry-run
"""

import argparse
import json
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
SKILLS_DIR = REPO / "skills"
DOCS_DIR = REPO / "docs" / "skills"


def load_skill(skill_dir):
    """Load skill.yaml from a skill directory."""
    yaml_path = skill_dir / "skill.yaml"
    if not yaml_path.exists():
        return None
    with open(yaml_path) as f:
        return yaml.safe_load(f)


def load_test_input(skill_dir):
    """Load test-input.json if it exists."""
    path = skill_dir / "test-input.json"
    if not path.exists():
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def generate_doc(skill, test_input=None):
    """Generate markdown documentation from a skill dict."""
    sid = skill.get("name", "unknown")
    lines = []

    # Title and metadata
    lines.append(f"# {skill.get('display_name', sid)}")
    lines.append("")
    meta = []
    meta.append(f"**ID:** `{sid}`")
    if skill.get("version"):
        meta.append(f"**Version:** {skill['version']}")
    if skill.get("family"):
        meta.append(f"**Family:** {skill['family']}")
    if skill.get("domain"):
        meta.append(f"**Domain:** {skill['domain']}")
    if skill.get("skill_type"):
        meta.append(f"**Type:** {skill['skill_type']}")
    if skill.get("tag"):
        meta.append(f"**Tag:** {skill['tag']}")
    lines.append(" | ".join(meta))
    lines.append("")

    # Description
    desc = skill.get("description", "").strip()
    if desc:
        lines.append("## Description")
        lines.append("")
        lines.append(desc)
        lines.append("")

    # Inputs
    inputs = skill.get("inputs", [])
    if inputs:
        lines.append("## Inputs")
        lines.append("")
        lines.append("| Name | Type | Required | Description |")
        lines.append("|------|------|----------|-------------|")
        for inp in inputs:
            name = inp.get("name", "")
            typ = inp.get("type", "string")
            req = "Yes" if inp.get("required", False) else "No"
            desc = inp.get("description", "").replace("|", "\\|").replace("\n", " ")
            lines.append(f"| `{name}` | {typ} | {req} | {desc} |")
        lines.append("")

    # Outputs (can be list of dicts or a dict of name->info)
    raw_outputs = skill.get("outputs", [])
    if raw_outputs:
        lines.append("## Outputs")
        lines.append("")
        lines.append("| Name | Type | Description |")
        lines.append("|------|------|-------------|")
        if isinstance(raw_outputs, list):
            for out in raw_outputs:
                name = out.get("name", "")
                typ = out.get("type", "string")
                desc = out.get("description", "").replace("|", "\\|").replace("\n", " ")
                lines.append(f"| `{name}` | {typ} | {desc} |")
        elif isinstance(raw_outputs, dict):
            for name, info in raw_outputs.items():
                if isinstance(info, dict):
                    typ = info.get("type", "string")
                    desc = info.get("description", "").replace("|", "\\|").replace("\n", " ")
                else:
                    typ = "string"
                    desc = str(info)
                lines.append(f"| `{name}` | {typ} | {desc} |")
        lines.append("")

    # Steps
    steps = skill.get("steps", [])
    if steps:
        lines.append("## Steps")
        lines.append("")
        for step in steps:
            step_id = step.get("id", "")
            name = step.get("name", "")
            stype = step.get("step_type", "")
            tc = step.get("task_class", "")
            lines.append(f"- **{step_id}** — {name} (`{stype}`, `{tc}`)")
        lines.append("")

    # Quality Gate
    qg = skill.get("quality_gate", {})
    contracts = skill.get("contracts", {})
    mv = contracts.get("machine_validated", {})
    quality_info = mv.get("quality", {})
    if qg or quality_info:
        lines.append("## Quality Gate")
        lines.append("")
        if quality_info.get("min_quality_score"):
            lines.append(f"- **Min Quality Score:** {quality_info['min_quality_score']}")
        if qg.get("min_quality_score"):
            lines.append(f"- **Min Quality Score:** {qg['min_quality_score']}")
        if qg.get("max_retries"):
            lines.append(f"- **Max Retries:** {qg['max_retries']}")
        if qg.get("escalate_below"):
            lines.append(f"- **Escalate Below:** {qg['escalate_below']}")
        critic = skill.get("critic_loop", {})
        if critic.get("enabled"):
            lines.append(f"- **Critic Loop:** enabled, acceptance={critic.get('acceptance_score', 'N/A')}, max_improvements={critic.get('max_improvements', 'N/A')}")
        sla = mv.get("sla", {})
        if sla:
            if sla.get("max_execution_seconds"):
                lines.append(f"- **Max Execution:** {sla['max_execution_seconds']}s")
            if sla.get("max_cost_usd"):
                lines.append(f"- **Max Cost:** ${sla['max_cost_usd']}")
        lines.append("")

    # Declarative Guarantees
    guarantees = contracts.get("declarative_guarantees", [])
    if guarantees:
        lines.append("## Declarative Guarantees")
        lines.append("")
        for g in guarantees:
            lines.append(f"- {g}")
        lines.append("")

    # Composable
    comp = skill.get("composable", {})
    if comp:
        lines.append("## Composability")
        lines.append("")
        if comp.get("output_type"):
            lines.append(f"- **Output Type:** {comp['output_type']}")
        feeds = comp.get("can_feed_into", [])
        if feeds:
            lines.append(f"- **Can Feed Into:** {', '.join(feeds)}")
        accepts = comp.get("accepts_input_from", [])
        if accepts:
            lines.append(f"- **Accepts Input From:** {', '.join(accepts)}")
        lines.append("")

    # Example Usage
    if test_input:
        lines.append("## Example Usage")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(test_input, indent=2))
        lines.append("```")
        lines.append("")

    return "\n".join(lines)


def discover_skills():
    """Find all skill directories containing skill.yaml."""
    skills = []
    for d in sorted(SKILLS_DIR.iterdir()):
        if d.is_dir() and (d / "skill.yaml").exists():
            skills.append(d)
    return skills


def main():
    parser = argparse.ArgumentParser(description="Generate skill documentation")
    parser.add_argument("--all", action="store_true", help="Generate docs for all skills")
    parser.add_argument("--skill", type=str, help="Generate doc for a single skill ID")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be generated")
    args = parser.parse_args()

    if not args.all and not args.skill:
        parser.print_help()
        sys.exit(1)

    # Collect skill dirs
    if args.skill:
        skill_dir = SKILLS_DIR / args.skill
        if not skill_dir.exists():
            print(f"ERROR: Skill directory not found: {skill_dir}")
            sys.exit(1)
        skill_dirs = [skill_dir]
    else:
        skill_dirs = discover_skills()

    if not args.dry_run:
        DOCS_DIR.mkdir(parents=True, exist_ok=True)

    generated = 0
    failures = []

    for sd in skill_dirs:
        skill_id = sd.name
        try:
            skill = load_skill(sd)
            if skill is None:
                failures.append((skill_id, "skill.yaml not found or empty"))
                continue

            if args.dry_run:
                print(f"  [dry-run] {skill_id} -> docs/skills/{skill_id}.md")
                generated += 1
                continue

            test_input = load_test_input(sd)
            doc = generate_doc(skill, test_input)
            out_path = DOCS_DIR / f"{skill_id}.md"
            out_path.write_text(doc)
            generated += 1
        except Exception as e:
            failures.append((skill_id, str(e)))

    # Summary
    print(f"\n{'[DRY RUN] ' if args.dry_run else ''}Skill docs: {generated} generated, {len(failures)} failures")
    if failures:
        print("\nFailures:")
        for sid, err in failures:
            print(f"  {sid}: {err}")

    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
