"""
NemoClaw Command Center — Client Service (CC-8)
Manages client CRUD, client-project linking, deliverable tracking,
and client health score computation with JSON persistence.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

log = logging.getLogger("cc.cc.8")


class ClientService:
    """Central service for client management, project linking, deliverable tracking, and health scoring."""

    def __init__(self, repo_root: Path) -> None:
        """Initialize ClientService with JSON persistence from repo root.

        Args:
            repo_root: Root path of the repository.
        """
        self.repo_root = Path(repo_root)
        self.data_dir: Path = self.repo_root / "command-center" / "backend" / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.clients_file: Path = self.data_dir / "clients.json"
        self.deliverables_file: Path = self.data_dir / "deliverables.json"
        self.client_projects_file: Path = self.data_dir / "client_projects.json"

        self.clients: dict[str, dict[str, Any]] = {}
        self.deliverables: dict[str, dict[str, Any]] = {}
        self.client_projects: dict[str, dict[str, Any]] = {}

        self._load_all()
        log.info(
            f"Loaded {len(self.clients)} clients, "
            f"{len(self.client_projects)} client-project links, "
            f"{len(self.deliverables)} deliverables"
        )

    # ── Persistence ────────────────────────────────────────────────────────

    def _load_all(self) -> None:
        """Load all data stores from disk."""
        self.clients = self._load_json(self.clients_file)
        self.deliverables = self._load_json(self.deliverables_file)
        self.client_projects = self._load_json(self.client_projects_file)

    def _load_json(self, path: Path) -> dict[str, dict[str, Any]]:
        """Load a JSON file into a dictionary.

        Args:
            path: Path to the JSON file.

        Returns:
            Dictionary of records keyed by ID.
        """
        if path.exists():
            try:
                with path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return data
                log.warning(f"Unexpected format in {path}, resetting to empty dict")
                return {}
            except (json.JSONDecodeError, OSError) as e:
                log.error(f"Failed to load {path}: {e}")
                return {}
        return {}

    def _save_json(self, path: Path, data: dict[str, dict[str, Any]]) -> None:
        """Save a dictionary to a JSON file.

        Args:
            path: Path to the JSON file.
            data: Dictionary of records to persist.
        """
        try:
            with path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
        except OSError as e:
            log.error(f"Failed to save {path}: {e}")

    def _save_clients(self) -> None:
        """Persist clients to disk."""
        self._save_json(self.clients_file, self.clients)

    def _save_deliverables(self) -> None:
        """Persist deliverables to disk."""
        self._save_json(self.deliverables_file, self.deliverables)

    def _save_client_projects(self) -> None:
        """Persist client-project links to disk."""
        self._save_json(self.client_projects_file, self.client_projects)

    @staticmethod
    def _generate_id() -> str:
        """Generate a unique short ID.

        Returns:
            8-character hex string.
        """
        return uuid4().hex[:8]

    @staticmethod
    def _now() -> str:
        """Get current UTC timestamp in ISO format.

        Returns:
            ISO-formatted UTC timestamp string.
        """
        return datetime.now(timezone.utc).isoformat()

    # ── Client CRUD ────────────────────────────────────────────────────────

    def create_client(
        self,
        name: str,
        company: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        status: str = "prospect",
        notes: Optional[str] = None,
        tags: Optional[list[str]] = None,
        assigned_agent: Optional[str] = None,
    ) -> dict[str, Any]:
        """Create a new client record.

        Args:
            name: Client name.
            company: Company name.
            email: Contact email.
            phone: Contact phone.
            status: Client status (prospect/active/churned).
            notes: Free-text notes.
            tags: List of tags for categorization.
            assigned_agent: Agent ID assigned to this client.

        Returns:
            The created client record.
        """
        if status not in ("prospect", "active", "churned"):
            raise ValueError(f"Invalid client status: {status}. Must be prospect/active/churned.")

        client_id = self._generate_id()
        now = self._now()

        client: dict[str, Any] = {
            "id": client_id,
            "name": name,
            "company": company or "",
            "email": email or "",
            "phone": phone or "",
            "status": status,
            "created_at": now,
            "updated_at": now,
            "notes": notes or "",
            "tags": tags or [],
            "assigned_agent": assigned_agent or "",
        }

        self.clients[client_id] = client
        self._save_clients()
        log.info(f"Created client '{name}' (id={client_id})")
        return client

    def list_clients(
        self,
        status: Optional[str] = None,
        tag: Optional[str] = None,
        assigned_agent: Optional[str] = None,
        search: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """List all clients with optional filters.

        Args:
            status: Filter by client status.
            tag: Filter by tag membership.
            assigned_agent: Filter by assigned agent.
            search: Free-text search across name, company, email, notes.

        Returns:
            List of matching client records.
        """
        results: list[dict[str, Any]] = []

        for client in self.clients.values():
            if status and client.get("status") != status:
                continue
            if tag and tag not in client.get("tags", []):
                continue
            if assigned_agent and client.get("assigned_agent") != assigned_agent:
                continue
            if search:
                search_lower = search.lower()
                searchable = " ".join([
                    client.get("name", ""),
                    client.get("company", ""),
                    client.get("email", ""),
                    client.get("notes", ""),
                ]).lower()
                if search_lower not in searchable:
                    continue
            results.append(client)

        results.sort(key=lambda c: c.get("created_at", ""), reverse=True)
        return results

    def get_client(self, client_id: str) -> Optional[dict[str, Any]]:
        """Get a single client by ID.

        Args:
            client_id: The client identifier.

        Returns:
            Client record or None if not found.
        """
        return self.clients.get(client_id)

    def update_client(self, client_id: str, updates: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Update an existing client record.

        Args:
            client_id: The client identifier.
            updates: Dictionary of fields to update.

        Returns:
            Updated client record, or None if client not found.
        """
        client = self.clients.get(client_id)
        if not client:
            log.warning(f"Client not found for update: {client_id}")
            return None

        allowed_fields = {"name", "company", "email", "phone", "status", "notes", "tags", "assigned_agent"}

        if "status" in updates and updates["status"] not in ("prospect", "active", "churned"):
            raise ValueError(f"Invalid client status: {updates['status']}. Must be prospect/active/churned.")

        for key, value in updates.items():
            if key in allowed_fields:
                client[key] = value

        client["updated_at"] = self._now()
        self.clients[client_id] = client
        self._save_clients()
        log.info(f"Updated client {client_id}: {list(updates.keys())}")
        return client

    def delete_client(self, client_id: str) -> bool:
        """Delete a client and all associated links and deliverables.

        Args:
            client_id: The client identifier.

        Returns:
            True if deleted, False if not found.
        """
        if client_id not in self.clients:
            log.warning(f"Client not found for deletion: {client_id}")
            return False

        del self.clients[client_id]
        self._save_clients()

        # Remove associated client-project links
        links_to_remove = [
            link_id for link_id, link in self.client_projects.items()
            if link.get("client_id") == client_id
        ]
        for link_id in links_to_remove:
            del self.client_projects[link_id]
        if links_to_remove:
            self._save_client_projects()

        # Remove associated deliverables
        deliverables_to_remove = [
            d_id for d_id, d in self.deliverables.items()
            if d.get("client_id") == client_id
        ]
        for d_id in deliverables_to_remove:
            del self.deliverables[d_id]
        if deliverables_to_remove:
            self._save_deliverables()

        log.info(
            f"Deleted client {client_id} with {len(links_to_remove)} project links "
            f"and {len(deliverables_to_remove)} deliverables"
        )
        return True

    # ── Client-Project Linking ─────────────────────────────────────────────

    def link_project(self, client_id: str, project_id: str, role: str = "owner") -> Optional[dict[str, Any]]:
        """Link a project to a client.

        Args:
            client_id: The client identifier.
            project_id: The project identifier.
            role: Relationship role (e.g., owner, stakeholder).

        Returns:
            The link record, or None if client not found.
        """
        if client_id not in self.clients:
            log.warning(f"Cannot link project: client {client_id} not found")
            return None

        # Check for existing link
        for link in self.client_projects.values():
            if link.get("client_id") == client_id and link.get("project_id") == project_id:
                log.info(f"Project {project_id} already linked to client {client_id}")
                return link

        link_id = self._generate_id()
        now = self._now()

        link: dict[str, Any] = {
            "id": link_id,
            "client_id": client_id,
            "project_id": project_id,
            "role": role,
            "linked_at": now,
        }

        self.client_projects[link_id] = link
        self._save_client_projects()
        log.info(f"Linked project {project_id} to client {client_id} (role={role})")
        return link

    def unlink_project(self, client_id: str, project_id: str) -> bool:
        """Remove a project-client link.

        Args:
            client_id: The client identifier.
            project_id: The project identifier.

        Returns:
            True if unlinked, False if link not found.
        """
        link_to_remove: Optional[str] = None
        for link_id, link in self.client_projects.items():
            if link.get("client_id") == client_id and link.get("project_id") == project_id:
                link_to_remove = link_id
                break

        if not link_to_remove:
            log.warning(f"No link found between client {client_id} and project {project_id}")
            return False

        del self.client_projects[link_to_remove]
        self._save_client_projects()
        log.info(f"Unlinked project {project_id} from client {client_id}")
        return True

    def get_client_projects(self, client_id: str) -> list[dict[str, Any]]:
        """Get all projects linked to a client.

        Args:
            client_id: The client identifier.

        Returns:
            List of client-project link records.
        """
        return [
            link for link in self.client_projects.values()
            if link.get("client_id") == client_id
        ]

    def get_project_clients(self, project_id: str) -> list[dict[str, Any]]:
        """Get all clients linked to a project.

        Args:
            project_id: The project identifier.

        Returns:
            List of client-project link records.
        """
        return [
            link for link in self.client_projects.values()
            if link.get("project_id") == project_id
        ]

    # ── Deliverable Tracking ───────────────────────────────────────────────

    VALID_DELIVERABLE_STATUSES = ("pending", "in_progress", "delivered", "approved")

    def create_deliverable(
        self,
        client_id: str,
        project_id: str,
        title: str,
        due_date: Optional[str] = None,
        status: str = "pending",
    ) -> Optional[dict[str, Any]]:
        """Create a new deliverable for a client project.

        Args:
            client_id: The client identifier.
            project_id: The project identifier.
            title: Deliverable title.
            due_date: Optional due date in ISO format.
            status: Initial status (pending/in_progress/delivered/approved).

        Returns:
            The created deliverable record, or None if client not found.
        """
        if client_id not in self.clients:
            log.warning(f"Cannot create deliverable: client {client_id} not found")
            return None

        if status not in self.VALID_DELIVERABLE_STATUSES:
            raise ValueError(
                f"Invalid deliverable status: {status}. "
                f"Must be one of {self.VALID_DELIVERABLE_STATUSES}"
            )

        deliverable_id = self._generate_id()
        now = self._now()

        deliverable: dict[str, Any] = {
            "id": deliverable_id,
            "client_id": client_id,
            "project_id": project_id,
            "title": title,
            "status": status,
            "due_date": due_date or "",
            "delivered_at": None,
            "created_at": now,
            "updated_at": now,
        }

        self.deliverables[deliverable_id] = deliverable
        self._save_deliverables()
        log.info(f"Created deliverable '{title}' (id={deliverable_id}) for client {client_id}")
        return deliverable

    def list_deliverables(
        self,
        client_id: Optional[str] = None,
        project_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """List deliverables with optional filters.

        Args:
            client_id: Filter by client.
            project_id: Filter by project.
            status: Filter by deliverable status.

        Returns:
            List of matching deliverable records.
        """
        results: list[dict[str, Any]] = []

        for deliverable in self.deliverables.values():
            if client_id and deliverable.get("client_id") != client_id:
                continue
            if project_id and deliverable.get("project_id") != project_id:
                continue
            if status and deliverable.get("status") != status:
                continue
            results.append(deliverable)

        results.sort(key=lambda d: d.get("due_date") or d.get("created_at", ""), reverse=False)
        return results

    def get_deliverable(self, deliverable_id: str) -> Optional[dict[str, Any]]:
        """Get a single deliverable by ID.

        Args:
            deliverable_id: The deliverable identifier.

        Returns:
            Deliverable record or None if not found.
        """
        return self.deliverables.get(deliverable_id)

    def update_deliverable(self, deliverable_id: str, updates: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Update an existing deliverable.

        Args:
            deliverable_id: The deliverable identifier.
            updates: Dictionary of fields to update.

        Returns:
            Updated deliverable record, or None if not found.
        """
        deliverable = self.deliverables.get(deliverable_id)
        if not deliverable:
            log.warning(f"Deliverable not found for update: {deliverable_id}")
            return None

        allowed_fields = {"title", "status", "due_date", "delivered_at"}

        if "status" in updates:
            if updates["status"] not in self.VALID_DELIVERABLE_STATUSES:
                raise ValueError(
                    f"Invalid deliverable status: {updates['status']}. "
                    f"Must be one of {self.VALID_DELIVERABLE_STATUSES}"
                )
            # Auto-set delivered_at when status transitions to delivered
            if updates["status"] == "delivered" and deliverable.get("status") != "delivered":
                if "delivered_at" not in updates:
                    updates["delivered_at"] = self._now()

        for key, value in updates.items():
            if key in allowed_fields:
                deliverable[key] = value

        deliverable["updated_at"] = self._now()
        self.deliverables[deliverable_id] = deliverable
        self._save_deliverables()
        log.info(f"Updated deliverable {deliverable_id}: {list(updates.keys())}")
        return deliverable

    def delete_deliverable(self, deliverable_id: str) -> bool:
        """Delete a deliverable.

        Args:
            deliverable_id: The deliverable identifier.

        Returns:
            True if deleted, False if not found.
        """
        if deliverable_id not in self.deliverables:
            log.warning(f"Deliverable not found for deletion: {deliverable_id}")
            return False

        del self.deliverables[deliverable_id]
        self._save_deliverables()
        log.info(f"Deleted deliverable {deliverable_id}")
        return True

    # ── Client Health Score ────────────────────────────────────────────────

    def compute_health_score(
        self,
        client_id: str,
        message_store: Optional[Any] = None,
    ) -> Optional[dict[str, Any]]:
        """Compute a health score for a client based on multiple factors.

        The health score is a composite of:
        - Project status score (0-30): Based on proportion of active/healthy projects
        - Deliverable timeliness score (0-40): Based on on-time deliveries
        - Communication frequency score (0-30): Based on recent lane activity

        Args:
            client_id: The client identifier.
            message_store: Optional MessageStore instance for communication scoring.

        Returns:
            Health score breakdown dict, or None if client not found.
        """
        client = self.clients.get(client_id)
        if not client:
            log.warning(f"Client not found for health score: {client_id}")
            return None

        # ── Project Status Score (0-30) ────────────────────────────────
        project_links = self.get_client_projects(client_id)
        project_score = 0.0
        project_count = len(project_links)

        if project_count > 0:
            # Having linked projects is inherently positive
            project_score = min(30.0, 15.0 + (project_count * 3.0))
        else:
            # No projects linked — neutral baseline
            project_score = 10.0

        # ── Deliverable Timeliness Score (0-40) ────────────────────────
        client_deliverables = self.list_deliverables(client_id=client_id)
        deliverable_score = 0.0
        total_deliverables = len(client_deliverables)

        if total_deliverables > 0:
            on_time = 0
            delivered_count = 0
            overdue_count = 0
            approved_count = 0
            now_str = self._now()

            for d in client_deliverables:
                d_status = d.get("status", "pending")

                if d_status == "approved":
                    approved_count += 1
                    delivered_count += 1
                    on_time += 1
                elif d_status == "delivered":
                    delivered_count += 1
                    due_date = d.get("due_date", "")
                    delivered_at = d.get("delivered_at", "")
                    if due_date and delivered_at:
                        if delivered_at <= due_date:
                            on_time += 1
                    else:
                        # No due date constraint — count as on time
                        on_time += 1
                elif d_status in ("pending", "in_progress"):
                    due_date = d.get("due_date", "")
                    if due_date and due_date < now_str:
                        overdue_count += 1

            # Calculate score components
            completion_ratio = delivered_count / total_deliverables if total_deliverables > 0 else 0.0
            timeliness_ratio = on_time / max(delivered_count, 1)
            approval_ratio = approved_count / total_deliverables if total_deliverables > 0 else 0.0
            overdue_penalty = min(overdue_count * 5.0, 15.0)

            deliverable_score = (
                (completion_ratio * 15.0) +
                (timeliness_ratio * 15.0) +
                (approval_ratio * 10.0) -
                overdue_penalty
            )
            deliverable_score = max(0.0, min(40.0, deliverable_score))
        else:
            # No deliverables — neutral
            deliverable_score = 15.0

        # ── Communication Frequency Score (0-30) ──────────────────────
        communication_score = 0.0

        if message_store is not None:
            try:
                communication_score = self._compute_communication_score(client_id, message_store)
            except Exception as e:
                log.warning(f"Failed to compute communication score for {client_id}: {e}")
                communication_score = 10.0
        else:
            # No message store available — assign neutral score
            communication_score = 15.0

        # ── Composite Score ───────────────────────────────────────────
        total_score = round(project_score + deliverable_score + communication_score, 1)
        total_score = max(0.0, min(100.0, total_score))

        # Determine health label
        if total_score >= 80:
            health_label = "excellent"
        elif total_score >= 60:
            health_label = "good"
        elif total_score >= 40:
            health_label = "fair"
        elif total_score >= 20:
            health_label = "at_risk"
        else:
            health_label = "critical"

        result: dict[str, Any] = {
            "client_id": client_id,
            "client_name": client.get("name", ""),
            "total_score": total_score,
            "health_label": health_label,
            "breakdown": {
                "project_score": round(project_score, 1),
                "project_max": 30,
                "project_count": project_count,
                "deliverable_score": round(deliverable_score, 1),
                "deliverable_max": 40,
                "deliverable_count": total_deliverables,
                "communication_score": round(communication_score, 1),
                "communication_max": 30,
            },
            "computed_at": self._now(),
        }

        log.info(
            f"Health score for client {client_id} ({client.get('name', '')}): "
            f"{total_score}/100 ({health_label})"
        )
        return result

    def _compute_communication_score(self, client_id: str, message_store: Any) -> float:
        """Compute communication frequency score from MessageStore lane activity.

        Looks for messages in lanes associated with this client.

        Args:
            client_id: The client identifier.
            message_store: MessageStore instance with lane querying capabilities.

        Returns:
            Communication score between 0.0 and 30.0.
        """
        score = 0.0

        # Try to find messages related to this client via lane activity
        client = self.clients.get(client_id, {})
        client_name = client.get("name", "").lower()

        # Attempt various MessageStore access patterns
        message_count = 0

        # Pattern 1: message_store has a method to get messages by tag/client
        if hasattr(message_store, "get_messages_by_client"):
            try:
                messages = message_store.get_messages_by_client(client_id)
                message_count = len(messages) if messages else 0
            except Exception:
                pass

        # Pattern 2: message_store has lanes we can search
        if message_count == 0 and hasattr(message_store, "lanes"):
            try:
                for lane_id, lane_messages in message_store.lanes.items():
                    if client_id in lane_id or client_name in lane_id.lower():
                        message_count += len(lane_messages) if isinstance(lane_messages, list) else 0
            except Exception:
                pass

        # Pattern 3: message_store has a search/query method
        if message_count == 0 and hasattr(message_store, "search"):
            try:
                results = message_store.search(client_id)
                message_count = len(results) if results else 0
            except Exception:
                pass

        # Pattern 4: generic get_messages with filter
        if message_count == 0 and hasattr(message_store, "get_messages"):
            try:
                messages = message_store.get_messages(client_id=client_id)
                message_count = len(messages) if messages else 0
            except Exception:
                pass

        # Score based on message count (recent activity proxy)
        if message_count >= 20:
            score = 30.0
        elif message_count >= 10:
            score = 25.0
        elif message_count >= 5:
            score = 20.0
        elif message_count >= 2:
            score = 15.0
        elif message_count >= 1:
            score = 10.0
        else:
            score = 5.0

        return score

    def compute_all_health_scores(
        self,
        message_store: Optional[Any] = None,
    ) -> list[dict[str, Any]]:
        """Compute health scores for all clients.

        Args:
            message_store: Optional MessageStore instance for communication scoring.

        Returns:
            List of health score records for all clients, sorted by score ascending.
        """
        scores: list[dict[str, Any]] = []
        for client_id in self.clients:
            score = self.compute_health_score(client_id, message_store)
            if score:
                scores.append(score)

        scores.sort(key=lambda s: s.get("total_score", 0))
        return scores

    # ── Statistics ─────────────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """Get summary statistics for clients, projects, and deliverables.

        Returns:
            Dictionary with count breakdowns.
        """
        status_counts: dict[str, int] = {"prospect": 0, "active": 0, "churned": 0}
        for client in self.clients.values():
            s = client.get("status", "prospect")
            status_counts[s] = status_counts.get(s, 0) + 1

        deliverable_status_counts: dict[str, int] = {
            "pending": 0, "in_progress": 0, "delivered": 0, "approved": 0,
        }
        for d in self.deliverables.values():
            ds = d.get("status", "pending")
            deliverable_status_counts[ds] = deliverable_status_counts.get(ds, 0) + 1

        # Count overdue deliverables
        now_str = self._now()
        overdue = 0
        for d in self.deliverables.values():
            if d.get("status") in ("pending", "in_progress"):
                due_date = d.get("due_date", "")
                if due_date and due_date < now_str:
                    overdue += 1

        # Tag distribution
        tag_counts: dict[str, int] = {}
        for client in self.clients.values():
            for tag in client.get("tags", []):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

        # Agent distribution
        agent_counts: dict[str, int] = {}
        for client in self.clients.values():
            agent = client.get("assigned_agent", "")
            if agent:
                agent_counts[agent] = agent_counts.get(agent, 0) + 1

        return {
            "total_clients": len(self.clients),
            "client_status": status_counts,
            "total_project_links": len(self.client_projects),
            "total_deliverables": len(self.deliverables),
            "deliverable_status": deliverable_status_counts,
            "overdue_deliverables": overdue,
            "tag_distribution": tag_counts,
            "agent_distribution": agent_counts,
        }

    # ── Reload ─────────────────────────────────────────────────────────────

    def reload(self) -> None:
        """Reload all data from disk."""
        self._load_all()
        log.info(
            f"Reloaded: {len(self.clients)} clients, "
            f"{len(self.client_projects)} links, "
            f"{len(self.deliverables)} deliverables"
        )