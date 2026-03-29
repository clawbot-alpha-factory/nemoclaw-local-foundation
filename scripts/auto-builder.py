#!/usr/bin/env python3
"""
NemoClaw Auto-Builder — Autonomous Phase Execution Engine
==========================================================
Run from repo root:
  python3 scripts/auto-builder.py              # runs next phase
  python3 scripts/auto-builder.py --phase cc-6  # runs specific phase
  python3 scripts/auto-builder.py --all         # runs all remaining phases
  python3 scripts/auto-builder.py --dry         # shows plan without executing

Uses:
  - Claude Opus 4.6 for complex tasks (services, components)
  - GPT-4o-mini for simple tasks (types, API clients, boilerplate)

Cost routing follows project rules:
  - Complex/strategic → premium (Opus 4.6)
  - Simple/boilerplate → cheapest (GPT-4o-mini)
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from textwrap import dedent

# ── Resolve paths ──────────────────────────────────────────────────────
REPO = Path(__file__).resolve().parents[1] if Path(__file__).resolve().parents[1].name == "nemoclaw-local-foundation" else Path.cwd()
APP = REPO / "command-center" / "backend" / "app"
SRC = REPO / "command-center" / "frontend" / "src"
ENV_FILE = REPO / "config" / ".env"
BACKEND_DIR = REPO / "command-center" / "backend"

# ── Load API keys ──────────────────────────────────────────────────────
def load_env():
    keys = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                keys[k.strip()] = v.strip()
    return keys

ENV = load_env()
ANTHROPIC_KEY = ENV.get("ANTHROPIC_API_KEY", "")
OPENAI_KEY = ENV.get("OPENAI_API_KEY", "")

if not ANTHROPIC_KEY or not OPENAI_KEY:
    print("ERROR: Missing API keys in config/.env")
    sys.exit(1)


# ── LLM Callers ────────────────────────────────────────────────────────
def call_opus(prompt: str, system: str = "", max_tokens: int = 16000) -> str:
    """Call Claude Opus 4.6 for complex tasks."""
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    msg = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=max_tokens,
        system=system or "You are a senior full-stack engineer. Output ONLY code. No markdown fences. No explanations.",
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


def call_mini(prompt: str, system: str = "", max_tokens: int = 8000) -> str:
    """Call GPT-4o-mini for simple/boilerplate tasks."""
    import openai
    client = openai.OpenAI(api_key=OPENAI_KEY)
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=max_tokens,
        messages=messages,
    )
    return resp.choices[0].message.content


def strip_fences(text: str) -> str:
    """Remove markdown code fences from LLM output."""
    text = text.strip()
    # Remove ```typescript, ```python, ```tsx, etc.
    text = re.sub(r'^```\w*\s*\n?', '', text)
    text = re.sub(r'\n?```\s*$', '', text)
    return text.strip()


# ── File helpers ───────────────────────────────────────────────────────
def read_file(path: Path) -> str:
    if path.exists():
        return path.read_text()
    return ""


def write_file(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    print(f"  ✓ Written: {path.relative_to(REPO)}")


def syntax_check_py(path: Path) -> bool:
    try:
        compile(path.read_text(), str(path), "exec")
        return True
    except SyntaxError as e:
        print(f"  ✗ SYNTAX ERROR in {path.relative_to(REPO)}: {e}")
        return False


# ── Context loaders ────────────────────────────────────────────────────
def get_backend_context() -> str:
    """Load key backend files for LLM context."""
    parts = ["=== BACKEND CONVENTIONS ==="]
    parts.append("- Absolute imports: from app.domain.models import X, from app.services.X import Y")
    parts.append("- Logger in main.py is 'logger' (not 'log')")
    parts.append("- Services attached to app.state in lifespan function")
    parts.append("- Router pattern: router = APIRouter(prefix='/api/...', tags=[...])")
    parts.append("")

    # Show existing router as example
    skills_router = read_file(APP / "api" / "routers" / "skills.py")
    if skills_router:
        parts.append("=== EXAMPLE ROUTER (skills.py — follow this pattern) ===")
        parts.append(skills_router[:2000])
        parts.append("")

    # Show existing service as example (truncated)
    skill_svc = read_file(APP / "services" / "skill_service.py")
    if skill_svc:
        parts.append("=== EXAMPLE SERVICE (skill_service.py — first 100 lines) ===")
        parts.append("\n".join(skill_svc.split("\n")[:100]))
        parts.append("")

    # Show main.py structure
    main_py = read_file(APP / "main.py")
    if main_py:
        parts.append("=== main.py (for patching reference) ===")
        parts.append(main_py)
        parts.append("")

    # Show domain models
    models = read_file(APP / "domain" / "models.py")
    if models:
        parts.append("=== domain/models.py (first 50 lines) ===")
        parts.append("\n".join(models.split("\n")[:50]))

    return "\n".join(parts)


def get_frontend_context() -> str:
    """Load key frontend files for LLM context."""
    parts = ["=== FRONTEND CONVENTIONS ==="]
    parts.append("- LIGHT THEME: white bg, dark text")
    parts.append("- Use nc-* Tailwind tokens: nc-bg, nc-surface, nc-surface-2, nc-border, nc-accent, nc-text, nc-text-dim")
    parts.append("- NEVER use raw zinc/gray colors")
    parts.append("- Token from localStorage: localStorage.getItem('cc-token')")
    parts.append("- API base: http://127.0.0.1:8100/api")
    parts.append("- 'use client' directive at top of all components")
    parts.append("- Import hooks: import { useState, useEffect, useCallback, useMemo } from 'react'")
    parts.append("")

    # Show existing API client as pattern
    skills_api = read_file(SRC / "lib" / "skills-api.ts")
    if skills_api:
        parts.append("=== EXAMPLE API CLIENT (skills-api.ts — follow this pattern) ===")
        parts.append(skills_api[:1500])
        parts.append("")

    # Show existing tab component (truncated)
    agents_tab = read_file(SRC / "components" / "AgentsTab.tsx")
    if agents_tab:
        parts.append("=== EXAMPLE TAB COMPONENT (AgentsTab.tsx — first 80 lines) ===")
        parts.append("\n".join(agents_tab.split("\n")[:80]))

    # Show page.tsx for patching
    page_tsx = read_file(SRC / "app" / "page.tsx")
    if page_tsx:
        parts.append("")
        parts.append("=== page.tsx (for patching reference) ===")
        parts.append(page_tsx)

    # Show sidebar
    sidebar = read_file(SRC / "components" / "Sidebar.tsx")
    if sidebar:
        parts.append("")
        parts.append("=== Sidebar.tsx (for patching reference) ===")
        parts.append(sidebar)

    return "\n".join(parts)


# ── Patching helpers ───────────────────────────────────────────────────
def patch_main_py(phase_id: str, service_import: str, router_import: str,
                  service_init: str, router_include: str):
    """Patch main.py with new imports, service init, and router inclusion."""
    content = read_file(APP / "main.py")
    changes = 0

    # Add imports after CC-5 imports
    marker = "from app.services.skill_service import SkillService"
    import_block = f"\n# ── {phase_id.upper()} imports ──\n{service_import}\n{router_import}"
    if service_import.split("import ")[-1].split()[0] not in content:
        content = content.replace(marker, marker + import_block)
        changes += 1

    # Add router inclusion after skills
    if "skills_router.router" in content and router_include.split("(")[1].split(")")[0] not in content:
        anchor = "app.include_router(skills_router.router)"
        # Find it — might be at module level or in lifespan
        if anchor in content:
            content = content.replace(anchor, anchor + f"\n{router_include}")
            changes += 1

    # Add service init before yield
    if service_init and service_init.split("=")[0].strip().split(".")[-1] not in content:
        # Find the CC-5 log line and add after
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if "CC-5:" in line and "logger.info" in line:
                indent = "    "
                init_lines = f"\n{indent}# ── {phase_id.upper()}: service init ──\n"
                for sl in service_init.strip().split("\n"):
                    init_lines += f"{indent}{sl}\n"
                lines.insert(i + 1, init_lines.rstrip())
                changes += 1
                break
        content = "\n".join(lines)

    if changes > 0:
        write_file(APP / "main.py", content)
        print(f"  ✓ Patched main.py ({changes} changes)")
    return changes


def patch_page_tsx(tab_name: str, component_name: str, tab_id: str):
    """Patch page.tsx with new tab import and render block."""
    content = read_file(SRC / "app" / "page.tsx")
    changes = 0

    # Add import
    if component_name not in content:
        anchor = "import SkillsTab"
        if anchor in content:
            idx = content.index(anchor)
            line_end = content.index("\n", idx)
            line = content[idx:line_end]
            content = content.replace(line, line + f"\nimport {component_name} from '../components/{component_name}';")
            changes += 1

    # Add render block
    if f"'{tab_id}'" not in content or f'"{tab_id}"' not in content:
        # Find skills render block and add after
        skills_pattern = "activeTab === 'skills'"
        if skills_pattern in content:
            idx = content.index(skills_pattern)
            # Find the closing brace of this block
            brace_count = 0
            end = idx
            for ci in range(idx, len(content)):
                if content[ci] == '{':
                    brace_count += 1
                elif content[ci] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end = ci + 1
                        break
            render_block = f"\n          {{activeTab === '{tab_id}' && <{component_name} />}}"
            content = content[:end] + render_block + content[end:]
            changes += 1

    if changes > 0:
        write_file(SRC / "app" / "page.tsx", content)
        print(f"  ✓ Patched page.tsx ({changes} changes)")
    return changes


def patch_sidebar(tab_id: str):
    """Enable a tab in Sidebar.tsx."""
    content = read_file(SRC / "components" / "Sidebar.tsx")
    if tab_id.lower() in content.lower():
        # Find disabled: true near the tab
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if tab_id.lower() in line.lower() and "label" in line.lower():
                for j in range(max(0, i - 3), min(len(lines), i + 5)):
                    if "disabled: true" in lines[j]:
                        lines[j] = lines[j].replace("disabled: true", "disabled: false")
                        content = "\n".join(lines)
                        write_file(SRC / "components" / "Sidebar.tsx", content)
                        print(f"  ✓ Enabled {tab_id} tab in Sidebar")
                        return True
    return False


# ── Test helpers ───────────────────────────────────────────────────────
def restart_backend() -> bool:
    """Restart backend and wait for it to be ready."""
    print("  Restarting backend...")
    subprocess.run("lsof -ti:8100 | xargs kill -9 2>/dev/null", shell=True,
                   capture_output=True)
    time.sleep(2)

    proc = subprocess.Popen(
        [sys.executable, "run.py"],
        cwd=str(BACKEND_DIR),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        env={**os.environ, "CC_BRAIN_INSIGHT_INTERVAL_SECONDS": "99999"},
    )

    # Wait for startup (max 30s)
    start = time.time()
    while time.time() - start < 30:
        time.sleep(1)
        try:
            import urllib.request
            resp = urllib.request.urlopen("http://127.0.0.1:8100/api/health", timeout=2)
            if resp.status == 200:
                print("  ✓ Backend is up")
                return True
        except Exception:
            pass

    print("  ✗ Backend failed to start in 30s")
    # Print output for debugging
    proc.terminate()
    try:
        out = proc.stdout.read().decode()[:2000]
        print(out)
    except Exception:
        pass
    return False


def smoke_test(endpoints: list[dict]) -> tuple[int, int]:
    """Test endpoints. Returns (passed, failed)."""
    import urllib.request

    # Get token
    token_file = Path.home() / ".nemoclaw" / "cc-token"
    token = token_file.read_text().strip() if token_file.exists() else ""

    passed = 0
    failed = 0

    for ep in endpoints:
        method = ep.get("method", "GET")
        path = ep["path"]
        url = f"http://127.0.0.1:8100{path}"

        try:
            req = urllib.request.Request(url)
            if ep.get("auth", True) and token:
                req.add_header("Authorization", f"Bearer {token}")
            if method == "POST":
                req.method = "POST"
                req.add_header("Content-Type", "application/json")
                req.data = json.dumps(ep.get("body", {})).encode()

            resp = urllib.request.urlopen(req, timeout=5)
            code = resp.status
            if 200 <= code < 300:
                passed += 1
                print(f"    ✓ {method} {path} → {code}")
            else:
                failed += 1
                print(f"    ✗ {method} {path} → {code}")
        except Exception as e:
            failed += 1
            print(f"    ✗ {method} {path} → {e}")

    return passed, failed


def git_commit(message: str):
    """Stage, commit, and push."""
    subprocess.run(["git", "add", "-A"], cwd=str(REPO), capture_output=True)
    result = subprocess.run(
        ["git", "--no-pager", "commit", "-m", message],
        cwd=str(REPO), capture_output=True, text=True
    )
    print(f"  {result.stdout.strip().split(chr(10))[0]}")

    result = subprocess.run(
        ["git", "push"], cwd=str(REPO), capture_output=True, text=True
    )
    if result.returncode == 0:
        print("  ✓ Pushed to origin")
    else:
        print(f"  ⚠ Push failed: {result.stderr[:200]}")


# ── Phase Definitions ──────────────────────────────────────────────────

PHASES = {
    "cc-6": {
        "name": "Operations + Finance",
        "tab_id": "operations",
        "component": "OpsTab",
        "service_file": "ops_service.py",
        "router_file": "ops.py",
        "api_client": "ops-api.ts",
        "service_spec": dedent("""
            Build an OpsService that provides:
            1. Task lifecycle management (create, assign, update status, complete)
               - Tasks stored in-memory with JSON persistence (like MessageStore pattern)
               - Task statuses: pending, in_progress, blocked, completed, cancelled
               - Tasks linked to agents and skills
            2. Budget/cost tracking dashboard data
               - Read budget data from state_aggregator
               - Compute spend-per-provider trends
               - Cost projections based on current burn rate
            3. System operations overview
               - Active task counts by status
               - Agent utilization (tasks assigned vs completed)
               - Recent activity feed (last 50 actions)

            Store tasks in data/tasks.json (same pattern as messages.json).
            Constructor takes repo_root Path.
            Expose get_dashboard(), get_tasks(), create_task(), update_task(),
            get_budget_overview(), get_activity_feed().
        """),
        "router_spec": dedent("""
            Endpoints:
            GET  /api/ops/dashboard     — summary cards (task counts, budget, activity)
            GET  /api/ops/tasks         — list tasks with filters (status, agent, skill)
            POST /api/ops/tasks         — create new task
            PATCH /api/ops/tasks/{id}   — update task status/assignment
            GET  /api/ops/budget        — budget breakdown by provider with trends
            GET  /api/ops/activity      — recent activity feed
        """),
        "tab_spec": dedent("""
            3 views: Dashboard (summary cards + activity feed), Tasks (filterable table
            with status badges, agent assignment, linked skill), Finance (budget bars
            per provider, spend projection, cost alerts).
            Include: create task modal, task status quick-update buttons.
            Use nc-* light theme tokens throughout.
        """),
        "test_endpoints": [
            {"path": "/api/ops/dashboard"},
            {"path": "/api/ops/tasks"},
            {"path": "/api/ops/budget"},
            {"path": "/api/ops/activity"},
            {"path": "/api/ops/tasks", "method": "POST", "body": {
                "title": "Test task", "description": "Auto-builder test",
                "assigned_agent": "engineering_lead", "status": "pending"
            }},
        ],
    },
    "cc-7": {
        "name": "Project Builder",
        "tab_id": "projects",
        "component": "ProjectsTab",
        "service_file": "project_service.py",
        "router_file": "projects.py",
        "api_client": "projects-api.ts",
        "service_spec": dedent("""
            Build a ProjectService that provides:
            1. Project CRUD — create, list, get, update, delete projects
               - Projects stored in-memory with JSON persistence (data/projects.json)
               - Fields: id, name, description, status (planning/active/paused/completed),
                 created_at, updated_at, assigned_agents, linked_skills, milestones, tags
            2. Project templates — predefined project structures
               - Templates: "Content Campaign", "Product Launch", "Client Onboarding",
                 "Sales Pipeline", "Research Sprint"
               - Each template pre-fills milestones and suggested skill assignments
            3. Skill-to-project mapping
               - Which skills are used in which project
               - Auto-suggest skills based on project type
            4. Milestone tracking
               - Milestones within projects with status and due dates

            Constructor takes repo_root Path and reference to skill_service.
        """),
        "router_spec": dedent("""
            Endpoints:
            GET    /api/projects/           — list projects with filters
            POST   /api/projects/           — create project (or from template)
            GET    /api/projects/templates  — list available templates
            GET    /api/projects/{id}       — single project detail
            PATCH  /api/projects/{id}       — update project
            DELETE /api/projects/{id}       — delete project
            GET    /api/projects/{id}/skills — skills linked to project
            POST   /api/projects/{id}/milestones — add milestone
        """),
        "tab_spec": dedent("""
            3 views: Projects (card grid with status badges, progress bars, agent avatars),
            Templates (template cards with "Create from Template" button),
            Timeline (milestone timeline view across all active projects).
            Include: create project modal (blank or from template), milestone inline editing.
        """),
        "test_endpoints": [
            {"path": "/api/projects/"},
            {"path": "/api/projects/templates"},
            {"path": "/api/projects/", "method": "POST", "body": {
                "name": "Test Project", "description": "Auto-builder test",
                "status": "planning"
            }},
        ],
    },
    "cc-8": {
        "name": "Client Projects",
        "tab_id": "clients",
        "component": "ClientsTab",
        "service_file": "client_service.py",
        "router_file": "clients.py",
        "api_client": "clients-api.ts",
        "service_spec": dedent("""
            Build a ClientService that provides:
            1. Client CRUD — create, list, get, update clients
               - Clients stored in-memory with JSON persistence (data/clients.json)
               - Fields: id, name, company, email, phone, status (prospect/active/churned),
                 created_at, notes, tags, assigned_agent
            2. Client-project linking — which projects belong to which client
            3. Deliverable tracking — deliverables per client project
               - Fields: id, client_id, project_id, title, status (pending/in_progress/
                 delivered/approved), due_date, delivered_at
            4. Client health score — computed from project status, deliverable timeliness,
               communication frequency (from MessageStore lane activity)

            Constructor takes repo_root Path.
        """),
        "router_spec": dedent("""
            Endpoints:
            GET    /api/clients/              — list clients with filters
            POST   /api/clients/              — create client
            GET    /api/clients/{id}           — single client detail
            PATCH  /api/clients/{id}           — update client
            GET    /api/clients/{id}/projects  — client's projects
            GET    /api/clients/{id}/deliverables — client deliverables
            POST   /api/clients/{id}/deliverables — add deliverable
            GET    /api/clients/health         — client health scores
        """),
        "tab_spec": dedent("""
            3 views: Clients (card grid with health indicators, company, status badge),
            Deliverables (table view with status, due dates, client name),
            Health (client health scores with contributing factors).
            Include: add client modal, deliverable status quick-update.
        """),
        "test_endpoints": [
            {"path": "/api/clients/"},
            {"path": "/api/clients/health"},
            {"path": "/api/clients/", "method": "POST", "body": {
                "name": "Test Client", "company": "Test Co",
                "email": "test@test.com", "status": "prospect"
            }},
        ],
    },
    "cc-9": {
        "name": "Approvals + Intelligence",
        "tab_id": "approvals",
        "component": "ApprovalsTab",
        "service_file": "approval_service.py",
        "router_file": "approvals.py",
        "api_client": "approvals-api.ts",
        "service_spec": dedent("""
            Build an ApprovalService that provides:
            1. Approval request CRUD — create, list, get, approve, reject
               - Stored in-memory with JSON persistence (data/approvals.json)
               - Fields: id, title, description, requested_by (agent_id),
                 approved_by, status (pending/approved/rejected/escalated),
                 priority (low/medium/high/critical), category (budget/task/deployment/access),
                 created_at, resolved_at, notes
            2. Approval routing — auto-assign based on category and authority level
               - Budget approvals → executive_operator
               - Task approvals → operations_lead
               - Deployment → engineering_lead
               - Escalation chain follows authority levels (4→3→2→1)
            3. Approval queue — pending items sorted by priority and age
            4. Audit trail — all approval actions logged with timestamps

            Constructor takes repo_root Path.
            Conflict resolution hierarchy: retain > close > acquire.
        """),
        "router_spec": dedent("""
            Endpoints:
            GET    /api/approvals/           — list approvals with filters (status, priority, category)
            POST   /api/approvals/           — create approval request
            GET    /api/approvals/queue      — pending approvals sorted by priority
            GET    /api/approvals/{id}        — single approval detail
            POST   /api/approvals/{id}/approve — approve with notes
            POST   /api/approvals/{id}/reject  — reject with reason
            POST   /api/approvals/{id}/escalate — escalate to higher authority
            GET    /api/approvals/audit       — audit trail
        """),
        "tab_spec": dedent("""
            3 views: Queue (pending approvals with priority badges, approve/reject buttons),
            History (resolved approvals with outcome badges),
            Audit (chronological audit trail of all approval actions).
            Include: create approval modal, inline approve/reject with notes.
        """),
        "test_endpoints": [
            {"path": "/api/approvals/"},
            {"path": "/api/approvals/queue"},
            {"path": "/api/approvals/audit"},
            {"path": "/api/approvals/", "method": "POST", "body": {
                "title": "Test Approval", "description": "Auto-builder test",
                "requested_by": "engineering_lead", "category": "task",
                "priority": "medium"
            }},
        ],
    },
    "cc-10": {
        "name": "Settings + Polish",
        "tab_id": "settings",
        "component": "SettingsTab",
        "service_file": None,  # No service needed — reads from config
        "router_file": "settings.py",
        "api_client": "settings-api.ts",
        "service_spec": None,
        "router_spec": dedent("""
            Endpoints:
            GET    /api/settings/          — current system settings (token, theme, intervals)
            GET    /api/settings/token     — current active token (for auto-setup)
            POST   /api/settings/theme     — set theme preference (light/dark)
            GET    /api/settings/system    — system info (python version, node version, git info, uptime)
            POST   /api/settings/brain/interval — update auto-insight interval
        """),
        "tab_spec": dedent("""
            Single view with sections:
            1. Token Setup — show current token with copy button, auto-set instructions
            2. Theme — light/dark toggle (store preference in localStorage)
            3. Brain Settings — auto-insight interval slider
            4. System Info — Python version, Node version, git branch/commit, uptime, API count
            5. About — NemoClaw Command Center version, repo link

            This tab fixes the known issue of manual token setup by showing the token
            directly and providing a "Copy & Apply" button.
        """),
        "test_endpoints": [
            {"path": "/api/settings/", "auth": False},
            {"path": "/api/settings/token", "auth": False},
            {"path": "/api/settings/system", "auth": False},
        ],
    },
}


# ── Phase Executor ─────────────────────────────────────────────────────

def execute_phase(phase_id: str, dry_run: bool = False):
    """Execute a single phase."""
    phase = PHASES.get(phase_id)
    if not phase:
        print(f"ERROR: Unknown phase '{phase_id}'")
        return False

    print(f"\n{'='*60}")
    print(f"  PHASE: {phase_id.upper()} — {phase['name']}")
    print(f"{'='*60}\n")

    if dry_run:
        print("  DRY RUN — showing plan only\n")
        if phase.get("service_file"):
            print(f"  Would create: app/services/{phase['service_file']}")
        print(f"  Would create: app/api/routers/{phase['router_file']}")
        print(f"  Would create: src/lib/{phase['api_client']}")
        print(f"  Would create: src/components/{phase['component']}.tsx")
        print(f"  Would patch:  app/main.py, page.tsx, Sidebar.tsx")
        print(f"  Would test:   {len(phase['test_endpoints'])} endpoints")
        return True

    backend_ctx = get_backend_context()
    frontend_ctx = get_frontend_context()

    # ── Step 1: Generate backend service (complex → Opus) ──
    if phase.get("service_file") and phase.get("service_spec"):
        svc_path = APP / "services" / phase["service_file"]
        if svc_path.exists():
            print(f"  ⏭ {svc_path.relative_to(REPO)} already exists")
        else:
            print(f"  Generating {phase['service_file']} (Opus 4.6)...")
            prompt = f"""Generate a complete Python service file for the NemoClaw Command Center.

{phase['service_spec']}

CRITICAL RULES:
- Use absolute imports: from app.config import settings, from app.domain.models import X
- Use logging: log = logging.getLogger("cc.{phase_id.replace('-','.')}")
- Include type hints
- Include docstrings
- Use Path for file operations
- JSON persistence pattern: load in __init__, save after mutations
- Data directory: self.repo_root / "command-center" / "backend" / "data"
- Generate unique IDs with uuid4().hex[:8]
- Include timestamps with datetime.now(timezone.utc).isoformat()

BACKEND CONTEXT:
{backend_ctx[:4000]}

Output ONLY the Python code. No markdown fences. No explanations."""

            code = strip_fences(call_opus(prompt))
            write_file(svc_path, code)

            if not syntax_check_py(svc_path):
                print("  Retrying service generation...")
                code = strip_fences(call_opus(prompt + "\n\nPREVIOUS ATTEMPT HAD SYNTAX ERROR. Be extra careful with indentation and string formatting."))
                write_file(svc_path, code)
                if not syntax_check_py(svc_path):
                    print("  ✗ Service file has syntax errors after 2 attempts")
                    return False

    # ── Step 2: Generate router (complex → Opus) ──
    router_path = APP / "api" / "routers" / phase["router_file"]
    if router_path.exists():
        print(f"  ⏭ {router_path.relative_to(REPO)} already exists")
    else:
        print(f"  Generating {phase['router_file']} (Opus 4.6)...")
        svc_name = phase["service_file"].replace(".py", "").replace("_", " ").title().replace(" ", "") if phase.get("service_file") else None
        svc_import = f"from app.services.{phase['service_file'][:-3]} import {svc_name}" if svc_name else ""

        prompt = f"""Generate a complete FastAPI router file for the NemoClaw Command Center.

{phase['router_spec']}

CRITICAL RULES:
- Use: from fastapi import APIRouter, Depends, Query, HTTPException, Request
- Use: from pydantic import BaseModel for request bodies
- Use: from app.auth import require_auth
- Pattern for getting service: request.app.state.{phase['service_file'][:-3] if phase.get('service_file') else 'settings'}
- router = APIRouter(prefix="/api/{phase['tab_id']}", tags=["{phase['tab_id']}"])
- All endpoints use _=Depends(require_auth) unless marked as no-auth
- For settings endpoints, some may not require auth (token, system info)
{f'- Import service: {svc_import}' if svc_import else '- No service import needed — read directly from app.state or config'}

BACKEND CONTEXT (router pattern to follow):
{backend_ctx[:3000]}

Output ONLY the Python code. No markdown fences. No explanations."""

        code = strip_fences(call_opus(prompt))
        write_file(router_path, code)

        if not syntax_check_py(router_path):
            print("  Retrying router generation...")
            code = strip_fences(call_opus(prompt + "\n\nPREVIOUS ATTEMPT HAD SYNTAX ERROR. Fix it."))
            write_file(router_path, code)
            if not syntax_check_py(router_path):
                print("  ✗ Router file has syntax errors after 2 attempts")
                return False

    # ── Step 3: Generate API client (simple → GPT-4o-mini) ──
    api_path = SRC / "lib" / phase["api_client"]
    if api_path.exists():
        print(f"  ⏭ {api_path.relative_to(REPO)} already exists")
    else:
        print(f"  Generating {phase['api_client']} (GPT-4o-mini)...")
        prompt = f"""Generate a TypeScript API client file for a Next.js frontend.

The router has these endpoints:
{phase['router_spec']}

Follow this EXACT pattern for the API client:
- const API = 'http://127.0.0.1:8100/api/{phase["tab_id"]}';
- function headers() that reads token from localStorage.getItem('cc-token')
- Export TypeScript interfaces for all data types
- Export async functions for each endpoint
- Use fetch() with proper error handling

Example pattern to follow:
{read_file(SRC / "lib" / "skills-api.ts")[:1500]}

Output ONLY the TypeScript code. No markdown fences."""

        code = strip_fences(call_opus(prompt, system="You are a TypeScript developer. Output only code.", max_tokens=8000))
        write_file(api_path, code)

    # ── Step 4: Generate tab component (complex → Opus) ──
    tab_path = SRC / "components" / f"{phase['component']}.tsx"
    if tab_path.exists():
        print(f"  ⏭ {tab_path.relative_to(REPO)} already exists")
    else:
        print(f"  Generating {phase['component']}.tsx (Opus 4.6)...")
        api_client_content = read_file(api_path)

        prompt = f"""Generate a complete React component for the NemoClaw Command Center.

Component name: {phase['component']}
File should export default function {phase['component']}()

{phase['tab_spec']}

CRITICAL RULES:
- Start with 'use client';
- Import from react: useState, useEffect, useCallback, useMemo
- Import API functions from '../lib/{phase["api_client"].replace('.ts', '')}'
- Use ONLY nc-* Tailwind tokens for colors: nc-text, nc-text-dim, nc-surface, nc-surface-2, nc-border, nc-accent, nc-bg
- NEVER use zinc, gray, slate, or any raw color classes
- Use green-100/green-800 for success badges, red-100/red-800 for error, yellow-100/yellow-800 for warning, blue-100/blue-800 for info
- Tab navigation at top with bg-nc-accent text-white for active tab
- Summary cards at top of each view
- Responsive grid: grid-cols-1 md:grid-cols-2 xl:grid-cols-3
- Modals: fixed inset-0 bg-black/40 z-50

API CLIENT (import types and functions from this):
{api_client_content[:3000]}

FRONTEND CONTEXT:
{frontend_ctx[:3000]}

Output ONLY the TSX code. No markdown fences. No explanations."""

        code = strip_fences(call_opus(prompt, max_tokens=20000))
        write_file(tab_path, code)

    # ── Step 5: Patch main.py ──
    print("  Patching main.py...")
    svc_module = phase["service_file"][:-3] if phase.get("service_file") else None
    svc_class = svc_module.replace("_", " ").title().replace(" ", "") if svc_module else None
    router_module = phase["router_file"][:-3]

    service_import_line = f"from app.services.{svc_module} import {svc_class}" if svc_class else ""
    router_import_line = f"from app.api.routers import {router_module} as {router_module}_router"

    if svc_class:
        service_init_line = f"app.state.{svc_module} = {svc_class}(Path(__file__).resolve().parents[3])\nlogger.info(f\"{phase_id.upper()}: {svc_class} initialized\")"
    else:
        service_init_line = ""

    router_include_line = f"app.include_router({router_module}_router.router)  # {phase_id.upper()}"

    patch_main_py(phase_id, service_import_line, router_import_line,
                  service_init_line, router_include_line)

    # ── Step 6: Patch page.tsx and Sidebar ──
    print("  Patching frontend...")
    patch_page_tsx(phase["name"], phase["component"], phase["tab_id"])
    patch_sidebar(phase["tab_id"])

    # ── Step 7: Restart and test ──
    print("\n  Testing...")
    if not restart_backend():
        print("  ✗ Backend failed to start — check for import errors")
        # Try to get the error
        result = subprocess.run(
            [sys.executable, "-c", f"import app.main"],
            cwd=str(BACKEND_DIR),
            capture_output=True, text=True
        )
        if result.stderr:
            print(f"  Error: {result.stderr[:500]}")
        return False

    time.sleep(2)
    passed, failed = smoke_test(phase["test_endpoints"])

    if failed > 0:
        print(f"\n  ✗ {failed} endpoint(s) failed")
        return False

    print(f"\n  ✓ All {passed} endpoints passed")

    # ── Step 8: Commit ──
    svc_desc = f"app/services/{phase['service_file']}, " if phase.get("service_file") else ""
    commit_msg = f"""feat({phase_id}): {phase['name'].lower()}

Backend: {svc_desc}app/api/routers/{phase['router_file']}, main.py patched
Frontend: src/components/{phase['component']}.tsx, src/lib/{phase['api_client']}
Sidebar + page.tsx patched, {len(phase['test_endpoints'])} endpoints verified.
Auto-built by NemoClaw Auto-Builder (Opus 4.6 + GPT-4o-mini)."""

    git_commit(commit_msg)

    print(f"\n  ✅ {phase_id.upper()} COMPLETE")
    return True


# ── Main ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="NemoClaw Auto-Builder")
    parser.add_argument("--phase", type=str, help="Run specific phase (e.g. cc-6)")
    parser.add_argument("--all", action="store_true", help="Run all remaining phases")
    parser.add_argument("--dry", action="store_true", help="Show plan without executing")
    parser.add_argument("--list", action="store_true", help="List all phases")
    args = parser.parse_args()

    if not APP.is_dir():
        print("ERROR: Run from repo root (nemoclaw-local-foundation/)")
        sys.exit(1)

    if args.list:
        print("\nAvailable phases:")
        for pid, phase in PHASES.items():
            exists = (APP / "api" / "routers" / phase["router_file"]).exists()
            status = "✅ done" if exists else "⬜ pending"
            print(f"  {pid:8s}  {phase['name']:30s}  {status}")
        return

    if args.phase:
        success = execute_phase(args.phase, dry_run=args.dry)
        sys.exit(0 if success else 1)

    if args.all:
        print("\n" + "=" * 60)
        print("  NEMOCLAW AUTO-BUILDER — FULL EXECUTION")
        print("=" * 60)

        results = {}
        for pid in PHASES:
            # Skip already-built phases
            phase = PHASES[pid]
            router_exists = (APP / "api" / "routers" / phase["router_file"]).exists()
            if router_exists and not args.dry:
                print(f"\n  ⏭ {pid.upper()} already built — skipping")
                results[pid] = "skipped"
                continue

            success = execute_phase(pid, dry_run=args.dry)
            results[pid] = "✅" if success else "✗"

            if not success and not args.dry:
                print(f"\n  ✗ {pid.upper()} FAILED — stopping")
                break

        print(f"\n{'='*60}")
        print("  RESULTS")
        print(f"{'='*60}")
        for pid, status in results.items():
            print(f"  {pid:8s}  {status}")
        return

    # Default: run next pending phase
    for pid, phase in PHASES.items():
        router_exists = (APP / "api" / "routers" / phase["router_file"]).exists()
        if not router_exists:
            print(f"\nNext phase: {pid.upper()} — {phase['name']}")
            success = execute_phase(pid, dry_run=args.dry)
            sys.exit(0 if success else 1)

    print("\n✅ All phases complete!")


if __name__ == "__main__":
    main()
