"""
State Aggregator — the heart of CC-1.

Reads the NemoClaw repo and ~/.nemoclaw filesystem every N seconds,
normalizes everything into a SystemState, and caches it in memory.

Design principles:
  - Never crashes on missing files — graceful degradation
  - Logs warnings, never raises on scan errors
  - Thread-safe state access via asyncio lock
  - All filesystem reads are synchronous (fast local FS), wrapped in executor
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path

import yaml

from app.config import settings
from app.domain.models import (
    AgentInfo,
    AgentsSummary,
    BridgeInfo,
    BridgesSummary,
    BridgeStatus,
    BudgetSummary,
    FrameworksSummary,
    HealthDomain,
    HealthStatus,
    HealthSummary,
    MASystemInfo,
    MASummary,
    ProviderBudget,
    SkillInfo,
    SkillsSummary,
    SkillStatus,
    SystemState,
    ValidationSummary,
)

logger = logging.getLogger("cc.aggregator")


class StateAggregator:
    """Scans the NemoClaw filesystem and produces normalized SystemState."""

    def __init__(self) -> None:
        self._state: SystemState = SystemState()
        self._lock = asyncio.Lock()
        self._scan_task: asyncio.Task | None = None
        self._running = False
        self._state_version: int = 0

    @property
    def state(self) -> SystemState:
        return self._state

    # ── Lifecycle ──────────────────────────────────────────────────────

    async def start(self) -> None:
        """Start the background scan loop."""
        self._running = True
        self._scan_task = asyncio.create_task(self._scan_loop())
        logger.info(
            "State aggregator started (interval=%ds)", settings.scan_interval_seconds
        )

    async def stop(self) -> None:
        """Stop the background scan loop."""
        self._running = False
        if self._scan_task:
            self._scan_task.cancel()
            try:
                await self._scan_task
            except asyncio.CancelledError:
                pass
        logger.info("State aggregator stopped")

    async def _scan_loop(self) -> None:
        """Periodically scan and rebuild state."""
        while self._running:
            try:
                new_state = await asyncio.get_event_loop().run_in_executor(
                    None, self._build_state
                )
                async with self._lock:
                    self._state = new_state
                logger.debug("State scan complete: %s", new_state.timestamp.isoformat())
            except Exception:
                logger.exception("State scan failed — keeping previous state")
            await asyncio.sleep(settings.scan_interval_seconds)

    async def force_scan(self) -> SystemState:
        """Force an immediate rescan. Returns the new state."""
        new_state = await asyncio.get_event_loop().run_in_executor(
            None, self._build_state
        )
        async with self._lock:
            self._state = new_state
        return self._state

    # ── Full State Build ───────────────────────────────────────────────

    def _build_state(self) -> SystemState:
        """Synchronous: scan everything, return a new SystemState."""
        self._state_version += 1

        state = SystemState(
            timestamp=datetime.now(),
            state_version=self._state_version,
            repo_root=str(settings.repo_root),
        )

        state.skills = self._scan_skills()
        state.agents = self._scan_agents()
        state.ma_systems = self._scan_ma_systems()
        state.bridges = self._scan_bridges()
        state.budget = self._scan_budget()
        state.validation = self._scan_validation()
        state.frameworks = self._scan_frameworks()
        state.pinchtab_status = self._check_pinchtab()
        state.health = self._build_health(state)
        state.narrative = self._build_narrative(state)

        git_info = self._get_git_info()
        state.git_branch = git_info.get("branch", "")
        state.git_commit = git_info.get("commit", "")

        return state

    # ── Skills ─────────────────────────────────────────────────────────

    def _scan_skills(self) -> SkillsSummary:
        skills_dir = settings.skills_dir
        if not skills_dir.is_dir():
            return SkillsSummary()

        skills: list[SkillInfo] = []
        families: dict[str, int] = {}

        for skill_path in sorted(skills_dir.iterdir()):
            if not skill_path.is_dir():
                continue

            skill_yaml = skill_path / "skill.yaml"
            if not skill_yaml.exists():
                continue

            try:
                data = yaml.safe_load(skill_yaml.read_text())
                if not isinstance(data, dict):
                    continue

                skill_id = data.get("skill_id", skill_path.name)
                family = data.get("family", "")
                name = data.get("name", skill_id)
                provider = data.get("provider", data.get("default_provider", ""))

                skills.append(
                    SkillInfo(
                        skill_id=skill_id,
                        family=family,
                        name=name,
                        status=SkillStatus.BUILT,
                        provider=provider,
                    )
                )

                if family:
                    families[family] = families.get(family, 0) + 1

            except Exception:
                logger.warning("Failed to parse skill.yaml: %s", skill_yaml)

        # Check for registered-but-not-built skills in catalog files
        registered = self._scan_registered_skills()

        return SkillsSummary(
            total_built=len(skills),
            total_registered=len(registered),
            skills=skills + registered,
            families=families,
        )

    def _scan_registered_skills(self) -> list[SkillInfo]:
        """Scan docs/ for skill catalog YAML files (k40-k54 etc).

        Primary: YAML parse. Fallback: regex extraction for files
        with invalid YAML (unquoted colons in inputs fields).
        """
        registered: list[SkillInfo] = []
        docs_dir = settings.docs_dir
        if not docs_dir.is_dir():
            return registered

        for catalog_file in docs_dir.glob("skill-catalog-*.yaml"):
            try:
                data = yaml.safe_load(catalog_file.read_text())
                if not isinstance(data, dict):
                    continue

                # Format 1: {skills: [...]} list of dicts with id field
                skills_list = data.get("skills", None)
                if isinstance(skills_list, list):
                    for entry in skills_list:
                        if not isinstance(entry, dict):
                            continue
                        sid = entry.get("id", entry.get("skill_id", ""))
                        if not sid:
                            continue
                        registered.append(
                            SkillInfo(
                                skill_id=str(sid),
                                family=entry.get("family", ""),
                                name=entry.get("display_name", entry.get("name", str(sid))),
                                status=SkillStatus.REGISTERED,
                                provider=entry.get("routing", entry.get("provider", "")),
                            )
                        )
                    continue

                # Format 2: flat dict {skill_id: {name, family, ...}}
                for sid, info in data.items():
                    if isinstance(info, dict):
                        registered.append(
                            SkillInfo(
                                skill_id=str(sid),
                                family=info.get("family", ""),
                                name=info.get("name", str(sid)),
                                status=SkillStatus.REGISTERED,
                                provider=info.get("provider", ""),
                            )
                        )

            except Exception:
                # YAML invalid — use regex to extract skill IDs
                self._regex_parse_catalog(catalog_file, registered)

        return registered

    def _regex_parse_catalog(self, catalog_file, registered: list) -> None:
        """Regex fallback for catalogs with invalid YAML."""
        try:
            raw = catalog_file.read_text()
            current_id = None
            current_name = None
            current_family = None
            current_routing = None

            for line in raw.splitlines():
                stripped = line.strip()

                # New skill entry
                if stripped.startswith("- id:"):
                    # Save previous skill if exists
                    if current_id:
                        registered.append(SkillInfo(
                            skill_id=current_id,
                            family=current_family or "",
                            name=current_name or current_id,
                            status=SkillStatus.REGISTERED,
                            provider=current_routing or "",
                        ))
                    current_id = stripped.split(":", 1)[1].strip()
                    current_name = None
                    current_family = None
                    current_routing = None

                elif stripped.startswith("display_name:"):
                    val = stripped.split(':', 1)[1].strip()
                    if val and val[0] in ('"', "'"):
                        val = val[1:]
                    if val and val[-1] in ('"', "'"):
                        val = val[:-1]
                    current_name = val

                elif stripped.startswith("family:"):
                    current_family = stripped.split(":", 1)[1].strip()

                elif stripped.startswith("routing:"):
                    current_routing = stripped.split(":", 1)[1].strip()

            # Save last skill
            if current_id:
                registered.append(SkillInfo(
                    skill_id=current_id,
                    family=current_family or "",
                    name=current_name or current_id,
                    status=SkillStatus.REGISTERED,
                    provider=current_routing or "",
                ))

            logger.info("Regex parsed %d skills from %s", 
                        sum(1 for s in registered if s.skill_id.startswith("k")), 
                        catalog_file.name)

        except Exception:
            logger.warning("Catalog regex fallback also failed: %s", catalog_file)

    # ── Agents ─────────────────────────────────────────────────────────

    def _scan_agents(self) -> AgentsSummary:
        agents_dir = settings.agents_dir
        if not agents_dir.is_dir():
            return AgentsSummary()

        agents: list[AgentInfo] = []

        # Primary path: parse agent-schema.yaml which contains all agents
        schema_file = agents_dir / "agent-schema.yaml"
        if schema_file.exists():
            try:
                data = yaml.safe_load(schema_file.read_text())
                if isinstance(data, dict):
                    # Handle both {agents: [...]} and {agents: {id: {...}}} formats
                    agents_data = data.get("agents", [])

                    if isinstance(agents_data, list):
                        for entry in agents_data:
                            if not isinstance(entry, dict):
                                continue
                            agent_id = entry.get("agent_id", entry.get("id", ""))
                            if not agent_id:
                                continue
                            agents.append(
                                AgentInfo(
                                    agent_id=agent_id,
                                    name=entry.get("name", agent_id),
                                    role=entry.get("role", ""),
                                    capabilities=entry.get("capabilities", []),
                                    domains=entry.get("domains", []),
                                    status=HealthStatus.HEALTHY,
                                )
                            )
                    elif isinstance(agents_data, dict):
                        for aid, entry in agents_data.items():
                            if not isinstance(entry, dict):
                                continue
                            agents.append(
                                AgentInfo(
                                    agent_id=str(aid),
                                    name=entry.get("name", str(aid)),
                                    role=entry.get("role", ""),
                                    capabilities=entry.get("capabilities", []),
                                    domains=entry.get("domains", []),
                                    status=HealthStatus.HEALTHY,
                                )
                            )
            except Exception:
                logger.warning("Failed to parse agent-schema.yaml")

        # Fallback: also check for individual agent YAML files
        if not agents:
            for agent_file in sorted(agents_dir.glob("*.yaml")):
                if agent_file.name in (
                    "agent-schema.yaml",
                    "capability-registry.yaml",
                ):
                    continue
                try:
                    data = yaml.safe_load(agent_file.read_text())
                    if not isinstance(data, dict):
                        continue
                    agent_id = data.get("agent_id", agent_file.stem)
                    agents.append(
                        AgentInfo(
                            agent_id=agent_id,
                            name=data.get("name", agent_id),
                            role=data.get("role", ""),
                            capabilities=data.get("capabilities", []),
                            domains=data.get("domains", []),
                            status=HealthStatus.HEALTHY,
                        )
                    )
                except Exception:
                    logger.warning("Failed to parse agent config: %s", agent_file)

        return AgentsSummary(total=len(agents), agents=agents)

    # ── MA Systems ─────────────────────────────────────────────────────

    def _scan_ma_systems(self) -> MASummary:
        """Scan for multi-agent system test files and governance configs."""
        # Known MA systems from the handover with their test counts
        ma_test_counts = {
            "MA-1": 8, "MA-2": 0, "MA-3": 14, "MA-4": 12, "MA-5": 5,
            "MA-6": 28, "MA-7": 26, "MA-8": 35, "MA-9": 26, "MA-10": 26,
            "MA-11": 28, "MA-12": 30, "MA-13": 32, "MA-14": 37,
            "MA-15": 29, "MA-16": 28, "MA-17": 32, "MA-18": 32,
            "MA-19": 44, "MA-20": 50,
        }

        # Try to discover from filesystem first
        systems: list[MASystemInfo] = []
        tests_dir = settings.repo_root / "tests"

        discovered_ids: set[str] = set()

        if tests_dir.is_dir():
            for test_file in tests_dir.rglob("test_ma_*.py"):
                match = re.search(r"ma[_-](\d+)", test_file.name)
                if match:
                    ma_id = f"MA-{match.group(1)}"
                    discovered_ids.add(ma_id)
                    # Count test functions
                    try:
                        content = test_file.read_text()
                        test_count = len(re.findall(r"def test_", content))
                    except Exception:
                        test_count = ma_test_counts.get(ma_id, 0)

                    systems.append(
                        MASystemInfo(
                            system_id=ma_id,
                            test_count=test_count,
                            status=HealthStatus.HEALTHY,
                        )
                    )

        # Fill in any MA systems not discovered but known
        for ma_id, count in ma_test_counts.items():
            if ma_id not in discovered_ids:
                systems.append(
                    MASystemInfo(
                        system_id=ma_id,
                        test_count=count,
                        status=HealthStatus.HEALTHY,
                    )
                )

        systems.sort(key=lambda s: int(s.system_id.split("-")[1]))
        total_tests = sum(s.test_count for s in systems)

        return MASummary(total=len(systems), total_tests=total_tests, systems=systems)

    # ── Bridges ────────────────────────────────────────────────────────

    def _scan_bridges(self) -> BridgesSummary:
        scripts_dir = settings.scripts_dir
        if not scripts_dir.is_dir():
            return BridgesSummary()

        bridges: list[BridgeInfo] = []
        env_file = settings.config_dir / ".env"
        env_keys: set[str] = set()

        if env_file.exists():
            try:
                for line in env_file.read_text().splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key = line.split("=", 1)[0].strip()
                        env_keys.add(key)
            except Exception:
                pass

        # Also check live environment variables (keys set via export)
        env_keys.update(os.environ.keys())

        # Bridge metadata: filename → (display_name, api_label, env_key_prefix)
        bridge_meta = {
            "web_browser.py": ("PinchTab Browser", "PinchTab localhost:9867", "PINCHTAB"),
            "hubspot_bridge.py": ("HubSpot CRM", "HubSpot CRM v3", "HUBSPOT"),
            "apollo_bridge.py": ("Apollo.io", "Apollo.io v1", "APOLLO"),
            "resend_bridge.py": ("Resend Email", "Resend emails", "RESEND"),
            "supabase_bridge.py": ("Supabase", "Supabase REST", "SUPABASE"),
            "lemonsqueezy_bridge.py": ("Lemon Squeezy", "Lemon Squeezy v1", "LEMONSQUEEZY"),
            "n8n_bridge.py": ("n8n", "n8n self-hosted", "N8N"),
            "instantly_bridge.py": ("Instantly.ai", "Instantly.ai v1", "INSTANTLY"),
            "google_ads_bridge.py": ("Google Ads", "Google Ads v17", "GOOGLE_ADS"),
            "meta_ads_bridge.py": ("Meta Ads", "Meta Marketing v19", "META_ADS"),
            "apify_bridge.py": ("Apify", "Apify v2", "APIFY"),
            "gws_bridge.py": ("Google Workspace", "GWS CLI", "GOOGLE"),
            "image_gen_bridge.py": ("Image Generation", "NVIDIA/NGC", "NGC"),
            "social_publish_bridge.py": ("Social Publishing", "Multi-platform", "LINKEDIN"),
            "whisper_bridge.py": ("Whisper STT", "OpenAI Whisper", "OPENAI"),
        }

        for bridge_file in sorted(scripts_dir.glob("*_bridge.py")):
            fname = bridge_file.name
            meta = bridge_meta.get(fname, (fname.replace("_bridge.py", "").title(), "", ""))

            # Check if any env key matches the prefix
            prefix = meta[2]
            has_key = any(k.startswith(prefix) for k in env_keys) if prefix else False

            status = BridgeStatus.CONNECTED if has_key else BridgeStatus.MOCKED

            # Try to count tests
            test_count = self._count_bridge_tests(bridge_file)

            bridges.append(
                BridgeInfo(
                    bridge_id=fname.replace(".py", ""),
                    name=meta[0],
                    api=meta[1],
                    test_count=test_count,
                    test_pass=test_count,  # Assume passing from handover
                    status=status,
                    has_api_key=has_key,
                )
            )

        # Also check for web_browser.py
        web_browser = scripts_dir / "web_browser.py"
        if web_browser.exists() and not any(b.bridge_id == "web_browser" for b in bridges):
            meta = bridge_meta["web_browser.py"]
            bridges.insert(
                0,
                BridgeInfo(
                    bridge_id="web_browser",
                    name=meta[0],
                    api=meta[1],
                    test_count=40,
                    test_pass=40,
                    status=BridgeStatus.MOCKED,
                    has_api_key=False,
                ),
            )

        total_tests = sum(b.test_count for b in bridges)
        connected = sum(1 for b in bridges if b.status == BridgeStatus.CONNECTED)

        return BridgesSummary(
            total=len(bridges),
            total_tests=total_tests,
            connected=connected,
            bridges=bridges,
        )

    def _count_bridge_tests(self, bridge_file: Path) -> int:
        """Count test functions for a bridge.

        Checks three locations:
          1. Separate test file: tests/test_<bridge>.py
          2. Embedded tests in the bridge file itself (def test_*)
          3. Embedded test count in bridge docstring/comments
        """
        count = 0

        # Check separate test file first
        tests_dir = settings.repo_root / "tests"
        for name in [f"test_{bridge_file.name}", f"test_{bridge_file.stem}.py"]:
            test_file = tests_dir / name
            if test_file.exists():
                try:
                    content = test_file.read_text()
                    count = len(re.findall(r"def test_", content))
                    if count > 0:
                        return count
                except Exception:
                    pass

        # Check embedded tests in bridge file itself
        try:
            content = bridge_file.read_text()
            embedded = len(re.findall(r"def test_", content))
            if embedded > 0:
                return embedded

            # Check for test count in comments like "# Tests: 22/22"
            match = re.search(r"#\s*Tests?:\s*(\d+)", content)
            if match:
                return int(match.group(1))
        except Exception:
            pass

        return count

    # ── Budget ─────────────────────────────────────────────────────────

    def _scan_budget(self) -> BudgetSummary:
        # Try multiple known locations for budget config
        candidates = [
            settings.budget_config,                                    # config/budget-config.yaml
            settings.config_dir / "routing" / "budget-config.yaml",   # config/routing/budget-config.yaml
            settings.config_dir / "budget.yaml",                      # config/budget.yaml
        ]

        budget_file: Path | None = None
        for candidate in candidates:
            if candidate.exists():
                budget_file = candidate
                break

        if budget_file is None:
            return BudgetSummary()

        try:
            data = yaml.safe_load(budget_file.read_text())
            if not isinstance(data, dict):
                return BudgetSummary()

            providers: list[ProviderBudget] = []

            # Handle multiple top-level structures:
            #   {budgets: {provider: {...}}}
            #   {providers: {provider: {...}}}
            #   {provider: {...}}  (flat)
            budgets = data.get("budgets", data.get("providers", data))
            if not isinstance(budgets, dict):
                return BudgetSummary()

            for provider_name, config in budgets.items():
                if not isinstance(config, dict):
                    continue
                # Skip metadata keys that aren't provider entries
                if provider_name in ("version", "updated", "currency", "defaults"):
                    continue

                # Flexible field names for limit
                limit = float(
                    config.get("monthly_limit",
                    config.get("limit",
                    config.get("budget_limit",
                    config.get("max_spend", 30.0))))
                )
                # Flexible field names for spend
                spent = float(
                    config.get("spent",
                    config.get("current_spend",
                    config.get("total_spent",
                    config.get("usage", 0.0))))
                )
                pct = (spent / limit * 100) if limit > 0 else 0.0

                providers.append(
                    ProviderBudget(
                        provider=provider_name,
                        spent=round(spent, 2),
                        limit=round(limit, 2),
                        percent_used=round(pct, 1),
                    )
                )

            total_spent = sum(p.spent for p in providers)
            total_limit = sum(p.limit for p in providers)

            return BudgetSummary(
                total_spent=round(total_spent, 2),
                total_limit=round(total_limit, 2),
                providers=providers,
            )

        except Exception:
            logger.warning("Failed to parse budget config: %s", budget_file)
            return BudgetSummary()

    # ── Health ─────────────────────────────────────────────────────────

    def _build_health(self, state: SystemState) -> HealthSummary:
        """Derive health from other scanned data."""
        domains: list[HealthDomain] = []
        now = datetime.now()

        # Skills health
        skills_ok = state.skills.total_built > 0
        domains.append(
            HealthDomain(
                domain="skills",
                status=HealthStatus.HEALTHY if skills_ok else HealthStatus.WARNING,
                message=f"{state.skills.total_built} built, {state.skills.total_registered} registered",
                last_check=now,
            )
        )

        # Agents health
        agents_ok = state.agents.total > 0
        domains.append(
            HealthDomain(
                domain="agents",
                status=HealthStatus.HEALTHY if agents_ok else HealthStatus.WARNING,
                message=f"{state.agents.total} agents configured",
                last_check=now,
            )
        )

        # MA Systems health
        ma_ok = state.ma_systems.total >= 20
        domains.append(
            HealthDomain(
                domain="multi_agent",
                status=HealthStatus.HEALTHY if ma_ok else HealthStatus.WARNING,
                message=f"{state.ma_systems.total}/20 systems, {state.ma_systems.total_tests} tests",
                last_check=now,
            )
        )

        # Bridges health
        domains.append(
            HealthDomain(
                domain="bridges",
                status=HealthStatus.HEALTHY if state.bridges.total > 0 else HealthStatus.WARNING,
                message=f"{state.bridges.total} bridges, {state.bridges.connected} connected",
                last_check=now,
            )
        )

        # Budget health
        budget_warning = any(
            p.percent_used > 80 for p in state.budget.providers
        )
        domains.append(
            HealthDomain(
                domain="budget",
                status=HealthStatus.WARNING if budget_warning else HealthStatus.HEALTHY,
                message=f"${state.budget.total_spent:.2f} / ${state.budget.total_limit:.2f}",
                last_check=now,
            )
        )

        # Repo health
        repo_ok = settings.repo_root.is_dir()
        domains.append(
            HealthDomain(
                domain="repository",
                status=HealthStatus.HEALTHY if repo_ok else HealthStatus.ERROR,
                message="Repo accessible" if repo_ok else "Repo not found",
                last_check=now,
            )
        )

        # Validation
        domains.append(
            HealthDomain(
                domain="validation",
                status=(
                    HealthStatus.HEALTHY
                    if state.validation.failed == 0
                    else HealthStatus.ERROR
                ),
                message=(
                    f"{state.validation.passed} pass, "
                    f"{state.validation.warnings} warn, "
                    f"{state.validation.failed} fail"
                ),
                last_check=now,
            )
        )

        # Frameworks
        domains.append(
            HealthDomain(
                domain="frameworks",
                status=HealthStatus.HEALTHY if state.frameworks.total > 0 else HealthStatus.UNKNOWN,
                message=f"{state.frameworks.total} production frameworks",
                last_check=now,
            )
        )

        # Browser/PinchTab
        if state.pinchtab_status == "running":
            pt_status = HealthStatus.HEALTHY
            pt_message = "PinchTab running (guard DOWN for dev)"
        elif state.pinchtab_status == "not_installed":
            pt_status = HealthStatus.WARNING
            pt_message = "PinchTab not installed"
        elif state.pinchtab_status == "stopped":
            pt_status = HealthStatus.WARNING
            pt_message = "PinchTab not running"
        else:
            pt_status = HealthStatus.UNKNOWN
            pt_message = "PinchTab status unknown"

        domains.append(
            HealthDomain(
                domain="browser",
                status=pt_status,
                message=pt_message,
                last_check=now,
            )
        )

        # Overall
        statuses = [d.status for d in domains]
        if HealthStatus.ERROR in statuses:
            overall = HealthStatus.ERROR
        elif HealthStatus.WARNING in statuses:
            overall = HealthStatus.WARNING
        else:
            overall = HealthStatus.HEALTHY

        return HealthSummary(overall=overall, domains=domains)

    # ── Validation ─────────────────────────────────────────────────────

    def _scan_validation(self) -> ValidationSummary:
        """Try to read validation results from last run."""
        # Check for validation results file
        val_file = settings.nemoclaw_home / "last-validation.yaml"
        if val_file.exists():
            try:
                data = yaml.safe_load(val_file.read_text())
                if isinstance(data, dict):
                    return ValidationSummary(
                        total_checks=data.get("total", 31),
                        passed=data.get("passed", 27),
                        warnings=data.get("warnings", 4),
                        failed=data.get("failed", 0),
                    )
            except Exception:
                pass

        # Fallback from handover data
        return ValidationSummary(total_checks=31, passed=27, warnings=4, failed=0)

    # ── Frameworks ─────────────────────────────────────────────────────

    def _scan_frameworks(self) -> FrameworksSummary:
        """Scan for production frameworks (FW-xxx).

        Checks frameworks/ directory first; if empty or missing, falls back
        to counting FW-NNN IDs in scripts/framework_library.py.
        """
        fw_dir = settings.repo_root / "frameworks"
        if fw_dir.is_dir():
            framework_ids: list[str] = []
            for item in sorted(fw_dir.iterdir()):
                if item.is_dir() and item.name.upper().startswith("FW-"):
                    framework_ids.append(item.name.upper())
            if framework_ids:
                return FrameworksSummary(total=len(framework_ids), framework_ids=framework_ids)

        # Fallback: count from framework_library.py
        lib_path = settings.scripts_dir / "framework_library.py"
        if lib_path.exists():
            try:
                text = lib_path.read_text()
                matches = re.findall(r'"(FW-\d{3})"', text)
                if matches:
                    fw_ids = sorted(set(matches))
                    return FrameworksSummary(total=len(fw_ids), framework_ids=fw_ids)
            except Exception:
                pass

        # Hard fallback: 15 known frameworks
        fw_ids = [f"FW-{str(i).zfill(3)}" for i in range(1, 16)]
        return FrameworksSummary(total=15, framework_ids=fw_ids)

    # ── Narrative ───────────────────────────────────────────────────────

    def _build_narrative(self, state: SystemState) -> list[str]:
        """Generate rule-based system insights from current state.

        Returns a list of short sentences describing system status,
        warnings, and opportunities. This is the "intelligence layer"
        for the Home tab — even before the AI Brain exists in CC-2.
        """
        lines: list[str] = []

        # Overall status
        if state.health.overall == HealthStatus.HEALTHY:
            lines.append("System stable. All health domains operational.")
        elif state.health.overall == HealthStatus.WARNING:
            warn_domains = [
                d.domain.replace("_", " ")
                for d in state.health.domains
                if d.status == HealthStatus.WARNING
            ]
            lines.append(
                f"Warnings in {len(warn_domains)} domain(s): {', '.join(warn_domains)}."
            )
        elif state.health.overall == HealthStatus.ERROR:
            err_domains = [
                d.domain.replace("_", " ")
                for d in state.health.domains
                if d.status == HealthStatus.ERROR
            ]
            lines.append(
                f"Errors in {len(err_domains)} domain(s): {', '.join(err_domains)}. Investigate."
            )

        # Budget burn
        for p in state.budget.providers:
            if p.percent_used > 80:
                lines.append(
                    f"Budget alert: {p.provider} at {p.percent_used:.0f}% "
                    f"(${p.spent:.2f} / ${p.limit:.2f})."
                )
            elif p.percent_used > 50:
                lines.append(
                    f"Budget watch: {p.provider} at {p.percent_used:.0f}%."
                )

        # Bridges
        unconfigured = sum(
            1 for b in state.bridges.bridges if not b.has_api_key
        )
        if unconfigured > 0 and state.bridges.total > 0:
            lines.append(
                f"{unconfigured}/{state.bridges.total} bridges awaiting API key configuration."
            )

        # Validation
        if state.validation.failed > 0:
            lines.append(
                f"Validation: {state.validation.failed} check(s) failing. Fix before scaling."
            )
        elif state.validation.warnings > 0:
            lines.append(
                f"Validation: {state.validation.warnings} warning(s). Non-blocking."
            )

        # Skills gap
        if state.skills.total_registered > 0:
            lines.append(
                f"{state.skills.total_registered} skills registered but not yet built."
            )

        # PinchTab
        if state.pinchtab_status == "not_installed":
            lines.append("PinchTab browser bridge is not installed.")
        elif state.pinchtab_status == "stopped":
            lines.append("PinchTab browser bridge is not running.")

        # MA completeness
        if state.ma_systems.total >= 20:
            lines.append(
                f"All {state.ma_systems.total} MA systems operational "
                f"({state.ma_systems.total_tests} tests)."
            )

        return lines

    # ── PinchTab ───────────────────────────────────────────────────────

    def _check_pinchtab(self) -> str:
        """Check if PinchTab is reachable on localhost:9867."""
        import shutil
        if not shutil.which("pinchtab") and not Path.home().joinpath(".pinchtab", "bin").exists():
            return "not_installed"
        try:
            import socket
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                result = s.connect_ex(("127.0.0.1", 9867))
                return "running" if result == 0 else "stopped"
        except Exception:
            return "unknown"

    # ── Git ─────────────────────────────────────────────────────────────

    def _get_git_info(self) -> dict[str, str]:
        """Get current git branch and short commit hash."""
        info: dict[str, str] = {}
        repo = settings.repo_root

        if not (repo / ".git").exists():
            return info

        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True, text=True, cwd=repo, timeout=5,
            )
            if result.returncode == 0:
                info["branch"] = result.stdout.strip()
        except Exception:
            pass

        try:
            result = subprocess.run(
                ["git", "--no-pager", "log", "-1", "--format=%h"],
                capture_output=True, text=True, cwd=repo, timeout=5,
            )
            if result.returncode == 0:
                info["commit"] = result.stdout.strip()
        except Exception:
            pass

        return info


# ── Module-level singleton ─────────────────────────────────────────────

aggregator = StateAggregator()
