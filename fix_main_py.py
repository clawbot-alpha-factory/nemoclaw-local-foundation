#!/usr/bin/env python3
"""
Fix CC-2 main.py patch issues:
  1. Remove misplaced 'import os' and 'from pathlib import Path' at top
  2. Fix 'state_agg' → 'aggregator' (actual variable name)
  3. Fix indented app.include_router(brain_router) → module level
  4. Add os + Path imports in correct location (after __future__)
  5. Wire app.state.ws_manager for auto-insight broadcast

Usage:
    cd ~/nemoclaw-local-foundation/command-center/backend
    python3 ../../cc2-brain/fix_main_py.py
"""

import re
from pathlib import Path

MAIN_PY = Path(__file__).parent.parent / "command-center" / "backend" / "app" / "main.py"

# Also try relative path if run from backend/
if not MAIN_PY.exists():
    MAIN_PY = Path("app/main.py")
if not MAIN_PY.exists():
    MAIN_PY = Path("command-center/backend/app/main.py")
if not MAIN_PY.exists():
    print("ERROR: Cannot find app/main.py — run from project root or backend/")
    exit(1)

print(f"Fixing: {MAIN_PY}")

content = MAIN_PY.read_text()
original = content

# --- Fix 1: Remove misplaced imports at top (lines 1-2) ---
# Pattern: file starts with 'from pathlib import Path\nimport os\n"""'
content = re.sub(
    r'^from pathlib import Path\nimport os\n',
    '',
    content,
)
print("  ✓ Removed misplaced top-level imports")

# --- Fix 2: Add os + Path imports after __future__ import ---
if "import os" not in content:
    content = content.replace(
        "from __future__ import annotations\n",
        "from __future__ import annotations\n\nimport os\nfrom pathlib import Path\n",
    )
    print("  ✓ Added os + Path imports after __future__")
elif "from pathlib import Path" not in content:
    content = content.replace(
        "import os\n",
        "import os\nfrom pathlib import Path\n",
        1,
    )
    print("  ✓ Added Path import")

# --- Fix 3: Fix state_agg → aggregator ---
content = content.replace(
    "brain_set_deps(_brain_service, state_agg)",
    "brain_set_deps(_brain_service, aggregator)",
)
print("  ✓ Fixed state_agg → aggregator")

# --- Fix 4: Fix indented app.include_router(brain_router) ---
# Remove the wrongly indented version
content = content.replace(
    "\n    # CC-2: Brain router (ask, analyze, status)\n    app.include_router(brain_router)\n",
    "",
)
# Add it at module level after the other include_router calls
content = content.replace(
    "app.include_router(health.router)\n",
    "app.include_router(health.router)\napp.include_router(brain_router)  # CC-2: Brain\n",
)
print("  ✓ Fixed brain_router indentation → module level")

# --- Fix 5: Wire app.state.ws_manager for auto-insight WS broadcast ---
# The auto-insight loop uses getattr(app.state, "ws_manager", None)
# We need to set it. Add after the yield (before shutdown) — actually, before yield.
if "app.state.ws_manager = ws_manager" not in content:
    content = content.replace(
        "_brain_asyncio.ensure_future(_auto_insight_loop())\n",
        "_brain_asyncio.ensure_future(_auto_insight_loop())\n\n"
        "    # Expose ws_manager on app.state for auto-insight broadcast\n"
        "    app.state.ws_manager = ws_manager\n",
    )
    print("  ✓ Added app.state.ws_manager wiring")

# --- Fix 6: Auto-insight should use aggregator directly, not brain_router._state_aggregator ---
content = content.replace(
    "                    _sa = brain_router._state_aggregator\n"
    "                    if _sa:\n"
    "                        _state = _sa.get_state()",
    "                    _state = aggregator.state",
)
# Clean up the now-broken indentation from removing lines
content = content.replace(
    "                    _state = aggregator.state\n"
    "                        _sd = _state.model_dump()",
    "                    _state = aggregator.state\n"
    "                    _sd = _state.model_dump()",
)
# Fix remaining over-indented lines
content = content.replace(
    "                        _insight = await _brain_service.generate_insight(_sd)\n"
    "                        if _insight.get(\"available\"):",
    "                    _insight = await _brain_service.generate_insight(_sd)\n"
    "                    if _insight.get(\"available\"):",
)
content = content.replace(
    "                            # Broadcast via WS if manager is available\n"
    "                            _wm = getattr(app.state, \"ws_manager\", None)\n"
    "                            if _wm and hasattr(_wm, \"broadcast_brain_message\"):\n"
    "                                await _wm.broadcast_brain_message({\n"
    "                                    \"type\": \"brain_insight\",\n"
    "                                    \"data\": _insight,\n"
    "                                })\n"
    "                            _logger.info(\"Auto-insight generated and broadcast\")",
    "                        # Broadcast via WS if manager is available\n"
    "                        _wm = getattr(app.state, \"ws_manager\", None)\n"
    "                        if _wm and hasattr(_wm, \"broadcast_brain_message\"):\n"
    "                            await _wm.broadcast_brain_message({\n"
    "                                \"type\": \"brain_insight\",\n"
    "                                \"data\": _insight,\n"
    "                            })\n"
    "                        _logger.info(\"Auto-insight generated and broadcast\")",
)
print("  ✓ Simplified auto-insight to use aggregator.state directly")

# --- Write ---
if content != original:
    MAIN_PY.write_text(content)
    print(f"\n  ✓ Written: {MAIN_PY}")

    # Verify compilation
    try:
        compile(content, str(MAIN_PY), "exec")
        print("  ✓ Compilation check: PASSED")
    except SyntaxError as e:
        print(f"  ✗ Compilation check: FAILED at line {e.lineno}")
        print(f"    {e.msg}")
        print("\n  Restoring backup recommended:")
        print(f"    cp .cc2-backup-*/command-center/backend/app/main.py {MAIN_PY}")
else:
    print("\n  No changes needed")
