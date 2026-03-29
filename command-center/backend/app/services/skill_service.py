"""
NemoClaw Command Center — Skill Service (CC-5)
Reads built skill YAMLs and registered catalog entries.
Computes dependency graph, health, priority, risk detection, and dry-run.
"""

import logging
import yaml
from pathlib import Path
from collections import defaultdict
from typing import Optional

log = logging.getLogger("cc.skills")


class SkillService:
    """Central service for skill catalog, dependency graph, and dry-run."""

    # Directories/files to skip when scanning skills/
    SKIP_DIRS = {"__pycache__", "graph-validation", "research-brief"}

    def __init__(self, repo_root):
        self.repo_root = Path(repo_root)
        self.skills: dict[str, dict] = {}
        self.agent_skill_map: dict[str, list[str]] = {}
        self._skill_to_agent: dict[str, str] = {}
        self.graph_edges: list[dict] = []
        self.graph_risks: dict = {"circular": [], "orphans": [], "overloaded": []}
        self.reload()

    # ── Loading ────────────────────────────────────────────────────────────

    def reload(self):
        """Reload all skill data from disk."""
        self.skills = {}
        self.graph_edges = []
        self.graph_risks = {"circular": [], "orphans": [], "overloaded": []}
        self._load_agent_skill_map()
        self._load_built_skills()
        self._load_registered_skills()
        self._build_graph()
        self._compute_health()
        self._compute_priority()
        built = sum(1 for s in self.skills.values() if s["status"] == "built")
        reg = sum(1 for s in self.skills.values() if s["status"] == "registered")
        log.info(f"Loaded {len(self.skills)} skills ({built} built, {reg} registered)")

    def _load_agent_skill_map(self):
        """Build agent_id -> [skill_ids] from agent-schema.yaml."""
        self.agent_skill_map = {}
        self._skill_to_agent = {}
        schema_path = self.repo_root / "config" / "agents" / "agent-schema.yaml"
        if not schema_path.exists():
            log.warning(f"Agent schema not found: {schema_path}")
            return
        try:
            data = yaml.safe_load(schema_path.read_text())
            agents = data.get("agents", [])
            for agent in agents:
                agent_id = agent.get("agent_id", "")
                skills_data = agent.get("skills", {})
                all_skills = []
                if isinstance(skills_data, dict):
                    for bucket in ("primary", "future"):
                        for s in skills_data.get(bucket, []):
                            sid = s.get("id", "") if isinstance(s, dict) else str(s)
                            if sid:
                                all_skills.append(sid)
                                self._skill_to_agent[sid] = agent_id
                elif isinstance(skills_data, list):
                    for s in skills_data:
                        sid = s.get("id", "") if isinstance(s, dict) else str(s)
                        if sid:
                            all_skills.append(sid)
                            self._skill_to_agent[sid] = agent_id
                self.agent_skill_map[agent_id] = all_skills
        except Exception as e:
            log.error(f"Failed to load agent schema: {e}")

    def _load_built_skills(self):
        """Load built skills from skills/*/skill.yaml."""
        skills_dir = self.repo_root / "skills"
        if not skills_dir.is_dir():
            return
        for item in sorted(skills_dir.iterdir()):
            if not item.is_dir() or item.name in self.SKIP_DIRS or item.name.startswith("__"):
                continue
            yaml_path = item / "skill.yaml"
            if not yaml_path.exists():
                continue
            try:
                raw = yaml.safe_load(yaml_path.read_text())
                if not raw or not isinstance(raw, dict):
                    continue
                skill = self._normalize_built(raw, item)
                self.skills[skill["id"]] = skill
            except Exception as e:
                self.skills[item.name] = {
                    "id": item.name, "display_name": item.name,
                    "description": f"Failed to load: {e}",
                    "version": "", "status": "built",
                    "health": "misconfigured", "health_reason": str(e),
                    "domain": "", "family": "", "skill_type": "", "tag": "",
                    "schema_version": 0,
                    "assigned_agent": self._skill_to_agent.get(item.name),
                    "priority": "low",
                    "inputs": [], "outputs": [],
                    "composable": {"output_type": "", "feeds_into": [], "accepts_from": []},
                    "contracts": {}, "steps": [], "routing": "",
                    "execution_role": "", "declarative_guarantees": [],
                }

    def _normalize_built(self, raw: dict, skill_dir: Path) -> dict:
        """Normalize a built skill YAML to common format."""
        skill_id = raw.get("name", skill_dir.name)
        composable = raw.get("composable", {}) or {}
        contracts = raw.get("contracts", {}) or {}
        machine = contracts.get("machine_validated", {}) or {}
        sla = machine.get("sla", {}) or {}
        quality = machine.get("quality", {}) or {}

        return {
            "id": skill_id,
            "display_name": raw.get("display_name", skill_id),
            "description": (raw.get("description") or "").strip(),
            "version": raw.get("version", ""),
            "status": "built",
            "health": "healthy",
            "health_reason": "",
            "domain": raw.get("domain", ""),
            "family": raw.get("family", ""),
            "skill_type": raw.get("skill_type", ""),
            "tag": raw.get("tag", ""),
            "schema_version": raw.get("schema_version", 1),
            "assigned_agent": raw.get("assigned_agent") or self._skill_to_agent.get(skill_id),
            "priority": "medium",
            "inputs": raw.get("inputs", []),
            "outputs": raw.get("outputs", []),
            "composable": {
                "output_type": composable.get("output_type", ""),
                "feeds_into": composable.get("can_feed_into", composable.get("feeds_into", [])) or [],
                "accepts_from": composable.get("accepts_input_from", composable.get("accepts_from", [])) or [],
            },
            "contracts": {
                "max_cost_usd": sla.get("max_cost_usd") or contracts.get("max_cost_usd"),
                "max_execution_seconds": sla.get("max_execution_seconds") or contracts.get("max_execution_seconds"),
                "min_quality_score": quality.get("min_quality_score") or contracts.get("min_quality_score"),
            },
            "steps": [
                {"id": s.get("id", ""), "name": s.get("name", ""),
                 "step_type": s.get("step_type", ""), "task_class": s.get("task_class", "")}
                for s in raw.get("steps", [])
            ],
            "routing": (raw.get("routing", {}).get("default_alias", "")
                        if isinstance(raw.get("routing"), dict)
                        else raw.get("routing", "")),
            "execution_role": (raw.get("execution_role") or "").strip(),
            "declarative_guarantees": (
                contracts.get("declarative_guarantees", []) or
                raw.get("declarative_guarantees", []) or []
            ),
        }

    def _load_registered_skills(self):
        """Load registered skills from docs/skill-catalog-*.yaml."""
        docs_dir = self.repo_root / "docs"
        if not docs_dir.is_dir():
            return
        for catalog_path in sorted(docs_dir.glob("skill-catalog-*.yaml")):
            try:
                raw_text = catalog_path.read_text()
                # Catalog inputs are freeform strings that break YAML
                # Quote any list item containing parentheses
                fixed_lines = []
                for line in raw_text.split(chr(10)):
                    stripped = line.strip()
                    if stripped.startswith('- ') and '(' in stripped and not stripped.startswith('- id:'):
                        indent = len(line) - len(line.lstrip())
                        safe = stripped[2:].replace(chr(34), chr(92)+chr(34))
                        fixed_lines.append(' ' * indent + '- ' + chr(34) + safe + chr(34))
                    else:
                        fixed_lines.append(line)
                data = yaml.safe_load(chr(10).join(fixed_lines))
                if not data or "skills" not in data:
                    continue
                for entry in data["skills"]:
                    skill = self._normalize_registered(entry)
                    self.skills[skill["id"]] = skill
            except Exception as e:
                log.error(f"Failed to load catalog {catalog_path.name}: {e}")

    def _normalize_registered(self, entry: dict) -> dict:
        """Normalize a registered skill catalog entry."""
        skill_id = entry.get("id", "unknown")
        composable = entry.get("composable", {}) or {}
        contracts = entry.get("contracts", {}) or {}

        return {
            "id": skill_id,
            "display_name": entry.get("display_name", skill_id),
            "description": (entry.get("description") or "").strip(),
            "version": "",
            "status": "registered",
            "health": "not_built",
            "health_reason": "Skill registered but not yet built",
            "domain": entry.get("domain", ""),
            "family": entry.get("family", ""),
            "skill_type": entry.get("skill_type", ""),
            "tag": entry.get("tag", ""),
            "schema_version": 0,
            "assigned_agent": entry.get("assigned_agent") or self._skill_to_agent.get(skill_id),
            "priority": "medium",
            "inputs": entry.get("inputs", []),
            "outputs": [],
            "composable": {
                "output_type": entry.get("output_type", ""),
                "feeds_into": composable.get("feeds_into", []) or [],
                "accepts_from": composable.get("accepts_from", []) or [],
            },
            "contracts": {
                "max_cost_usd": contracts.get("max_cost_usd"),
                "max_execution_seconds": contracts.get("max_execution_seconds"),
                "min_quality_score": contracts.get("min_quality_score"),
            },
            "steps": [],
            "routing": entry.get("routing", ""),
            "execution_role": "",
            "declarative_guarantees": entry.get("declarative_guarantees", []) or [],
        }

    # ── Graph ──────────────────────────────────────────────────────────────

    def _build_graph(self):
        """Build dependency graph edges and detect risks."""
        self.graph_edges = []
        incoming = defaultdict(int)
        outgoing = defaultdict(int)
        adjacency: dict[str, set] = defaultdict(set)
        edge_set: set[tuple] = set()

        for skill_id, skill in self.skills.items():
            comp = skill.get("composable", {})
            for target in comp.get("feeds_into", []):
                key = (skill_id, target)
                if key not in edge_set:
                    edge_set.add(key)
                    self.graph_edges.append({"source": skill_id, "target": target, "type": "feeds_into"})
                    outgoing[skill_id] += 1
                    incoming[target] += 1
                    adjacency[skill_id].add(target)

            for source in comp.get("accepts_from", []):
                key = (source, skill_id)
                if key not in edge_set:
                    edge_set.add(key)
                    self.graph_edges.append({"source": source, "target": skill_id, "type": "accepts_from"})
                    outgoing[source] += 1
                    incoming[skill_id] += 1
                    adjacency[source].add(skill_id)

        # Orphans: skills with no edges at all
        nodes_in_graph = set()
        for e in self.graph_edges:
            nodes_in_graph.add(e["source"])
            nodes_in_graph.add(e["target"])
        self.graph_risks["orphans"] = [sid for sid in self.skills if sid not in nodes_in_graph]

        # Overloaded: 5+ incoming dependencies
        self.graph_risks["overloaded"] = [sid for sid, c in incoming.items() if c >= 5]

        # Circular: DFS cycle detection
        self.graph_risks["circular"] = self._detect_cycles(adjacency)

    def _detect_cycles(self, adjacency: dict) -> list:
        """Detect circular dependencies via DFS."""
        cycles = []
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {n: WHITE for n in self.skills}

        def dfs(node, path):
            color[node] = GRAY
            for neighbor in adjacency.get(node, []):
                if color.get(neighbor, WHITE) == GRAY:
                    idx = path.index(neighbor) if neighbor in path else len(path)
                    cycles.append(path[idx:] + [neighbor])
                elif color.get(neighbor, WHITE) == WHITE:
                    dfs(neighbor, path + [neighbor])
            color[node] = BLACK

        for node in self.skills:
            if color.get(node, WHITE) == WHITE:
                dfs(node, [node])
        return cycles

    # ── Health ─────────────────────────────────────────────────────────────

    def _compute_health(self):
        """Compute health status for each skill."""
        for skill_id, skill in self.skills.items():
            if skill["status"] == "registered":
                continue  # already "not_built"
            if skill["health"] == "misconfigured":
                continue  # set during load error

            comp = skill.get("composable", {})
            refs = (comp.get("feeds_into", []) or []) + (comp.get("accepts_from", []) or [])
            missing = [r for r in refs if r not in self.skills]

            if missing:
                skill["health"] = "missing_dependencies"
                skill["health_reason"] = f"References missing skills: {', '.join(missing)}"
                continue

            has_agent = bool(skill.get("assigned_agent"))
            has_edges = any(
                e["source"] == skill_id or e["target"] == skill_id
                for e in self.graph_edges
            )
            if not has_agent and not has_edges:
                skill["health"] = "unused"
                skill["health_reason"] = "No agent assigned and no dependency connections"
            else:
                skill["health"] = "healthy"
                skill["health_reason"] = ""

    # ── Priority ───────────────────────────────────────────────────────────

    def _compute_priority(self):
        """Compute priority from dependent count + domain."""
        dep_count: dict[str, int] = defaultdict(int)
        for edge in self.graph_edges:
            dep_count[edge["source"]] += 1

        for skill_id, skill in self.skills.items():
            deps = dep_count.get(skill_id, 0)
            domain = skill.get("domain", "")
            if deps >= 5:
                skill["priority"] = "critical"
            elif deps >= 3 or domain in ("A", "B"):
                skill["priority"] = "high"
            elif deps >= 1:
                skill["priority"] = "medium"
            else:
                skill["priority"] = "low"

    # ── Public API ─────────────────────────────────────────────────────────

    def get_catalog(
        self,
        status: Optional[str] = None,
        domain: Optional[str] = None,
        skill_type: Optional[str] = None,
        agent: Optional[str] = None,
        priority: Optional[str] = None,
        health: Optional[str] = None,
        search: Optional[str] = None,
    ) -> list[dict]:
        """Return filtered skill catalog."""
        results = []
        for skill in self.skills.values():
            if status and skill["status"] != status:
                continue
            if domain and skill["domain"].lower() != domain.lower():
                continue
            if skill_type and skill["skill_type"] != skill_type:
                continue
            if agent and skill.get("assigned_agent") != agent:
                continue
            if priority and skill["priority"] != priority:
                continue
            if health and skill["health"] != health:
                continue
            if search:
                q = search.lower()
                hay = f"{skill['id']} {skill['display_name']} {skill['description']} {skill['tag']}".lower()
                if q not in hay:
                    continue
            results.append(skill)
        return results

    def get_skill(self, skill_id: str) -> Optional[dict]:
        """Return single skill detail."""
        return self.skills.get(skill_id)

    def get_graph(self) -> dict:
        """Return dependency graph: nodes, edges, risks."""
        nodes = [
            {
                "id": s["id"], "display_name": s["display_name"],
                "status": s["status"], "domain": s["domain"],
                "family": s["family"], "skill_type": s["skill_type"],
                "priority": s["priority"], "health": s["health"],
                "assigned_agent": s.get("assigned_agent"),
            }
            for s in self.skills.values()
        ]
        return {
            "nodes": nodes,
            "edges": self.graph_edges,
            "risks": self.graph_risks,
            "stats": {
                "total_nodes": len(nodes),
                "total_edges": len(self.graph_edges),
                "circular_count": len(self.graph_risks["circular"]),
                "orphan_count": len(self.graph_risks["orphans"]),
                "overloaded_count": len(self.graph_risks["overloaded"]),
            },
        }

    def get_stats(self) -> dict:
        """Return summary statistics."""
        by_status: dict[str, int] = defaultdict(int)
        by_domain: dict[str, int] = defaultdict(int)
        by_priority: dict[str, int] = defaultdict(int)
        by_health: dict[str, int] = defaultdict(int)
        by_agent: dict[str, int] = defaultdict(int)
        by_type: dict[str, int] = defaultdict(int)

        for skill in self.skills.values():
            by_status[skill["status"]] += 1
            by_domain[skill.get("domain") or "unknown"] += 1
            by_priority[skill["priority"]] += 1
            by_health[skill["health"]] += 1
            by_type[skill.get("skill_type") or "unknown"] += 1
            if skill.get("assigned_agent"):
                by_agent[skill["assigned_agent"]] += 1

        return {
            "total": len(self.skills),
            "by_status": dict(by_status),
            "by_domain": dict(by_domain),
            "by_priority": dict(by_priority),
            "by_health": dict(by_health),
            "by_type": dict(by_type),
            "by_agent": dict(by_agent),
            "graph": {
                "total_edges": len(self.graph_edges),
                "circular_deps": len(self.graph_risks["circular"]),
                "orphans": len(self.graph_risks["orphans"]),
                "overloaded": len(self.graph_risks["overloaded"]),
            },
        }

    def get_by_agent(self, agent_id: str) -> dict:
        """Return skills for an agent, split by primary/future."""
        primary, future = [], []
        for sid, skill in self.skills.items():
            if skill.get("assigned_agent") == agent_id:
                if skill["status"] == "built":
                    primary.append(skill)
                else:
                    future.append(skill)
        return {
            "agent_id": agent_id,
            "total": len(primary) + len(future),
            "primary": primary,
            "future": future,
        }

    def dry_run(self, skill_id: str, provided_inputs: Optional[dict] = None) -> dict:
        """Validate skill and inputs without executing."""
        skill = self.skills.get(skill_id)
        if not skill:
            return {"error": f"Skill '{skill_id}' not found", "passed": False}

        dep_chain = self._get_dependency_chain(skill_id)

        if skill["status"] == "registered":
            return {
                "skill_id": skill_id, "display_name": skill["display_name"],
                "passed": False,
                "error": "Skill is registered but not yet built. Dry-run requires a built skill.",
                "input_schema": skill["inputs"],
                "dependency_chain": dep_chain,
            }

        provided = provided_inputs or {}
        errors, warnings = [], []

        # Validate inputs against schema
        for inp in skill.get("inputs", []):
            if not isinstance(inp, dict):
                continue
            name = inp.get("name", "")
            required = inp.get("required", False)
            validation = inp.get("validation", {}) or {}

            if required and name not in provided:
                errors.append(f"Required input '{name}' not provided")
                continue

            if name in provided:
                value = provided[name]
                if inp.get("type") == "string" and isinstance(value, str):
                    min_len = validation.get("min_length")
                    max_len = validation.get("max_length")
                    if min_len and len(value) < min_len:
                        errors.append(f"Input '{name}' too short (min {min_len}, got {len(value)})")
                    if max_len and len(value) > max_len:
                        errors.append(f"Input '{name}' too long (max {max_len}, got {len(value)})")

        # Check dependency health
        dep_health = {"all_available": True, "missing": [], "unhealthy": []}
        for ref_list in (dep_chain.get("upstream", []), dep_chain.get("downstream", [])):
            for ref in ref_list:
                ref_id = ref["id"]
                if ref_id not in self.skills:
                    dep_health["all_available"] = False
                    dep_health["missing"].append(ref_id)
                elif self.skills[ref_id]["health"] not in ("healthy", "not_built"):
                    dep_health["unhealthy"].append(ref_id)

        if dep_health["missing"]:
            warnings.append(f"Missing dependency skills: {', '.join(dep_health['missing'])}")

        contracts = skill.get("contracts", {})
        cost = contracts.get("max_cost_usd")
        time_s = contracts.get("max_execution_seconds")

        return {
            "skill_id": skill_id,
            "display_name": skill["display_name"],
            "passed": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "input_schema": skill.get("inputs", []),
            "provided_inputs": provided,
            "dependency_chain": dep_chain,
            "dependency_health": dep_health,
            "estimated_cost": f"${cost}" if cost else "N/A",
            "estimated_time": f"{time_s}s" if time_s else "N/A",
            "output_structure": skill.get("outputs", []),
            "steps": skill.get("steps", []),
            "routing": skill.get("routing", ""),
            "health": skill["health"],
            "priority": skill["priority"],
        }

    def _get_dependency_chain(self, skill_id: str) -> dict:
        """Get upstream and downstream skills."""
        upstream, downstream = [], []
        for edge in self.graph_edges:
            if edge["target"] == skill_id:
                src = self.skills.get(edge["source"])
                upstream.append({
                    "id": edge["source"],
                    "display_name": src["display_name"] if src else edge["source"],
                    "status": src["status"] if src else "unknown",
                })
            elif edge["source"] == skill_id:
                tgt = self.skills.get(edge["target"])
                downstream.append({
                    "id": edge["target"],
                    "display_name": tgt["display_name"] if tgt else edge["target"],
                    "status": tgt["status"] if tgt else "unknown",
                })
        return {"upstream": upstream, "downstream": downstream}
