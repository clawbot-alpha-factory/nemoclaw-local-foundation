#!/usr/bin/env python3
"""
NemoClaw MCP Skill Server — Exposes 124 skills as MCP tools.

Any MCP-compatible client (Claude Desktop, VS Code, Cursor) can invoke
NemoClaw skills via this server. Runs on port 8200.

Usage:
    python3 scripts/mcp_skill_server.py          # start server
    python3 scripts/mcp_skill_server.py --test    # verify tool count
    python3 scripts/mcp_skill_server.py --list    # list all tools
"""

import json
import logging
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SKILLS_DIR = REPO / "skills"
RUNNER = REPO / "skills" / "skill-runner.py"
PYTHON = str(REPO / ".venv313" / "bin" / "python3")

sys.path.insert(0, str(REPO))
logger = logging.getLogger("nemoclaw.mcp")

SKIP_DIRS = {"__pycache__", "graph-validation"}


def load_skill_catalog():
    """Load all skill metadata from skill.yaml files."""
    import yaml
    skills = {}
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        if not skill_dir.is_dir() or skill_dir.name in SKIP_DIRS:
            continue
        yaml_path = skill_dir / "skill.yaml"
        if not yaml_path.exists():
            continue
        try:
            with open(yaml_path) as f:
                data = yaml.safe_load(f)
            skills[skill_dir.name] = {
                "id": skill_dir.name,
                "name": data.get("display_name", data.get("name", skill_dir.name)),
                "description": data.get("description", ""),
                "inputs": data.get("inputs", []),
                "domain": data.get("tag", "general"),
            }
        except Exception as e:
            logger.warning(f"Failed to load {yaml_path}: {e}")
    return skills


def invoke_skill(skill_id: str, inputs: dict, timeout: int = 120) -> dict:
    """Execute a skill via skill-runner.py and return the result."""
    cmd = [PYTHON, str(RUNNER), "--skill", skill_id]
    for k, v in inputs.items():
        cmd.extend(["--input", k, str(v)])

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, cwd=str(REPO)
        )
        output = result.stdout + result.stderr

        # Find envelope
        for line in output.split("\n"):
            if "envelope_path" in line:
                try:
                    path = line.split(":")[-1].strip().strip('"')
                    if Path(path).exists():
                        return json.loads(Path(path).read_text())
                except Exception:
                    pass

        if result.returncode == 0:
            return {"success": True, "output": output[-2000:]}
        return {"success": False, "error": output[-1000:]}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Timeout after {timeout}s"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def create_mcp_server():
    """Create FastMCP server with all skills as tools."""
    try:
        from fastmcp import FastMCP
    except ImportError:
        print("ERROR: fastmcp not installed. Run: pip install fastmcp")
        sys.exit(1)

    mcp = FastMCP("NemoClaw Skills")
    catalog = load_skill_catalog()

    for skill_id, meta in catalog.items():
        safe_name = skill_id.replace("-", "_")
        desc = f"{meta['name']}: {meta['description'][:200]}"
        input_names = [inp.get("name", "input") for inp in meta.get("inputs", [])]

        # Dynamic tool registration
        def make_handler(sid, inputs):
            def handler(**kwargs) -> str:
                clean = {k: v for k, v in kwargs.items() if v is not None}
                result = invoke_skill(sid, clean)
                return json.dumps(result, indent=2, default=str)[:4000]
            handler.__name__ = safe_name
            handler.__doc__ = desc
            return handler

        mcp.tool()(make_handler(skill_id, input_names))

    return mcp, len(catalog)


# ── CLI ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if "--test" in sys.argv:
        catalog = load_skill_catalog()
        print(f"MCP server ready with {len(catalog)} tools")
        for sid in list(catalog.keys())[:5]:
            print(f"  {sid}: {catalog[sid]['name']}")
        print(f"  ... and {len(catalog)-5} more")
        sys.exit(0)

    if "--list" in sys.argv:
        catalog = load_skill_catalog()
        for sid, meta in catalog.items():
            print(f"  {sid:45s} {meta['name']}")
        print(f"\nTotal: {len(catalog)} skills")
        sys.exit(0)

    mcp, count = create_mcp_server()
    print(f"Starting NemoClaw MCP server with {count} tools on stdio...")
    mcp.run()
