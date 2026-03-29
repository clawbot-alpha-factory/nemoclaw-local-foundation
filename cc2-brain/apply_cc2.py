#!/usr/bin/env python3
"""
CC-2 AI Brain — Setup Script
=============================
Copies new files and patches existing files to add AI Brain functionality
to the NemoClaw Command Center.

Usage:
    cd ~/nemoclaw-local-foundation
    python3 cc2-brain/apply_cc2.py

What this does:
  1. Backs up all files that will be modified
  2. Copies new files (brain_service.py, brain router, BrainSidebar, store)
  3. Patches main.py (adds brain imports, router, auto-insight task)
  4. Patches websocket_manager.py (adds broadcast_brain_message method)
  5. Patches frontend page.tsx (adds BrainSidebar to layout)
  6. Patches frontend useWebSocket.ts (handles brain_insight WS messages)
  7. Adds dependencies to requirements.txt and package.json
  8. Prints next steps

Safe to run multiple times — checks for existing patches before applying.
"""

import os
import sys
import shutil
import json
import re
from pathlib import Path
from datetime import datetime

# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = Path.cwd()

BACKEND = PROJECT_ROOT / "command-center" / "backend"
FRONTEND = PROJECT_ROOT / "command-center" / "frontend"
BACKUP_DIR = PROJECT_ROOT / f".cc2-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

# Text markers to detect if CC-2 patches already applied
CC2_MARKER = "# CC-2: AI Brain"
CC2_MARKER_TS = "// CC-2: AI Brain"


# ------------------------------------------------------------------
# Utilities
# ------------------------------------------------------------------

def log(msg: str, level: str = "INFO"):
    symbols = {"INFO": "✓", "WARN": "⚠", "ERROR": "✗", "STEP": "→"}
    print(f"  {symbols.get(level, '·')} {msg}")


def backup(path: Path):
    """Back up a file to the backup directory."""
    if path.exists():
        rel = path.relative_to(PROJECT_ROOT)
        dest = BACKUP_DIR / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)


def read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_file(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def insert_after(content: str, anchor: str, insertion: str) -> str:
    """Insert text after the first occurrence of anchor."""
    idx = content.find(anchor)
    if idx == -1:
        return content
    end = idx + len(anchor)
    # Find end of the anchor line
    newline_idx = content.find("\n", end)
    if newline_idx == -1:
        return content + "\n" + insertion
    return content[:newline_idx + 1] + insertion + content[newline_idx + 1:]


def insert_before(content: str, anchor: str, insertion: str) -> str:
    """Insert text before the first occurrence of anchor."""
    idx = content.find(anchor)
    if idx == -1:
        return content
    return content[:idx] + insertion + content[idx:]


# ------------------------------------------------------------------
# Step 1: Copy new files
# ------------------------------------------------------------------

def copy_new_files():
    """Copy new CC-2 files to their destinations."""
    print("\n[1/6] Copying new files...")

    copies = [
        (SCRIPT_DIR / "backend" / "app" / "brain_service.py",
         BACKEND / "app" / "brain_service.py"),
        (SCRIPT_DIR / "backend" / "app" / "routers" / "brain.py",
         BACKEND / "app" / "routers" / "brain.py"),
        (SCRIPT_DIR / "frontend" / "src" / "lib" / "store.ts",
         FRONTEND / "src" / "lib" / "store.ts"),
        (SCRIPT_DIR / "frontend" / "src" / "components" / "BrainSidebar.tsx",
         FRONTEND / "src" / "components" / "BrainSidebar.tsx"),
    ]

    for src, dest in copies:
        if not src.exists():
            log(f"Source not found: {src}", "ERROR")
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        log(f"Copied {dest.relative_to(PROJECT_ROOT)}")


# ------------------------------------------------------------------
# Step 2: Patch backend main.py
# ------------------------------------------------------------------

def patch_main_py():
    """Add brain imports, router, and auto-insight background task to main.py."""
    print("\n[2/6] Patching backend main.py...")

    main_path = BACKEND / "app" / "main.py"
    if not main_path.exists():
        log("main.py not found!", "ERROR")
        return

    backup(main_path)
    content = read_file(main_path)

    if CC2_MARKER in content:
        log("Already patched (CC-2 marker found)", "WARN")
        return

    # --- Add imports ---
    import_block = f"""
{CC2_MARKER}
import asyncio as _brain_asyncio
from .brain_service import BrainService
from .routers.brain import router as brain_router, set_dependencies as brain_set_deps
"""

    # Find a good anchor for imports — look for existing router imports
    if "from .routers" in content:
        # Insert after the last "from .routers" import line
        lines = content.split("\n")
        last_router_import = -1
        for i, line in enumerate(lines):
            if line.strip().startswith("from .routers"):
                last_router_import = i
        if last_router_import >= 0:
            lines.insert(last_router_import + 1, import_block)
            content = "\n".join(lines)
    elif "import " in content:
        # Insert after the first block of imports
        content = content.replace("from fastapi", import_block + "\nfrom fastapi", 1)
    else:
        content = import_block + "\n" + content

    # --- Add brain router inclusion ---
    # Find where state/health routers are included
    if "app.include_router" in content:
        # Find the last include_router call
        last_include = content.rfind("app.include_router")
        end_of_line = content.find("\n", last_include)
        if end_of_line > 0:
            brain_router_code = """
    # CC-2: Brain router (ask, analyze, status)
    app.include_router(brain_router)
"""
            content = content[:end_of_line + 1] + brain_router_code + content[end_of_line + 1:]

    # --- Add brain service init and auto-insight task in lifespan ---
    # Look for the lifespan function or startup logic
    # Common patterns: "async def lifespan", "state_agg", "state_aggregator"

    # Find where state_aggregator is created/started
    brain_init_code = '''
    # CC-2: Initialize Brain service
    _brain_routing_alias = os.environ.get("CC_BRAIN_ROUTING_ALIAS", "balanced")
    _brain_project_root = os.environ.get("CC_PROJECT_ROOT", str(Path(__file__).parent.parent.parent.parent))
    _brain_service = BrainService(
        project_root=_brain_project_root,
        routing_alias=_brain_routing_alias,
    )

    # Wire brain dependencies
    # Detect state aggregator variable name
'''

    auto_insight_code = '''
    # CC-2: Auto-insight background task
    _insight_interval = int(os.environ.get("CC_BRAIN_INSIGHT_INTERVAL_SECONDS", "300"))

    async def _auto_insight_loop():
        """Generate strategic insight every N seconds."""
        import logging
        _logger = logging.getLogger("cc.brain.auto")
        _logger.info(f"Auto-insight loop started (interval: {_insight_interval}s)")
        await _brain_asyncio.sleep(30)  # Wait 30s after startup before first insight
        while True:
            try:
                if _brain_service.is_available:
                    _sa = brain_router._state_aggregator
                    if _sa:
                        _state = _sa.get_state()
                        _sd = _state.model_dump() if hasattr(_state, "model_dump") else _state.dict()
                        _insight = await _brain_service.generate_insight(_sd)
                        if _insight.get("available"):
                            # Broadcast via WS if manager is available
                            _wm = getattr(app.state, "ws_manager", None)
                            if _wm and hasattr(_wm, "broadcast_brain_message"):
                                await _wm.broadcast_brain_message({
                                    "type": "brain_insight",
                                    "data": _insight,
                                })
                            _logger.info("Auto-insight generated and broadcast")
            except Exception as e:
                _logger.error(f"Auto-insight error: {e}")
            await _brain_asyncio.sleep(_insight_interval)

    _brain_asyncio.ensure_future(_auto_insight_loop())
'''

    # Try to find the yield in the lifespan (common pattern)
    yield_idx = content.find("yield")
    if yield_idx > 0:
        # Insert brain init before yield
        # But we need to wire the dependencies — find the state aggregator variable
        # Look for common variable names
        sa_var = None
        for candidate in ["state_agg", "state_aggregator", "aggregator", "sa"]:
            if f"{candidate}" in content and ("StateAggregator" in content or "state_aggregator" in content):
                # Check it's actually assigned
                pattern = rf'\b({candidate})\s*='
                match = re.search(pattern, content[:yield_idx])
                if match:
                    sa_var = match.group(1)
                    break

        if not sa_var:
            sa_var = "state_agg"  # Best guess from CC-1 patterns

        # Also find WS manager variable
        ws_var = None
        for candidate in ["ws_manager", "ws_mgr", "manager"]:
            pattern = rf'\b({candidate})\s*='
            match = re.search(pattern, content[:yield_idx])
            if match:
                ws_var = match.group(1)
                break

        wire_code = f"""
    brain_set_deps(_brain_service, {sa_var})
    if _brain_service.is_available:
        logger.info(f"Brain online: {{_brain_service.provider_info}}")
"""
        if ws_var:
            wire_code += f"        app.state.ws_manager = {ws_var}  # CC-2: expose for auto-insight\n"

        full_brain_code = brain_init_code + wire_code + auto_insight_code

        content = content[:yield_idx] + full_brain_code + "\n    " + content[yield_idx:]
    else:
        log("Could not find lifespan yield — manual wiring needed", "WARN")
        log("Add brain init code before the yield in your lifespan function", "WARN")

    # Add os and Path imports if not present
    if "import os" not in content:
        content = "import os\n" + content
    if "from pathlib import Path" not in content:
        content = "from pathlib import Path\n" + content

    write_file(main_path, content)
    log("Patched main.py (imports + router + brain init + auto-insight)")


# ------------------------------------------------------------------
# Step 3: Patch websocket_manager.py
# ------------------------------------------------------------------

def patch_ws_manager():
    """Add broadcast_brain_message method to WebSocket manager."""
    print("\n[3/6] Patching websocket_manager.py...")

    ws_path = BACKEND / "app" / "websocket_manager.py"
    if not ws_path.exists():
        log("websocket_manager.py not found!", "ERROR")
        return

    backup(ws_path)
    content = read_file(ws_path)

    if "broadcast_brain_message" in content:
        log("Already patched (broadcast_brain_message exists)", "WARN")
        return

    brain_method = '''
    # CC-2: Brain message broadcast
    async def broadcast_brain_message(self, message: dict):
        """Broadcast a brain insight/response to all connected WS clients."""
        import json as _json
        data = _json.dumps(message)
        dead = set()
        for ws in self._connections:
            try:
                await ws.send_text(data)
            except Exception:
                dead.add(ws)
        self._connections -= dead
'''

    # Find the last method in the class (look for the last "async def" or "def")
    # Insert the new method before the end of the class
    lines = content.split("\n")
    insert_idx = len(lines)

    # Find the class and its last method
    in_class = False
    last_method_end = -1
    for i, line in enumerate(lines):
        if "class " in line and "Manager" in line:
            in_class = True
        if in_class and (line.strip().startswith("async def ") or line.strip().startswith("def ")):
            last_method_end = i

    # Find the end of the last method (next line at class indent level or end of file)
    if last_method_end > 0:
        # Walk forward to find where to insert
        for i in range(last_method_end + 1, len(lines)):
            # Look for next method or end of class
            stripped = lines[i].strip()
            if stripped and not stripped.startswith("#") and not stripped.startswith("\"\"\""):
                indent = len(lines[i]) - len(lines[i].lstrip())
                if indent <= 4 and stripped:  # Back at class level or module level
                    insert_idx = i
                    break
        else:
            insert_idx = len(lines)

    lines.insert(insert_idx, brain_method)
    content = "\n".join(lines)

    write_file(ws_path, content)
    log("Patched websocket_manager.py (added broadcast_brain_message)")


# ------------------------------------------------------------------
# Step 4: Patch frontend page.tsx
# ------------------------------------------------------------------

def patch_page_tsx():
    """Add BrainSidebar import and component to page layout."""
    print("\n[4/6] Patching frontend page.tsx...")

    page_path = FRONTEND / "src" / "app" / "page.tsx"
    if not page_path.exists():
        log("page.tsx not found!", "ERROR")
        return

    backup(page_path)
    content = read_file(page_path)

    if CC2_MARKER_TS in content or "BrainSidebar" in content:
        log("Already patched (BrainSidebar reference found)", "WARN")
        return

    # Add import
    import_line = f"\n{CC2_MARKER_TS}\nimport BrainSidebar from '../components/BrainSidebar';\n"

    # Find existing component imports
    if "import Sidebar" in content or "import HomeTab" in content:
        # Insert after the last component import
        lines = content.split("\n")
        last_import = -1
        for i, line in enumerate(lines):
            if line.strip().startswith("import ") and ("components/" in line or "hooks/" in line):
                last_import = i
        if last_import >= 0:
            lines.insert(last_import + 1, import_line)
            content = "\n".join(lines)
        else:
            content = import_line + content
    else:
        content = import_line + content

    # Add BrainSidebar component to layout
    # Pattern: find </main> and add <BrainSidebar /> after it
    if "</main>" in content:
        content = content.replace("</main>", "</main>\n        <BrainSidebar />", 1)
        log("Added BrainSidebar after </main>")
    else:
        # Alternative: find the closing of the main flex container
        log("Could not find </main> tag — add <BrainSidebar /> manually to layout", "WARN")

    write_file(page_path, content)
    log("Patched page.tsx (import + component)")


# ------------------------------------------------------------------
# Step 5: Patch frontend useWebSocket.ts
# ------------------------------------------------------------------

def patch_use_websocket():
    """Add brain_insight message type handling to useWebSocket hook."""
    print("\n[5/6] Patching useWebSocket.ts...")

    ws_path = FRONTEND / "src" / "hooks" / "useWebSocket.ts"
    if not ws_path.exists():
        log("useWebSocket.ts not found!", "ERROR")
        return

    backup(ws_path)
    content = read_file(ws_path)

    if CC2_MARKER_TS in content or "brain_insight" in content:
        log("Already patched (brain_insight reference found)", "WARN")
        return

    # Add store import
    store_import = f"\n{CC2_MARKER_TS}\nimport {{ useStore }} from '../lib/store';\n"

    if "import " in content:
        # Insert after first import
        first_import_end = content.find("\n", content.find("import "))
        if first_import_end > 0:
            content = content[:first_import_end + 1] + store_import + content[first_import_end + 1:]
    else:
        content = store_import + content

    # Add brain message handling in the onmessage handler
    # Look for where parsed JSON data is handled (usually checking message type or state_version)
    brain_handler = """
        // CC-2: Handle brain insight messages from auto-insight loop
        if (parsedData?.type === 'brain_insight' && parsedData?.data) {
          const store = useStore.getState();
          store.addBrainMessage({
            role: 'assistant',
            content: parsedData.data.content,
            timestamp: parsedData.data.timestamp,
            type: 'insight',
          });
          return;  // Don't process as state update
        }
"""

    # Find the onmessage handler — look for "onmessage" or "JSON.parse"
    parse_idx = content.find("JSON.parse")
    if parse_idx > 0:
        # Find the variable assignment (e.g., "const data = JSON.parse" or "const parsedData")
        line_start = content.rfind("\n", 0, parse_idx) + 1
        line = content[line_start:content.find("\n", parse_idx)]

        # Find the variable name
        var_match = re.search(r'(?:const|let|var)\s+(\w+)\s*=\s*JSON\.parse', line)
        if var_match:
            var_name = var_match.group(1)
            # Replace 'parsedData' in our handler with actual variable name
            brain_handler = brain_handler.replace("parsedData", var_name)

        # Insert after the JSON.parse line
        next_line = content.find("\n", parse_idx)
        if next_line > 0:
            content = content[:next_line + 1] + brain_handler + content[next_line + 1:]
            log(f"Added brain_insight handler (data var: {var_match.group(1) if var_match else 'unknown'})")
        else:
            log("Could not find insertion point for brain handler", "WARN")
    else:
        log("Could not find JSON.parse in useWebSocket — manual patch needed", "WARN")

    write_file(ws_path, content)
    log("Patched useWebSocket.ts")


# ------------------------------------------------------------------
# Step 6: Update dependencies
# ------------------------------------------------------------------

def update_dependencies():
    """Add anthropic to requirements.txt and zustand to package.json."""
    print("\n[6/6] Updating dependencies...")

    # Backend: requirements.txt
    req_path = BACKEND / "requirements.txt"
    if req_path.exists():
        backup(req_path)
        content = read_file(req_path)
        new_deps = []
        if "anthropic" not in content:
            new_deps.append("anthropic>=0.40.0")
        if "openai" not in content:
            new_deps.append("openai>=1.0.0")
        if new_deps:
            content = content.rstrip() + "\n" + "\n".join(new_deps) + "\n"
            write_file(req_path, content)
            log(f"Added to requirements.txt: {', '.join(new_deps)}")
        else:
            log("requirements.txt already has LLM packages")
    else:
        log("requirements.txt not found — create it manually", "WARN")

    # Frontend: package.json
    pkg_path = FRONTEND / "package.json"
    if pkg_path.exists():
        backup(pkg_path)
        try:
            pkg = json.loads(read_file(pkg_path))
            deps = pkg.get("dependencies", {})
            added = []
            if "zustand" not in deps:
                deps["zustand"] = "^4.5.0"
                added.append("zustand")
            if added:
                pkg["dependencies"] = dict(sorted(deps.items()))
                write_file(pkg_path, json.dumps(pkg, indent=2) + "\n")
                log(f"Added to package.json: {', '.join(added)}")
            else:
                log("package.json already has zustand")
        except json.JSONDecodeError:
            log("Could not parse package.json", "ERROR")
    else:
        log("package.json not found", "WARN")


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main():
    # Verify location
    if not (BACKEND / "app" / "main.py").exists():
        print("\n  ERROR: Run this from the nemoclaw-local-foundation root directory:")
        print("    cd ~/nemoclaw-local-foundation")
        print("    python3 cc2-brain/apply_cc2.py\n")
        sys.exit(1)

    print("=" * 62)
    print("  CC-2 AI Brain — Setup Script")
    print("=" * 62)

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\n  Backup: {BACKUP_DIR.relative_to(PROJECT_ROOT)}")

    copy_new_files()
    patch_main_py()
    patch_ws_manager()
    patch_page_tsx()
    patch_use_websocket()
    update_dependencies()

    print("\n" + "=" * 62)
    print("  CC-2 Setup Complete!")
    print("=" * 62)
    print("""
  NEXT STEPS:

  1. Install backend dependencies:
     cd command-center/backend
     source ~/.venv312/bin/activate
     pip install -r requirements.txt --break-system-packages

  2. Install frontend dependencies:
     cd command-center/frontend
     npm install

  3. Set your API key (if not already done):
     echo 'ANTHROPIC_API_KEY=sk-ant-...' >> config/.env

  4. (Optional) Set brain routing alias:
     export CC_BRAIN_ROUTING_ALIAS=balanced  # or premium, fast, etc.

  5. Start backend (Terminal 1):
     cd command-center/backend
     source ~/.venv312/bin/activate
     python run.py --reload

  6. Start frontend (Terminal 2):
     cd command-center/frontend
     npm run dev

  7. Verify brain is online:
     curl -s http://127.0.0.1:8100/api/brain/status | python3 -m json.tool

  8. Open http://localhost:3000 — click the 🧠 button on the right edge

  ENVIRONMENT VARIABLES (optional):
    CC_BRAIN_ROUTING_ALIAS          — routing alias (default: balanced)
    CC_BRAIN_INSIGHT_INTERVAL_SECONDS — auto-insight interval (default: 300)
    CC_PROJECT_ROOT                 — project root path (auto-detected)

  BACKUP:
    All original files backed up to: {backup_dir}
    To revert: cp -r {backup_dir}/* .
""".format(backup_dir=BACKUP_DIR.relative_to(PROJECT_ROOT)))


if __name__ == "__main__":
    main()
