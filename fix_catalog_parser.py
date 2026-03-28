#!/usr/bin/env python3
"""
Fix for skill catalog parser in state_aggregator.py
Replaces the broken regex fallback with a clean working version.

Usage:
    cd ~/nemoclaw-local-foundation
    python3 fix_catalog_parser.py
"""

import os
import sys

AGGREGATOR_PATH = "command-center/backend/app/state_aggregator.py"


def build_fixed_method():
    """Return the complete fixed _scan_registered_skills method."""
    # Using a list of lines to avoid any escaping issues
    lines = []
    lines.append('    def _scan_registered_skills(self) -> list[SkillInfo]:')
    lines.append('        """Scan docs/ for skill catalog YAML files (k40-k54 etc).')
    lines.append('')
    lines.append('        Primary: YAML parse. Fallback: regex extraction for files')
    lines.append('        with invalid YAML (unquoted colons in inputs fields).')
    lines.append('        """')
    lines.append('        registered: list[SkillInfo] = []')
    lines.append('        docs_dir = settings.docs_dir')
    lines.append('        if not docs_dir.is_dir():')
    lines.append('            return registered')
    lines.append('')
    lines.append('        for catalog_file in docs_dir.glob("skill-catalog-*.yaml"):')
    lines.append('            try:')
    lines.append('                data = yaml.safe_load(catalog_file.read_text())')
    lines.append('                if not isinstance(data, dict):')
    lines.append('                    continue')
    lines.append('')
    lines.append('                # Format 1: {skills: [...]} list of dicts with id field')
    lines.append('                skills_list = data.get("skills", None)')
    lines.append('                if isinstance(skills_list, list):')
    lines.append('                    for entry in skills_list:')
    lines.append('                        if not isinstance(entry, dict):')
    lines.append('                            continue')
    lines.append('                        sid = entry.get("id", entry.get("skill_id", ""))')
    lines.append('                        if not sid:')
    lines.append('                            continue')
    lines.append('                        registered.append(')
    lines.append('                            SkillInfo(')
    lines.append('                                skill_id=str(sid),')
    lines.append('                                family=entry.get("family", ""),')
    lines.append('                                name=entry.get("display_name", entry.get("name", str(sid))),')
    lines.append('                                status=SkillStatus.REGISTERED,')
    lines.append('                                provider=entry.get("routing", entry.get("provider", "")),')
    lines.append('                            )')
    lines.append('                        )')
    lines.append('                    continue')
    lines.append('')
    lines.append('                # Format 2: flat dict {skill_id: {name, family, ...}}')
    lines.append('                for sid, info in data.items():')
    lines.append('                    if isinstance(info, dict):')
    lines.append('                        registered.append(')
    lines.append('                            SkillInfo(')
    lines.append('                                skill_id=str(sid),')
    lines.append('                                family=info.get("family", ""),')
    lines.append('                                name=info.get("name", str(sid)),')
    lines.append('                                status=SkillStatus.REGISTERED,')
    lines.append('                                provider=info.get("provider", ""),')
    lines.append('                            )')
    lines.append('                        )')
    lines.append('')
    lines.append('            except Exception:')
    lines.append('                # YAML invalid — use regex to extract skill IDs')
    lines.append('                self._regex_parse_catalog(catalog_file, registered)')
    lines.append('')
    lines.append('        return registered')
    lines.append('')
    lines.append('    def _regex_parse_catalog(self, catalog_file, registered: list) -> None:')
    lines.append('        """Regex fallback for catalogs with invalid YAML."""')
    lines.append('        try:')
    lines.append('            raw = catalog_file.read_text()')
    lines.append('            current_id = None')
    lines.append('            current_name = None')
    lines.append('            current_family = None')
    lines.append('            current_routing = None')
    lines.append('')
    lines.append('            for line in raw.splitlines():')
    lines.append('                stripped = line.strip()')
    lines.append('')
    lines.append('                # New skill entry')
    lines.append('                if stripped.startswith("- id:"):')
    lines.append('                    # Save previous skill if exists')
    lines.append('                    if current_id:')
    lines.append('                        registered.append(SkillInfo(')
    lines.append('                            skill_id=current_id,')
    lines.append('                            family=current_family or "",')
    lines.append('                            name=current_name or current_id,')
    lines.append('                            status=SkillStatus.REGISTERED,')
    lines.append('                            provider=current_routing or "",')
    lines.append('                        ))')
    lines.append('                    current_id = stripped.split(":", 1)[1].strip()')
    lines.append('                    current_name = None')
    lines.append('                    current_family = None')
    lines.append('                    current_routing = None')
    lines.append('')
    lines.append('                elif stripped.startswith("display_name:"):')
    lines.append("                    val = stripped.split(':', 1)[1].strip()")
    lines.append("                    if val and val[0] in ('\"', \"'\"):")
    lines.append("                        val = val[1:]")
    lines.append("                    if val and val[-1] in ('\"', \"'\"):")
    lines.append("                        val = val[:-1]")
    lines.append('                    current_name = val')
    lines.append('')
    lines.append('                elif stripped.startswith("family:"):')
    lines.append('                    current_family = stripped.split(":", 1)[1].strip()')
    lines.append('')
    lines.append('                elif stripped.startswith("routing:"):')
    lines.append('                    current_routing = stripped.split(":", 1)[1].strip()')
    lines.append('')
    lines.append('            # Save last skill')
    lines.append('            if current_id:')
    lines.append('                registered.append(SkillInfo(')
    lines.append('                    skill_id=current_id,')
    lines.append('                    family=current_family or "",')
    lines.append('                    name=current_name or current_id,')
    lines.append('                    status=SkillStatus.REGISTERED,')
    lines.append('                    provider=current_routing or "",')
    lines.append('                ))')
    lines.append('')
    lines.append('            logger.info("Regex parsed %d skills from %s", ')
    lines.append('                        sum(1 for s in registered if s.skill_id.startswith("k")), ')
    lines.append('                        catalog_file.name)')
    lines.append('')
    lines.append('        except Exception:')
    lines.append('            logger.warning("Catalog regex fallback also failed: %s", catalog_file)')

    return "\n".join(lines) + "\n"


def main():
    if not os.path.exists(AGGREGATOR_PATH):
        print(f"ERROR: {AGGREGATOR_PATH} not found. Run from ~/nemoclaw-local-foundation/")
        sys.exit(1)

    with open(AGGREGATOR_PATH) as f:
        content = f.read()

    # Find the start of _scan_registered_skills method
    marker_start = "    def _scan_registered_skills(self)"
    marker_end_candidates = [
        "    # ── Agents",
        "    # ── MA Systems",
        "    def _scan_agents(self)",
    ]

    start_idx = content.find(marker_start)
    if start_idx < 0:
        print("ERROR: Could not find _scan_registered_skills method")
        sys.exit(1)

    # Find the end — next method or section
    end_idx = len(content)
    for marker in marker_end_candidates:
        idx = content.find(marker, start_idx + 1)
        if idx > 0 and idx < end_idx:
            end_idx = idx

    # Also check for _regex_parse_catalog if it already exists (from previous bad patch)
    regex_method_marker = "    def _regex_parse_catalog("
    regex_idx = content.find(regex_method_marker)
    if regex_idx > 0:
        # Find where _regex_parse_catalog ends (next method)
        next_method = end_idx
        for marker in marker_end_candidates:
            idx = content.find(marker, regex_idx + 1)
            if idx > 0 and idx < next_method:
                next_method = idx
        end_idx = next_method

    old_method = content[start_idx:end_idx]
    new_method = build_fixed_method()

    content = content[:start_idx] + new_method + "\n" + content[end_idx:]

    with open(AGGREGATOR_PATH, "w") as f:
        f.write(content)

    print("SUCCESS — catalog parser fixed")
    print(f"  Replaced {len(old_method.splitlines())} lines with {len(new_method.splitlines())} lines")
    print(f"  File: {AGGREGATOR_PATH}")
    print()
    print("If backend is running with --reload, it will pick this up automatically.")
    print("Otherwise restart: cd command-center/backend && python run.py --reload")


if __name__ == "__main__":
    main()
