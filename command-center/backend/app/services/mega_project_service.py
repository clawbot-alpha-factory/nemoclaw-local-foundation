"""
NemoClaw Command Center — Mega Project Service (E-13)
Orchestrates tier 3/4 projects: SaaS builds, business launches, content empires.
Creates project → forms team → allocates budget → decomposes phases → assigns skills
→ creates channel → starts execution.
JSON persistence to data/mega_projects.json.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

log = logging.getLogger("cc.e-13.mega")

# ── Status Constants ─────────────────────────────────────────────────

STATUS_PLANNING = "planning"
STATUS_ACTIVE = "active"
STATUS_PAUSED = "paused"
STATUS_COMPLETED = "completed"
STATUS_CANCELLED = "cancelled"

VALID_STATUSES = {STATUS_PLANNING, STATUS_ACTIVE, STATUS_PAUSED, STATUS_COMPLETED, STATUS_CANCELLED}


class MegaProjectService:
    """Orchestrates tier 3/4 mega-projects with full lifecycle management."""

    # ── Templates ─────────────────────────────────────────────────────

    TEMPLATES: dict[str, dict[str, Any]] = {
        "saas_builder": {
            "name": "SaaS Builder",
            "description": "Full SaaS product from idea to launch — market research, spec, MVP, deployment, and go-to-market.",
            "tier": 4,
            "estimated_cost_usd": 500,
            "default_timeline_weeks": 12,
            "phases": [
                {"name": "Discovery & Research", "duration_weeks": 2, "skills": [
                    "k55-seo-keyword-researcher", "a01-arch-spec-writer",
                ], "milestone": "Market research report + initial spec"},
                {"name": "Architecture & Design", "duration_weeks": 2, "skills": [
                    "a01-arch-spec-writer", "a02-database-schema-designer",
                ], "milestone": "Technical architecture + DB schema"},
                {"name": "MVP Development", "duration_weeks": 4, "skills": [
                    "a05-api-endpoint-builder", "a06-frontend-component-gen",
                    "a07-test-case-generator",
                ], "milestone": "Deployed MVP with core features"},
                {"name": "Testing & QA", "duration_weeks": 1, "skills": [
                    "a07-test-case-generator", "a08-code-review-assistant",
                ], "milestone": "All tests passing, code reviewed"},
                {"name": "Launch & GTM", "duration_weeks": 3, "skills": [
                    "cnt-01-blog-post-writer", "cnt-06-content-calendar-builder",
                    "k55-seo-keyword-researcher",
                ], "milestone": "Product live + marketing launched"},
            ],
            "required_agents": ["strategy_lead", "dev_lead", "content_lead"],
            "milestones": [
                "Market research report + initial spec",
                "Technical architecture + DB schema",
                "Deployed MVP with core features",
                "All tests passing, code reviewed",
                "Product live + marketing launched",
            ],
        },
        "business_launcher": {
            "name": "Business Launcher",
            "description": "Launch a new business — branding, legal docs, website, content, and client acquisition.",
            "tier": 3,
            "estimated_cost_usd": 300,
            "default_timeline_weeks": 8,
            "phases": [
                {"name": "Brand & Strategy", "duration_weeks": 2, "skills": [
                    "b01-brand-voice-definer", "b02-competitive-analyzer",
                ], "milestone": "Brand guide + competitive analysis"},
                {"name": "Legal & Compliance", "duration_weeks": 1, "skills": [
                    "k57-nda-generator", "l01-legal-doc-drafter",
                ], "milestone": "NDA, terms, privacy policy drafted"},
                {"name": "Web & Digital Presence", "duration_weeks": 2, "skills": [
                    "a05-api-endpoint-builder", "a06-frontend-component-gen",
                    "k55-seo-keyword-researcher",
                ], "milestone": "Website live with SEO"},
                {"name": "Content & Marketing", "duration_weeks": 2, "skills": [
                    "cnt-01-blog-post-writer", "cnt-06-content-calendar-builder",
                    "cnt-03-social-caption-writer",
                ], "milestone": "Content pipeline running"},
                {"name": "Client Acquisition", "duration_weeks": 1, "skills": [
                    "s01-outreach-email-writer", "s02-proposal-generator",
                ], "milestone": "First outreach batch sent"},
            ],
            "required_agents": ["strategy_lead", "content_lead", "sales_lead"],
            "milestones": [
                "Brand guide + competitive analysis",
                "NDA, terms, privacy policy drafted",
                "Website live with SEO",
                "Content pipeline running",
                "First outreach batch sent",
            ],
        },
        "content_empire": {
            "name": "Content Empire",
            "description": "Build a multi-platform content machine — blog, social, video, newsletters.",
            "tier": 3,
            "estimated_cost_usd": 200,
            "default_timeline_weeks": 6,
            "phases": [
                {"name": "Content Strategy", "duration_weeks": 1, "skills": [
                    "k55-seo-keyword-researcher", "cnt-06-content-calendar-builder",
                ], "milestone": "Content strategy + calendar"},
                {"name": "Blog & SEO", "duration_weeks": 2, "skills": [
                    "cnt-01-blog-post-writer", "k55-seo-keyword-researcher",
                    "cnt-04-newsletter-composer",
                ], "milestone": "10 blog posts + newsletter template"},
                {"name": "Social Media", "duration_weeks": 1, "skills": [
                    "cnt-03-social-caption-writer", "cnt-11-agent-self-promo-generator",
                ], "milestone": "30 days of social content queued"},
                {"name": "Video & Multimedia", "duration_weeks": 1, "skills": [
                    "cnt-08-script-to-video-planner", "cnt-09-thumbnail-brief-writer",
                ], "milestone": "Video scripts + thumbnail briefs"},
                {"name": "Analytics & Optimization", "duration_weeks": 1, "skills": [
                    "k61-weekly-client-reporter",
                ], "milestone": "Reporting dashboard configured"},
            ],
            "required_agents": ["content_lead", "social_media_lead"],
            "milestones": [
                "Content strategy + calendar",
                "10 blog posts + newsletter template",
                "30 days of social content queued",
                "Video scripts + thumbnail briefs",
                "Reporting dashboard configured",
            ],
        },
        "client_engagement": {
            "name": "Client Engagement",
            "description": "Full client onboarding, deliverable pipeline, and retention workflow.",
            "tier": 3,
            "estimated_cost_usd": 150,
            "default_timeline_weeks": 4,
            "phases": [
                {"name": "Client Onboarding", "duration_weeks": 1, "skills": [
                    "s02-proposal-generator", "k57-nda-generator",
                ], "milestone": "Signed proposal + NDA"},
                {"name": "Discovery & Scoping", "duration_weeks": 1, "skills": [
                    "a01-arch-spec-writer", "b02-competitive-analyzer",
                ], "milestone": "Scope doc + competitive landscape"},
                {"name": "Deliverable Execution", "duration_weeks": 1, "skills": [
                    "cnt-01-blog-post-writer", "a05-api-endpoint-builder",
                ], "milestone": "First deliverables shipped"},
                {"name": "Reporting & Review", "duration_weeks": 1, "skills": [
                    "k61-weekly-client-reporter",
                ], "milestone": "Client report delivered"},
            ],
            "required_agents": ["sales_lead", "strategy_lead", "ops_lead"],
            "milestones": [
                "Signed proposal + NDA",
                "Scope doc + competitive landscape",
                "First deliverables shipped",
                "Client report delivered",
            ],
        },
        "research_initiative": {
            "name": "Research Initiative",
            "description": "Deep research project — market analysis, competitive intelligence, strategic recommendations.",
            "tier": 3,
            "estimated_cost_usd": 100,
            "default_timeline_weeks": 3,
            "phases": [
                {"name": "Research Design", "duration_weeks": 1, "skills": [
                    "k55-seo-keyword-researcher",
                ], "milestone": "Research plan + methodology"},
                {"name": "Data Collection", "duration_weeks": 1, "skills": [
                    "b02-competitive-analyzer", "int-05-cross-platform-scraper",
                ], "milestone": "Raw data collected + organized"},
                {"name": "Analysis & Synthesis", "duration_weeks": 0.5, "skills": [
                    "a01-arch-spec-writer",
                ], "milestone": "Analysis report drafted"},
                {"name": "Recommendations", "duration_weeks": 0.5, "skills": [
                    "s02-proposal-generator",
                ], "milestone": "Final recommendations delivered"},
            ],
            "required_agents": ["strategy_lead", "research_lead"],
            "milestones": [
                "Research plan + methodology",
                "Raw data collected + organized",
                "Analysis report drafted",
                "Final recommendations delivered",
            ],
        },
    }

    def __init__(
        self,
        repo_root: Path,
        project_service: Any = None,
        team_service: Any = None,
        execution_service: Any = None,
    ):
        self.repo_root = Path(repo_root)
        self.project_service = project_service
        self.team_service = team_service
        self.execution_service = execution_service
        self.data_dir: Path = self.repo_root / "command-center" / "backend" / "data"
        self.data_file: Path = self.data_dir / "mega_projects.json"
        self.mega_projects: dict[str, dict[str, Any]] = {}
        self._load()

    # ── Persistence ───────────────────────────────────────────────────

    def _load(self):
        """Load mega projects from disk."""
        if self.data_file.exists():
            try:
                self.mega_projects = json.loads(self.data_file.read_text())
                log.info(f"Loaded {len(self.mega_projects)} mega projects")
            except (json.JSONDecodeError, IOError) as e:
                log.warning(f"Failed to load mega projects: {e}")
                self.mega_projects = {}
        else:
            self.mega_projects = {}

    def _save(self):
        """Persist mega projects to disk."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.data_file.write_text(json.dumps(self.mega_projects, indent=2, default=str))

    # ── Templates ─────────────────────────────────────────────────────

    def list_templates(self) -> list[dict[str, Any]]:
        """Return all mega project templates."""
        result = []
        for tid, t in self.TEMPLATES.items():
            result.append({
                "id": tid,
                "name": t["name"],
                "description": t["description"],
                "tier": t["tier"],
                "estimated_cost_usd": t["estimated_cost_usd"],
                "default_timeline_weeks": t["default_timeline_weeks"],
                "phase_count": len(t["phases"]),
                "required_agents": t["required_agents"],
            })
        return result

    def get_template(self, template_id: str) -> Optional[dict[str, Any]]:
        """Return a single template by ID."""
        t = self.TEMPLATES.get(template_id)
        if not t:
            return None
        return {"id": template_id, **t}

    # ── CRUD ──────────────────────────────────────────────────────────

    def create_mega_project(
        self,
        name: str,
        description: str,
        template_id: str,
        budget_usd: float = 0,
        objectives: Optional[list[str]] = None,
        timeline_weeks: Optional[int] = None,
    ) -> Optional[dict[str, Any]]:
        """Create a mega project from a template with full orchestration."""
        template = self.TEMPLATES.get(template_id)
        if not template:
            log.error(f"Unknown template: {template_id}")
            return None

        now = datetime.now(timezone.utc).isoformat()
        project_id = f"mega-{uuid4().hex[:12]}"
        effective_timeline = timeline_weeks or template["default_timeline_weeks"]
        effective_budget = budget_usd or template["estimated_cost_usd"]

        # Build phases with computed dates
        phases = []
        week_cursor = 0
        for i, phase_def in enumerate(template["phases"]):
            duration = phase_def["duration_weeks"]
            start_week = week_cursor
            end_week = week_cursor + duration
            phases.append({
                "id": f"phase-{i + 1}",
                "name": phase_def["name"],
                "status": "pending",
                "start_week": start_week,
                "end_week": end_week,
                "duration_weeks": duration,
                "skills": phase_def["skills"],
                "milestone": phase_def["milestone"],
                "started_at": None,
                "completed_at": None,
            })
            week_cursor = end_week

        # Build milestones
        milestones = []
        for i, ms_text in enumerate(template["milestones"]):
            milestones.append({
                "id": f"ms-{uuid4().hex[:8]}",
                "title": ms_text,
                "status": "pending",
                "phase_id": f"phase-{i + 1}",
                "created_at": now,
                "completed_at": None,
            })

        # Form team assignment
        team = []
        for agent_id in template["required_agents"]:
            team.append({
                "agent_id": agent_id,
                "role": "contributor",
                "assigned_at": now,
            })
        if team:
            team[0]["role"] = "lead"

        # Collect all required skills
        all_skills = []
        for phase_def in template["phases"]:
            for sid in phase_def["skills"]:
                if sid not in all_skills:
                    all_skills.append(sid)

        mega = {
            "id": project_id,
            "name": name,
            "description": description,
            "template_id": template_id,
            "template_name": template["name"],
            "tier": template["tier"],
            "status": STATUS_PLANNING,
            "budget_usd": effective_budget,
            "spent_usd": 0.0,
            "objectives": objectives or [],
            "timeline_weeks": effective_timeline,
            "phases": phases,
            "milestones": milestones,
            "team": team,
            "skills": all_skills,
            "channel_id": f"mega-{project_id}",
            "progress_pct": 0.0,
            "created_at": now,
            "updated_at": now,
            "started_at": None,
            "completed_at": None,
            "paused_at": None,
            "cancelled_at": None,
        }

        self.mega_projects[project_id] = mega
        self._save()
        log.info(f"Created mega project '{name}' ({project_id}) from template '{template_id}'")
        return mega

    def list_mega_projects(
        self,
        status: Optional[str] = None,
        tier: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """List all mega projects, optionally filtered."""
        results = list(self.mega_projects.values())
        if status:
            results = [p for p in results if p.get("status") == status]
        if tier is not None:
            results = [p for p in results if p.get("tier") == tier]
        results.sort(key=lambda p: p.get("created_at", ""), reverse=True)
        return results

    def get_mega_project(self, project_id: str) -> Optional[dict[str, Any]]:
        """Get a single mega project by ID."""
        return self.mega_projects.get(project_id)

    def get_dashboard(self, project_id: str) -> Optional[dict[str, Any]]:
        """Build a dashboard view for a mega project."""
        mega = self.mega_projects.get(project_id)
        if not mega:
            return None

        phases = mega.get("phases", [])
        total_phases = len(phases)
        completed_phases = sum(1 for p in phases if p["status"] == "completed")
        active_phases = sum(1 for p in phases if p["status"] == "active")

        milestones = mega.get("milestones", [])
        total_milestones = len(milestones)
        completed_milestones = sum(1 for m in milestones if m["status"] == "completed")

        return {
            "id": mega["id"],
            "name": mega["name"],
            "status": mega["status"],
            "tier": mega["tier"],
            "template_name": mega["template_name"],
            "progress_pct": mega.get("progress_pct", 0.0),
            "budget": {
                "total_usd": mega["budget_usd"],
                "spent_usd": mega["spent_usd"],
                "remaining_usd": mega["budget_usd"] - mega["spent_usd"],
                "utilization_pct": round(
                    (mega["spent_usd"] / mega["budget_usd"] * 100) if mega["budget_usd"] > 0 else 0, 1
                ),
            },
            "phases": {
                "total": total_phases,
                "completed": completed_phases,
                "active": active_phases,
                "pending": total_phases - completed_phases - active_phases,
            },
            "milestones": {
                "total": total_milestones,
                "completed": completed_milestones,
                "pending": total_milestones - completed_milestones,
            },
            "team": mega.get("team", []),
            "timeline_weeks": mega["timeline_weeks"],
            "created_at": mega["created_at"],
            "started_at": mega.get("started_at"),
        }

    # ── Lifecycle Actions ─────────────────────────────────────────────

    def _update_progress(self, mega: dict[str, Any]):
        """Recalculate progress_pct from phase completion."""
        phases = mega.get("phases", [])
        if not phases:
            mega["progress_pct"] = 0.0
            return
        completed = sum(1 for p in phases if p["status"] == "completed")
        mega["progress_pct"] = round(completed / len(phases) * 100, 1)

    def pause_project(self, project_id: str) -> Optional[dict[str, Any]]:
        """Pause an active mega project."""
        mega = self.mega_projects.get(project_id)
        if not mega:
            return None
        if mega["status"] not in (STATUS_ACTIVE, STATUS_PLANNING):
            return None

        now = datetime.now(timezone.utc).isoformat()
        mega["status"] = STATUS_PAUSED
        mega["paused_at"] = now
        mega["updated_at"] = now

        # Pause active phases
        for phase in mega.get("phases", []):
            if phase["status"] == "active":
                phase["status"] = "paused"

        self._save()
        log.info(f"Paused mega project {project_id}")
        return mega

    def resume_project(self, project_id: str) -> Optional[dict[str, Any]]:
        """Resume a paused mega project."""
        mega = self.mega_projects.get(project_id)
        if not mega:
            return None
        if mega["status"] != STATUS_PAUSED:
            return None

        now = datetime.now(timezone.utc).isoformat()
        mega["status"] = STATUS_ACTIVE
        mega["paused_at"] = None
        mega["updated_at"] = now

        # Resume paused phases
        for phase in mega.get("phases", []):
            if phase["status"] == "paused":
                phase["status"] = "active"

        self._save()
        log.info(f"Resumed mega project {project_id}")
        return mega

    def cancel_project(self, project_id: str) -> Optional[dict[str, Any]]:
        """Cancel a mega project."""
        mega = self.mega_projects.get(project_id)
        if not mega:
            return None
        if mega["status"] in (STATUS_COMPLETED, STATUS_CANCELLED):
            return None

        now = datetime.now(timezone.utc).isoformat()
        mega["status"] = STATUS_CANCELLED
        mega["cancelled_at"] = now
        mega["updated_at"] = now

        # Cancel all non-completed phases
        for phase in mega.get("phases", []):
            if phase["status"] not in ("completed",):
                phase["status"] = "cancelled"

        self._save()
        log.info(f"Cancelled mega project {project_id}")
        return mega
