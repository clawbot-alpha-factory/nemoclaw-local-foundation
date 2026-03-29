"""
NemoClaw Command Center — Project Service (CC-7)
Manages projects with CRUD, templates, skill mapping, and milestone tracking.
JSON persistence to data/projects.json.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

log = logging.getLogger("cc.cc.7")


class ProjectService:
    """Central service for project management, templates, skill mapping, and milestones."""

    # ── Project Templates ──────────────────────────────────────────────────

    TEMPLATES: dict[str, dict[str, Any]] = {
        "content_campaign": {
            "name": "Content Campaign",
            "description": "End-to-end content creation and distribution campaign.",
            "status": "planning",
            "tags": ["content", "marketing", "campaign"],
            "suggested_skills": [
                "content-writing",
                "seo-optimization",
                "social-media-publishing",
                "analytics-reporting",
                "graphic-design",
            ],
            "milestones": [
                {
                    "title": "Strategy & Planning",
                    "description": "Define target audience, channels, and content calendar.",
                    "status": "pending",
                    "due_offset_days": 7,
                },
                {
                    "title": "Content Creation",
                    "description": "Draft, review, and finalize all content assets.",
                    "status": "pending",
                    "due_offset_days": 21,
                },
                {
                    "title": "Design & Assets",
                    "description": "Create visual assets, thumbnails, and graphics.",
                    "status": "pending",
                    "due_offset_days": 28,
                },
                {
                    "title": "Publishing & Distribution",
                    "description": "Schedule and publish content across all channels.",
                    "status": "pending",
                    "due_offset_days": 35,
                },
                {
                    "title": "Analytics & Review",
                    "description": "Measure performance metrics and compile report.",
                    "status": "pending",
                    "due_offset_days": 49,
                },
            ],
        },
        "product_launch": {
            "name": "Product Launch",
            "description": "Coordinate a full product launch from pre-launch to post-launch.",
            "status": "planning",
            "tags": ["product", "launch", "go-to-market"],
            "suggested_skills": [
                "market-research",
                "landing-page-builder",
                "email-automation",
                "press-release-writing",
                "analytics-reporting",
                "social-media-publishing",
            ],
            "milestones": [
                {
                    "title": "Market Research",
                    "description": "Analyze competitors, target market, and positioning.",
                    "status": "pending",
                    "due_offset_days": 14,
                },
                {
                    "title": "Pre-Launch Setup",
                    "description": "Build landing page, email sequences, and press materials.",
                    "status": "pending",
                    "due_offset_days": 28,
                },
                {
                    "title": "Beta Testing",
                    "description": "Run beta program, collect feedback, iterate.",
                    "status": "pending",
                    "due_offset_days": 42,
                },
                {
                    "title": "Launch Day",
                    "description": "Execute launch plan across all channels.",
                    "status": "pending",
                    "due_offset_days": 49,
                },
                {
                    "title": "Post-Launch Review",
                    "description": "Analyze launch metrics, user feedback, and next steps.",
                    "status": "pending",
                    "due_offset_days": 63,
                },
            ],
        },
        "client_onboarding": {
            "name": "Client Onboarding",
            "description": "Structured onboarding process for new clients.",
            "status": "planning",
            "tags": ["client", "onboarding", "operations"],
            "suggested_skills": [
                "crm-integration",
                "email-automation",
                "document-generation",
                "task-management",
                "reporting-dashboard",
            ],
            "milestones": [
                {
                    "title": "Discovery Call",
                    "description": "Initial meeting to understand client needs and goals.",
                    "status": "pending",
                    "due_offset_days": 3,
                },
                {
                    "title": "Proposal & Agreement",
                    "description": "Send proposal, negotiate terms, and sign agreement.",
                    "status": "pending",
                    "due_offset_days": 7,
                },
                {
                    "title": "Account Setup",
                    "description": "Create accounts, configure tools, and set permissions.",
                    "status": "pending",
                    "due_offset_days": 10,
                },
                {
                    "title": "Kickoff & Training",
                    "description": "Conduct kickoff meeting and training sessions.",
                    "status": "pending",
                    "due_offset_days": 14,
                },
                {
                    "title": "First Deliverable",
                    "description": "Complete and deliver first project milestone.",
                    "status": "pending",
                    "due_offset_days": 28,
                },
                {
                    "title": "30-Day Check-in",
                    "description": "Review progress, satisfaction, and adjust as needed.",
                    "status": "pending",
                    "due_offset_days": 30,
                },
            ],
        },
        "sales_pipeline": {
            "name": "Sales Pipeline",
            "description": "Manage and optimize the sales funnel from lead to close.",
            "status": "planning",
            "tags": ["sales", "pipeline", "revenue"],
            "suggested_skills": [
                "lead-generation",
                "crm-integration",
                "email-automation",
                "proposal-generation",
                "analytics-reporting",
                "follow-up-sequencing",
            ],
            "milestones": [
                {
                    "title": "Lead Generation Setup",
                    "description": "Configure lead sources, forms, and tracking.",
                    "status": "pending",
                    "due_offset_days": 7,
                },
                {
                    "title": "Qualification Process",
                    "description": "Define scoring criteria and qualification workflows.",
                    "status": "pending",
                    "due_offset_days": 14,
                },
                {
                    "title": "Outreach Sequences",
                    "description": "Build email and call sequences for each stage.",
                    "status": "pending",
                    "due_offset_days": 21,
                },
                {
                    "title": "Proposal Templates",
                    "description": "Create reusable proposal and quote templates.",
                    "status": "pending",
                    "due_offset_days": 28,
                },
                {
                    "title": "Pipeline Review & Optimization",
                    "description": "Analyze conversion rates and optimize each stage.",
                    "status": "pending",
                    "due_offset_days": 42,
                },
            ],
        },
        "research_sprint": {
            "name": "Research Sprint",
            "description": "Time-boxed research initiative to explore a topic or validate hypotheses.",
            "status": "planning",
            "tags": ["research", "sprint", "analysis"],
            "suggested_skills": [
                "market-research",
                "data-analysis",
                "report-generation",
                "web-scraping",
                "summarization",
            ],
            "milestones": [
                {
                    "title": "Define Research Questions",
                    "description": "Formulate hypotheses and key questions to answer.",
                    "status": "pending",
                    "due_offset_days": 2,
                },
                {
                    "title": "Data Collection",
                    "description": "Gather data from primary and secondary sources.",
                    "status": "pending",
                    "due_offset_days": 7,
                },
                {
                    "title": "Analysis",
                    "description": "Analyze collected data, identify patterns and insights.",
                    "status": "pending",
                    "due_offset_days": 10,
                },
                {
                    "title": "Findings Report",
                    "description": "Compile findings into a structured report.",
                    "status": "pending",
                    "due_offset_days": 12,
                },
                {
                    "title": "Presentation & Review",
                    "description": "Present findings to stakeholders and decide next steps.",
                    "status": "pending",
                    "due_offset_days": 14,
                },
            ],
        },
    }

    VALID_STATUSES = {"planning", "active", "paused", "completed"}
    VALID_MILESTONE_STATUSES = {"pending", "in_progress", "completed", "skipped"}

    def __init__(self, repo_root: Path, skill_service: Any = None) -> None:
        """Initialize ProjectService with repo root and optional skill service reference.

        Args:
            repo_root: Root path of the repository.
            skill_service: Reference to the SkillService for skill lookups and suggestions.
        """
        self.repo_root = Path(repo_root)
        self.skill_service = skill_service
        self.data_dir: Path = self.repo_root / "command-center" / "backend" / "data"
        self.data_file: Path = self.data_dir / "projects.json"
        self.projects: dict[str, dict[str, Any]] = {}
        self._load()
        log.info(
            "ProjectService initialized with %d projects from %s",
            len(self.projects),
            self.data_file,
        )

    # ── Persistence ────────────────────────────────────────────────────────

    def _load(self) -> None:
        """Load projects from JSON file on disk."""
        if self.data_file.exists():
            try:
                raw = self.data_file.read_text(encoding="utf-8")
                data = json.loads(raw)
                if isinstance(data, dict):
                    self.projects = data
                elif isinstance(data, list):
                    self.projects = {p["id"]: p for p in data if "id" in p}
                else:
                    self.projects = {}
                log.info("Loaded %d projects from %s", len(self.projects), self.data_file)
            except (json.JSONDecodeError, KeyError) as exc:
                log.warning("Failed to load projects from %s: %s", self.data_file, exc)
                self.projects = {}
        else:
            self.projects = {}
            log.info("No projects file found at %s, starting empty", self.data_file)

    def _save(self) -> None:
        """Persist projects to JSON file on disk."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        try:
            self.data_file.write_text(
                json.dumps(self.projects, indent=2, default=str),
                encoding="utf-8",
            )
            log.debug("Saved %d projects to %s", len(self.projects), self.data_file)
        except OSError as exc:
            log.error("Failed to save projects to %s: %s", self.data_file, exc)

    # ── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _generate_id() -> str:
        """Generate a unique short ID."""
        return uuid4().hex[:8]

    @staticmethod
    def _now() -> str:
        """Return current UTC timestamp in ISO format."""
        return datetime.now(timezone.utc).isoformat()

    def _compute_due_date(self, offset_days: int) -> str:
        """Compute an ISO due date from now plus offset_days.

        Args:
            offset_days: Number of days from now.

        Returns:
            ISO formatted date string.
        """
        from datetime import timedelta

        due = datetime.now(timezone.utc) + timedelta(days=offset_days)
        return due.isoformat()

    # ── CRUD Operations ────────────────────────────────────────────────────

    def create_project(
        self,
        name: str,
        description: str = "",
        status: str = "planning",
        assigned_agents: Optional[list[str]] = None,
        linked_skills: Optional[list[str]] = None,
        milestones: Optional[list[dict[str, Any]]] = None,
        tags: Optional[list[str]] = None,
        template: Optional[str] = None,
    ) -> dict[str, Any]:
        """Create a new project, optionally from a template.

        Args:
            name: Project name.
            description: Project description.
            status: Initial status (planning/active/paused/completed).
            assigned_agents: List of agent IDs assigned to this project.
            linked_skills: List of skill IDs linked to this project.
            milestones: List of milestone dicts.
            tags: List of tags.
            template: Optional template key to pre-fill from.

        Returns:
            The created project dict.

        Raises:
            ValueError: If status is invalid or template not found.
        """
        if status not in self.VALID_STATUSES:
            raise ValueError(
                f"Invalid status '{status}'. Must be one of: {', '.join(self.VALID_STATUSES)}"
            )

        now = self._now()
        project_id = self._generate_id()

        # Start with template defaults if specified
        if template:
            tpl = self._get_template_data(template)
            if not name:
                name = tpl["name"]
            if not description:
                description = tpl.get("description", "")
            if not tags:
                tags = list(tpl.get("tags", []))
            if not linked_skills:
                linked_skills = list(tpl.get("suggested_skills", []))
            if not milestones:
                milestones = self._build_milestones_from_template(tpl)

        # Ensure milestone IDs
        resolved_milestones = []
        if milestones:
            for m in milestones:
                milestone = {
                    "id": m.get("id", self._generate_id()),
                    "title": m.get("title", "Untitled Milestone"),
                    "description": m.get("description", ""),
                    "status": m.get("status", "pending"),
                    "due_date": m.get("due_date"),
                    "created_at": now,
                    "updated_at": now,
                }
                if milestone["status"] not in self.VALID_MILESTONE_STATUSES:
                    milestone["status"] = "pending"
                resolved_milestones.append(milestone)

        project: dict[str, Any] = {
            "id": project_id,
            "name": name,
            "description": description,
            "status": status,
            "created_at": now,
            "updated_at": now,
            "assigned_agents": assigned_agents or [],
            "linked_skills": linked_skills or [],
            "milestones": resolved_milestones,
            "tags": tags or [],
        }

        self.projects[project_id] = project
        self._save()
        log.info("Created project '%s' (id=%s, status=%s)", name, project_id, status)
        return project

    def list_projects(
        self,
        status: Optional[str] = None,
        tag: Optional[str] = None,
        agent: Optional[str] = None,
        skill: Optional[str] = None,
        search: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """List all projects with optional filters.

        Args:
            status: Filter by project status.
            tag: Filter by tag.
            agent: Filter by assigned agent ID.
            skill: Filter by linked skill ID.
            search: Free-text search across name and description.

        Returns:
            List of project dicts matching filters.
        """
        results = list(self.projects.values())

        if status:
            results = [p for p in results if p.get("status") == status]

        if tag:
            tag_lower = tag.lower()
            results = [
                p for p in results
                if any(t.lower() == tag_lower for t in p.get("tags", []))
            ]

        if agent:
            results = [
                p for p in results
                if agent in p.get("assigned_agents", [])
            ]

        if skill:
            results = [
                p for p in results
                if skill in p.get("linked_skills", [])
            ]

        if search:
            search_lower = search.lower()
            results = [
                p for p in results
                if search_lower in p.get("name", "").lower()
                or search_lower in p.get("description", "").lower()
            ]

        # Sort by updated_at descending
        results.sort(key=lambda p: p.get("updated_at", ""), reverse=True)
        return results

    def get_project(self, project_id: str) -> Optional[dict[str, Any]]:
        """Get a single project by ID.

        Args:
            project_id: The project ID.

        Returns:
            The project dict or None if not found.
        """
        return self.projects.get(project_id)

    def update_project(self, project_id: str, updates: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Update an existing project.

        Args:
            project_id: The project ID to update.
            updates: Dict of fields to update.

        Returns:
            The updated project dict or None if not found.

        Raises:
            ValueError: If status is invalid.
        """
        project = self.projects.get(project_id)
        if not project:
            return None

        now = self._now()

        # Validate status if being updated
        if "status" in updates:
            if updates["status"] not in self.VALID_STATUSES:
                raise ValueError(
                    f"Invalid status '{updates['status']}'. "
                    f"Must be one of: {', '.join(self.VALID_STATUSES)}"
                )

        # Allowed updatable fields
        allowed_fields = {
            "name", "description", "status", "assigned_agents",
            "linked_skills", "tags",
        }

        for field, value in updates.items():
            if field in allowed_fields:
                project[field] = value

        project["updated_at"] = now
        self.projects[project_id] = project
        self._save()
        log.info("Updated project '%s' (id=%s)", project.get("name"), project_id)
        return project

    def delete_project(self, project_id: str) -> bool:
        """Delete a project by ID.

        Args:
            project_id: The project ID to delete.

        Returns:
            True if deleted, False if not found.
        """
        if project_id not in self.projects:
            return False

        project_name = self.projects[project_id].get("name", "unknown")
        del self.projects[project_id]
        self._save()
        log.info("Deleted project '%s' (id=%s)", project_name, project_id)
        return True

    # ── Templates ──────────────────────────────────────────────────────────

    def list_templates(self) -> list[dict[str, Any]]:
        """List all available project templates.

        Returns:
            List of template summary dicts.
        """
        templates = []
        for key, tpl in self.TEMPLATES.items():
            templates.append({
                "key": key,
                "name": tpl["name"],
                "description": tpl["description"],
                "tags": tpl.get("tags", []),
                "suggested_skills": tpl.get("suggested_skills", []),
                "milestone_count": len(tpl.get("milestones", [])),
            })
        return templates

    def get_template(self, template_key: str) -> Optional[dict[str, Any]]:
        """Get a specific template by key.

        Args:
            template_key: The template key (e.g., 'content_campaign').

        Returns:
            Full template dict or None if not found.
        """
        tpl = self.TEMPLATES.get(template_key)
        if not tpl:
            return None
        return {
            "key": template_key,
            **tpl,
        }

    def _get_template_data(self, template_key: str) -> dict[str, Any]:
        """Get template data, raising ValueError if not found.

        Args:
            template_key: The template key.

        Returns:
            Template dict.

        Raises:
            ValueError: If template not found.
        """
        tpl = self.TEMPLATES.get(template_key)
        if not tpl:
            available = ", ".join(self.TEMPLATES.keys())
            raise ValueError(
                f"Template '{template_key}' not found. Available: {available}"
            )
        return tpl

    def _build_milestones_from_template(self, tpl: dict[str, Any]) -> list[dict[str, Any]]:
        """Build milestone list from template with computed due dates.

        Args:
            tpl: Template dict containing milestone definitions.

        Returns:
            List of milestone dicts with IDs and due dates.
        """
        milestones = []
        for m in tpl.get("milestones", []):
            due_date = None
            if "due_offset_days" in m:
                due_date = self._compute_due_date(m["due_offset_days"])

            milestones.append({
                "id": self._generate_id(),
                "title": m.get("title", "Untitled"),
                "description": m.get("description", ""),
                "status": m.get("status", "pending"),
                "due_date": due_date,
            })
        return milestones

    def create_from_template(
        self,
        template_key: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        assigned_agents: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Create a new project from a predefined template.

        Args:
            template_key: Template key to use.
            name: Override template name.
            description: Override template description.
            assigned_agents: Agents to assign.

        Returns:
            The created project dict.

        Raises:
            ValueError: If template not found.
        """
        tpl = self._get_template_data(template_key)
        return self.create_project(
            name=name or tpl["name"],
            description=description or tpl.get("description", ""),
            status="planning",
            assigned_agents=assigned_agents,
            linked_skills=list(tpl.get("suggested_skills", [])),
            milestones=self._build_milestones_from_template(tpl),
            tags=list(tpl.get("tags", [])),
        )

    # ── Skill-to-Project Mapping ───────────────────────────────────────────

    def get_skill_project_map(self) -> dict[str, list[dict[str, str]]]:
        """Get a mapping of skill IDs to the projects that use them.

        Returns:
            Dict mapping skill_id -> list of {project_id, project_name, project_status}.
        """
        skill_map: dict[str, list[dict[str, str]]] = {}
        for project in self.projects.values():
            for skill_id in project.get("linked_skills", []):
                if skill_id not in skill_map:
                    skill_map[skill_id] = []
                skill_map[skill_id].append({
                    "project_id": project["id"],
                    "project_name": project.get("name", ""),
                    "project_status": project.get("status", ""),
                })
        return skill_map

    def get_projects_for_skill(self, skill_id: str) -> list[dict[str, Any]]:
        """Get all projects that use a specific skill.

        Args:
            skill_id: The skill identifier.

        Returns:
            List of project dicts that link to this skill.
        """
        return [
            p for p in self.projects.values()
            if skill_id in p.get("linked_skills", [])
        ]

    def get_skills_for_project(self, project_id: str) -> list[str]:
        """Get all skill IDs linked to a specific project.

        Args:
            project_id: The project ID.

        Returns:
            List of skill IDs, or empty list if project not found.
        """
        project = self.projects.get(project_id)
        if not project:
            return []
        return list(project.get("linked_skills", []))

    def suggest_skills(self, project_id: str) -> list[dict[str, Any]]:
        """Auto-suggest skills for a project based on its tags and linked template.

        Args:
            project_id: The project ID.

        Returns:
            List of suggested skill dicts with id and reason.
        """
        project = self.projects.get(project_id)
        if not project:
            return []

        suggestions: list[dict[str, Any]] = []
        already_linked = set(project.get("linked_skills", []))
        project_tags = set(t.lower() for t in project.get("tags", []))

        # Gather suggested skills from all templates whose tags overlap
        for _key, tpl in self.TEMPLATES.items():
            tpl_tags = set(t.lower() for t in tpl.get("tags", []))
            overlap = project_tags & tpl_tags
            if overlap:
                for skill_id in tpl.get("suggested_skills", []):
                    if skill_id not in already_linked:
                        suggestions.append({
                            "skill_id": skill_id,
                            "reason": f"Suggested from '{tpl['name']}' template (matching tags: {', '.join(overlap)})",
                            "source_template": _key,
                        })
                        already_linked.add(skill_id)  # prevent duplicates

        # If skill_service is available, try to enrich suggestions
        if self.skill_service:
            enriched = []
            for s in suggestions:
                skill_data = None
                if hasattr(self.skill_service, "skills"):
                    skill_data = self.skill_service.skills.get(s["skill_id"])
                enriched.append({
                    **s,
                    "skill_name": skill_data.get("name", s["skill_id"]) if skill_data else s["skill_id"],
                    "skill_status": skill_data.get("status", "unknown") if skill_data else "unknown",
                })
            return enriched

        return suggestions

    def link_skill(self, project_id: str, skill_id: str) -> Optional[dict[str, Any]]:
        """Link a skill to a project.

        Args:
            project_id: The project ID.
            skill_id: The skill ID to link.

        Returns:
            Updated project dict or None if project not found.
        """
        project = self.projects.get(project_id)
        if not project:
            return None

        if skill_id not in project.get("linked_skills", []):
            project.setdefault("linked_skills", []).append(skill_id)
            project["updated_at"] = self._now()
            self._save()
            log.info("Linked skill '%s' to project '%s'", skill_id, project_id)

        return project

    def unlink_skill(self, project_id: str, skill_id: str) -> Optional[dict[str, Any]]:
        """Unlink a skill from a project.

        Args:
            project_id: The project ID.
            skill_id: The skill ID to unlink.

        Returns:
            Updated project dict or None if project not found.
        """
        project = self.projects.get(project_id)
        if not project:
            return None

        skills = project.get("linked_skills", [])
        if skill_id in skills:
            skills.remove(skill_id)
            project["linked_skills"] = skills
            project["updated_at"] = self._now()
            self._save()
            log.info("Unlinked skill '%s' from project '%s'", skill_id, project_id)

        return project

    # ── Milestone Tracking ─────────────────────────────────────────────────

    def add_milestone(
        self,
        project_id: str,
        title: str,
        description: str = "",
        status: str = "pending",
        due_date: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Add a milestone to a project.

        Args:
            project_id: The project ID.
            title: Milestone title.
            description: Milestone description.
            status: Milestone status (pending/in_progress/completed/skipped).
            due_date: Optional ISO due date string.

        Returns:
            The created milestone dict or None if project not found.

        Raises:
            ValueError: If milestone status is invalid.
        """
        project = self.projects.get(project_id)
        if not project:
            return None

        if status not in self.VALID_MILESTONE_STATUSES:
            raise ValueError(
                f"Invalid milestone status '{status}'. "
                f"Must be one of: {', '.join(self.VALID_MILESTONE_STATUSES)}"
            )

        now = self._now()
        milestone: dict[str, Any] = {
            "id": self._generate_id(),
            "title": title,
            "description": description,
            "status": status,
            "due_date": due_date,
            "created_at": now,
            "updated_at": now,
        }

        project.setdefault("milestones", []).append(milestone)
        project["updated_at"] = now
        self._save()
        log.info(
            "Added milestone '%s' to project '%s' (id=%s)",
            title, project.get("name"), project_id,
        )
        return milestone

    def update_milestone(
        self,
        project_id: str,
        milestone_id: str,
        updates: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        """Update a milestone within a project.

        Args:
            project_id: The project ID.
            milestone_id: The milestone ID to update.
            updates: Dict of fields to update (title, description, status, due_date).

        Returns:
            The updated milestone dict or None if not found.

        Raises:
            ValueError: If milestone status is invalid.
        """
        project = self.projects.get(project_id)
        if not project:
            return None

        if "status" in updates and updates["status"] not in self.VALID_MILESTONE_STATUSES:
            raise ValueError(
                f"Invalid milestone status '{updates['status']}'. "
                f"Must be one of: {', '.join(self.VALID_MILESTONE_STATUSES)}"
            )

        now = self._now()
        milestones = project.get("milestones", [])

        for milestone in milestones:
            if milestone.get("id") == milestone_id:
                allowed_fields = {"title", "description", "status", "due_date"}
                for field, value in updates.items():
                    if field in allowed_fields:
                        milestone[field] = value
                milestone["updated_at"] = now
                project["updated_at"] = now
                self._save()
                log.info(
                    "Updated milestone '%s' in project '%s'",
                    milestone_id, project_id,
                )
                return milestone

        return None

    def delete_milestone(self, project_id: str, milestone_id: str) -> bool:
        """Delete a milestone from a project.

        Args:
            project_id: The project ID.
            milestone_id: The milestone ID to delete.

        Returns:
            True if deleted, False if not found.
        """
        project = self.projects.get(project_id)
        if not project:
            return False

        milestones = project.get("milestones", [])
        original_count = len(milestones)
        project["milestones"] = [
            m for m in milestones if m.get("id") != milestone_id
        ]

        if len(project["milestones"]) < original_count:
            project["updated_at"] = self._now()
            self._save()
            log.info(
                "Deleted milestone '%s' from project '%s'",
                milestone_id, project_id,
            )
            return True

        return False

    def get_milestones(self, project_id: str) -> Optional[list[dict[str, Any]]]:
        """Get all milestones for a project.

        Args:
            project_id: The project ID.

        Returns:
            List of milestone dicts or None if project not found.
        """
        project = self.projects.get(project_id)
        if not project:
            return None
        return list(project.get("milestones", []))

    def get_milestone_summary(self, project_id: str) -> Optional[dict[str, Any]]:
        """Get milestone progress summary for a project.

        Args:
            project_id: The project ID.

        Returns:
            Summary dict with counts and progress percentage, or None if not found.
        """
        project = self.projects.get(project_id)
        if not project:
            return None

        milestones = project.get("milestones", [])
        total = len(milestones)
        if total == 0:
            return {
                "total": 0,
                "pending": 0,
                "in_progress": 0,
                "completed": 0,
                "skipped": 0,
                "progress_pct": 0.0,
                "overdue": 0,
            }

        status_counts: dict[str, int] = {
            "pending": 0,
            "in_progress": 0,
            "completed": 0,
            "skipped": 0,
        }

        overdue = 0
        now_str = self._now()

        for m in milestones:
            ms_status = m.get("status", "pending")
            if ms_status in status_counts:
                status_counts[ms_status] += 1

            # Check overdue
            due_date = m.get("due_date")
            if due_date and ms_status not in ("completed", "skipped"):
                if due_date < now_str:
                    overdue += 1

        completed = status_counts["completed"]
        # Progress: completed / (total - skipped) if applicable
        countable = total - status_counts["skipped"]
        progress_pct = round((completed / countable * 100) if countable > 0 else 0.0, 1)

        return {
            "total": total,
            **status_counts,
            "progress_pct": progress_pct,
            "overdue": overdue,
        }

    # ── Stats & Summary ────────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """Get summary statistics across all projects.

        Returns:
            Dict with counts by status, total projects, skill usage, and milestone stats.
        """
        total = len(self.projects)
        status_counts: dict[str, int] = {s: 0 for s in self.VALID_STATUSES}
        total_milestones = 0
        completed_milestones = 0
        overdue_milestones = 0
        all_tags: dict[str, int] = {}
        all_skills: dict[str, int] = {}
        all_agents: dict[str, int] = {}

        now_str = self._now()

        for project in self.projects.values():
            p_status = project.get("status", "planning")
            if p_status in status_counts:
                status_counts[p_status] += 1

            for tag in project.get("tags", []):
                all_tags[tag] = all_tags.get(tag, 0) + 1

            for skill_id in project.get("linked_skills", []):
                all_skills[skill_id] = all_skills.get(skill_id, 0) + 1

            for agent_id in project.get("assigned_agents", []):
                all_agents[agent_id] = all_agents.get(agent_id, 0) + 1

            for m in project.get("milestones", []):
                total_milestones += 1
                ms = m.get("status", "pending")
                if ms == "completed":
                    completed_milestones += 1
                due = m.get("due_date")
                if due and ms not in ("completed", "skipped") and due < now_str:
                    overdue_milestones += 1

        return {
            "total_projects": total,
            "by_status": status_counts,
            "total_milestones": total_milestones,
            "completed_milestones": completed_milestones,
            "overdue_milestones": overdue_milestones,
            "milestone_completion_pct": round(
                (completed_milestones / total_milestones * 100)
                if total_milestones > 0 else 0.0,
                1,
            ),
            "unique_skills_used": len(all_skills),
            "skill_usage": dict(sorted(all_skills.items(), key=lambda x: x[1], reverse=True)),
            "unique_agents_assigned": len(all_agents),
            "agent_assignments": dict(sorted(all_agents.items(), key=lambda x: x[1], reverse=True)),
            "tag_counts": dict(sorted(all_tags.items(), key=lambda x: x[1], reverse=True)),
        }

    # ── Reload ─────────────────────────────────────────────────────────────

    def reload(self) -> None:
        """Reload projects from disk.

        Useful after external modifications to the JSON file.
        """
        self._load()
        log.info("Reloaded %d projects from disk", len(self.projects))