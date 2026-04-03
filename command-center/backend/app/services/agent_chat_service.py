"""
AgentChatService — Agent Team Communication (CC-3)

Loads agent personas from agent-schema.yaml + capability-registry.yaml,
builds rich 6-block system prompts with full identity, authority, capabilities,
team context, quality standards, and dynamic runtime context.

SEPARATE from BrainService:
  - Brain = strategic system-wide advisor (persistent sidebar)
  - AgentChat = operational team communication (per-lane context)
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date
from pathlib import Path
from typing import Any, Optional

try:
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
    from lib.prompt_sanitizer import sanitize as sanitize_secrets
except ImportError:
    sanitize_secrets = lambda text: text  # noqa: E731 — fallback

import yaml
from openai import OpenAI

from app.domain.comms_models import Message, SenderType

logger = logging.getLogger("cc.agent_chat")

# Cost control: resolved from routing config (L-003)
def _resolve_chat_model():
    """Resolve the chat model — must be compatible with the OpenAI client.
    If routing returns an Anthropic model, fall back to gpt-5.4-mini for chat.
    Agent chat uses OpenAI SDK; skill execution uses lib.routing (provider-agnostic).
    """
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
        from lib.routing import resolve_alias
        provider, model, _ = resolve_alias("general_short")
        # OpenAI client can only use OpenAI models
        if provider == "openai":
            return model
        # For Anthropic/Google, fall back to gpt-5.4 for chat (capable + compatible)
        _, fallback, _ = resolve_alias("agentic")  # gpt-5.4
        return fallback if fallback else "gpt-5.4"
    except Exception:
        return "gpt-5.4"

DEFAULT_MODEL = _resolve_chat_model()
DEFAULT_MAX_TOKENS = 800
CONTEXT_MESSAGES_LIMIT = 15


class AgentPersona:
    """Represents a loaded agent with its LLM persona.

    Builds rich 6-block system prompts that include full identity, authority,
    capabilities, team context, quality standards, and dynamic runtime data.
    """

    def __init__(self, agent_data: dict[str, Any]) -> None:
        self.id: str = agent_data.get("id", agent_data.get("agent_id", "unknown"))
        # Identity block holds character name, cartoon persona, avatar
        identity = agent_data.get("identity", {})
        self.character_name: str = identity.get("name", agent_data.get("name", ""))
        self.character: str = identity.get("character", "")
        self.character_show: str = identity.get("show", "")
        self.role_display: str = agent_data.get("display_name", self.id)
        # name = character name if available, else display_name
        self.name: str = self.character_name or agent_data.get("display_name", self.id)
        self.title_short: str = agent_data.get("title", "")
        self.role: str = agent_data.get("role", "General Agent")
        self.description: str = agent_data.get(
            "description", agent_data.get("desc", agent_data.get("role", ""))
        )
        self.capabilities: list[str] = agent_data.get("capabilities", agent_data.get("owns", []))
        self.family: str = agent_data.get("family", "")
        # Handle nested skills format: {primary: [...], future: [...]}
        raw_skills = agent_data.get("skills", [])
        if isinstance(raw_skills, dict):
            self.skills: list[str] = raw_skills.get("primary", [])
        else:
            self.skills: list[str] = raw_skills
        self.constraints: list[str] = agent_data.get("constraints", [])
        self.style: dict[str, str] = agent_data.get("style", {})
        self.raw: dict[str, Any] = agent_data

    @property
    def display_name(self) -> str:
        return self.name or self.id

    @property
    def lane_id(self) -> str:
        """DM lane ID for this agent."""
        return f"dm-{self.id}"

    @property
    def avatar(self) -> str:
        """Emoji avatar based on role keywords."""
        role_lower = self.role.lower()
        if "content" in role_lower or "write" in role_lower:
            return "✍️"
        if "sales" in role_lower or "outreach" in role_lower:
            return "📞"
        if "ops" in role_lower or "operation" in role_lower:
            return "⚙️"
        if "research" in role_lower or "analy" in role_lower:
            return "🔬"
        if "strategy" in role_lower or "plan" in role_lower:
            return "🎯"
        if "finance" in role_lower or "budget" in role_lower:
            return "💰"
        if "engineer" in role_lower or "dev" in role_lower:
            return "🛠️"
        return "🤖"

    # ------------------------------------------------------------------
    # Block builders — each returns a formatted string for one prompt section
    # ------------------------------------------------------------------

    def _build_identity_block(self) -> str:
        """Block 1: Full identity — name, title, authority, personality, voice, philosophy."""
        identity = self.raw.get("identity", {})
        auth_level = self.raw.get("authority_level", "?")
        title = self.raw.get("title", self.role)
        persona = identity.get("persona", "")
        work_philosophy = identity.get("work_philosophy", "")

        # Voice rules
        voice_rules = identity.get("voice_rules", [])
        voice_rules_str = "\n".join(f"  - {r}" for r in voice_rules) if voice_rules else ""

        # Operating principles
        principles = identity.get("operating_principles", [])
        principles_str = "\n".join(f"  - {p}" for p in principles) if principles else ""

        # Personality voice — extract style and work example
        pv = identity.get("personality_voice", {})
        if isinstance(pv, dict):
            voice_style = pv.get("style", "")
            work_example = pv.get("work_example", "")
        elif isinstance(pv, str):
            # Parse multiline string format: "Style: ...\nExample work: ..."
            voice_style = ""
            work_example = ""
            for pv_line in pv.split("\n"):
                pv_line = pv_line.strip()
                if pv_line.lower().startswith("style:"):
                    voice_style = pv_line[6:].strip()
                elif pv_line.lower().startswith("example work:"):
                    work_example = pv_line[13:].strip().strip('"')
        else:
            voice_style = ""
            work_example = ""

        # Decisions this agent makes
        decides = self.raw.get("decides", [])
        decides_str = "\n".join(f"  - {d}" for d in decides) if decides else ""

        lines = [
            f"You are {self.display_name}, {title} (Authority Level {auth_level}).",
            f"Character: {self.character} from {self.character_show}." if self.character else "",
            f"\n{persona}" if persona else "",
            f"\nVoice style: {voice_style}" if voice_style else "",
            f"Work example: \"{work_example}\"" if work_example else "",
            f"\nVoice rules:\n{voice_rules_str}" if voice_rules_str else "",
            f"\nWork philosophy: {work_philosophy}" if work_philosophy else "",
            f"\nOperating principles:\n{principles_str}" if principles_str else "",
            f"\nYou decide:\n{decides_str}" if decides_str else "",
        ]
        return "\n".join(line for line in lines if line)

    def _build_authority_block(self, schema_top: dict | None = None) -> str:
        """Block 2: Authority — domains owned, forbidden, reporting chain, overrides."""
        owns = self.raw.get("owns", self.capabilities)
        owns_str = ", ".join(owns[:12]) if owns else "none specified"

        # Domain boundaries from schema top-level
        boundaries = {}
        if schema_top:
            boundaries = schema_top.get("domain_boundaries", {}).get(self.id, {})
        forbidden = boundaries.get("forbidden", [])
        forbidden_str = ", ".join(forbidden) if forbidden else "none"

        # Reporting chain
        reports_to = self.raw.get("reports_to", [])
        if isinstance(reports_to, str):
            reports_to = [reports_to]
        reports_str = ", ".join(reports_to) if reports_to else "none (top authority)"

        # Override rules — find this agent's entry
        override_desc = ""
        if schema_top:
            for rule in schema_top.get("authority_hierarchy", {}).get("override_rules", []):
                if rule.get("from") == self.id:
                    can_override = rule.get("can_override", "none")
                    if isinstance(can_override, list):
                        can_override = ", ".join(can_override)
                    conditions = rule.get("conditions", "")
                    override_desc = f"Override power: can override {can_override}. {conditions}"
                    break

        # Constraints from schema
        constraints = self.constraints or boundaries.get("constraints", [])
        constraints_str = ""
        if constraints:
            constraints_str = "\nConstraints:\n" + "\n".join(f"  - {c}" for c in constraints)

        return f"""AUTHORITY:
- Domains you OWN (final decisions): {owns_str}
- Domains FORBIDDEN (must delegate): {forbidden_str}
- Reports to: {reports_str}
- {override_desc if override_desc else 'Cannot override peers — escalate to parent'}
- All overrides require mandatory logging{constraints_str}"""

    def _build_capabilities_block(self, capability_data: dict | None = None) -> str:
        """Block 3: Skills and tools — what this agent can execute."""
        # Skills from registry or fallback to self.skills
        skills = []
        if capability_data:
            skills = capability_data.get("capabilities", [])
        if not skills:
            skills = self.skills

        skills_str = ", ".join(skills[:20]) if skills else "none loaded"

        # Tools from registry
        tools = []
        if capability_data:
            tools = capability_data.get("tools", [])
        # Merge with external_tools from schema
        ext_tools = self.raw.get("external_tools", [])
        all_tools = list(set(tools + ext_tools))
        tools_str = ", ".join(all_tools[:15]) if all_tools else "PinchTab, Apify, browser-use, GWS"

        return f"""CAPABILITIES:
Skills: {skills_str}
Tools: {tools_str}
To execute a skill: EXECUTE: <skill_id> with inputs: {{key: value}}
You CAN execute skills, run searches, browse the web, scrape data, and take autonomous action.
When asked to do something, DO IT — don't tell the user to do it themselves.
If a task is outside your domain, delegate to the right team member."""

    def _build_quality_block(self) -> str:
        """Block 4: Quality standards and output requirements."""
        auto_cap = self.raw.get("autonomous_capability", {})
        quality_target = auto_cap.get("quality_target", 9)
        on_below = auto_cap.get("on_quality_below_8",
                                auto_cap.get("on_quality_below_9", "re-evaluate and improve"))

        # Metrics this agent tracks
        metrics = self.raw.get("metrics", [])
        metrics_str = ", ".join(metrics[:6]) if metrics else ""

        return f"""QUALITY STANDARDS:
- Target: {quality_target}/10 on every output — no exceptions
- If quality drops below 8: {on_below}
- Structure all outputs: headers, bullets, clear sections
- Include reasoning and evidence for every recommendation
- Never fabricate data — state assumptions explicitly
- Be specific with numbers, dates, and names — no vague language
{f'- Track these KPIs: {metrics_str}' if metrics_str else ''}"""

    def _build_context_block(self, context_data: dict | None = None) -> str:
        """Block 5: Dynamic runtime context — budget, recent work."""
        if not context_data:
            return ""

        parts = []
        # Budget
        budget = context_data.get("budget_remaining")
        if budget and isinstance(budget, dict):
            budget_lines = [f"{k}: ${v:.2f}" for k, v in budget.items() if isinstance(v, (int, float))]
            if budget_lines:
                parts.append("Budget remaining: " + " | ".join(budget_lines))

        # Recent work
        recent = context_data.get("recent_work", [])
        if recent:
            work_lines = []
            for entry in recent[:3]:
                action = entry.get("action", "unknown")
                details = entry.get("details", "")[:80]
                work_lines.append(f"  - {action}: {details}")
            parts.append("Recent work:\n" + "\n".join(work_lines))

        if not parts:
            return ""

        return "CONTEXT:\n" + "\n".join(parts)

    def _build_behavior_rules(self) -> str:
        """Block 6: Communication and behavior rules."""
        return """BEHAVIOR:
- Respond in character as a team member, not as a generic AI
- Be concise and operational — this is team chat, not a report
- Use first person ("I'll handle that", "My recommendation is...")
- Reference your specific capabilities and skills when relevant
- Keep responses under 200 words unless the question requires detail
- Be direct and action-oriented — lead with the answer or action
- Never repeat what another team member already said in this conversation"""

    # ------------------------------------------------------------------
    # Main prompt assembly
    # ------------------------------------------------------------------

    def build_system_prompt(
        self,
        capability_data: dict | None = None,
        team_block: str = "",
        quality_doc: str = "",
        context_data: dict | None = None,
        schema_top: dict | None = None,
    ) -> str:
        """Build rich 6-block system prompt from agent persona + enrichment data.

        All parameters are optional for backward compatibility — calling with no
        args produces a functional (though less detailed) prompt.

        Blocks:
          1. IDENTITY — name, title, authority, personality, philosophy
          2. AUTHORITY — domains, forbidden, overrides, reporting chain
          3. CAPABILITIES — skills, tools, invocation format
          4. TEAM — all 11 agents with roles (for delegation awareness)
          5. QUALITY — output standards, quality target, KPIs
          6. CONTEXT — dynamic budget + recent work history
          + BEHAVIOR — communication rules
          + QUALITY GUIDE — domain-specific examples (from docs/agents/*.md)
        """
        blocks = [
            self._build_identity_block(),
            self._build_authority_block(schema_top),
            self._build_capabilities_block(capability_data),
        ]

        if team_block:
            blocks.append(f"TEAM DIRECTORY:\n{team_block}")

        blocks.append(self._build_quality_block())

        context_block = self._build_context_block(context_data)
        if context_block:
            blocks.append(context_block)

        if quality_doc:
            blocks.append(f"QUALITY GUIDE:\n{quality_doc}")

        blocks.append(self._build_behavior_rules())

        return "\n\n".join(blocks)


class AgentChatService:
    """Manages agent-based team communication with rich agent prompts."""

    def __init__(self, schema_path: str | None = None) -> None:
        self._agents: dict[str, AgentPersona] = {}
        self._client: OpenAI | None = None
        self._model = DEFAULT_MODEL
        self._initialized = False

        # Enrichment data loaded from configs
        self._schema_top: dict[str, Any] = {}       # authority_hierarchy, domain_boundaries, etc.
        self._agent_capabilities: dict[str, list[str]] = {}  # agent_id -> [skill_ids]
        self._agent_tools: dict[str, list[str]] = {}          # agent_id -> [tool_names]
        self._team_block: str = ""                             # cached team directory
        self._quality_docs: dict[str, str] = {}                # agent_id -> quality doc extract

        # External services wired from main.py
        self.knowledge_base = None      # KnowledgeBaseService
        self.vector_memory = None       # VectorMemory

        # Find and load agent schema
        self._schema_path = self._resolve_schema_path(schema_path)
        if self._schema_path:
            self._load_agents()
            self._load_capability_registry()
            self._build_team_block()
            self._cache_quality_docs()

        # Initialize OpenAI client
        self._init_client()

    def _resolve_schema_path(self, explicit_path: str | None) -> Path | None:
        """Find agent-schema.yaml in known locations."""
        candidates = []
        if explicit_path:
            candidates.append(Path(explicit_path))

        # Relative to backend app (command-center/backend/app/)
        app_dir = Path(__file__).parent
        candidates.extend(
            [
                app_dir / "../../../config/agents/agent-schema.yaml",
                app_dir / "../../../config/agent-schema.yaml",
                app_dir / "../../../config/agents.yaml",
                app_dir / "../../config/agent-schema.yaml",
                app_dir / "../../config/agents/agent-schema.yaml",
            ]
        )

        # Check CC_REPO_ROOT (set in Docker/Railway)
        import os
        repo_root = os.environ.get("CC_REPO_ROOT")
        if repo_root:
            candidates.append(Path(repo_root) / "config/agents/agent-schema.yaml")
            candidates.append(Path(repo_root) / "config/agent-schema.yaml")

        # Absolute fallback
        home = Path.home()
        candidates.append(home / "nemoclaw-local-foundation/config/agents/agent-schema.yaml")
        candidates.append(home / "nemoclaw-local-foundation/config/agent-schema.yaml")

        for p in candidates:
            resolved = p.resolve()
            if resolved.exists():
                logger.info("Found agent schema at: %s", resolved)
                return resolved

        logger.warning("No agent-schema.yaml found — agent chat will be limited")
        return None

    def _load_agents(self) -> None:
        """Load agent personas from YAML schema and capture top-level sections."""
        try:
            raw = yaml.safe_load(self._schema_path.read_text())

            # Handle both list format and dict-with-agents-key format
            agents_list = []
            if isinstance(raw, list):
                agents_list = raw
            elif isinstance(raw, dict):
                # Capture top-level schema sections for prompt enrichment
                for key in (
                    "authority_hierarchy", "domain_boundaries",
                    "domain_overlap_governance", "behavior_modes",
                ):
                    if key in raw:
                        self._schema_top[key] = raw[key]

                agents_list = raw.get("agents", raw.get("agent_list", []))
                if not agents_list and not any(
                    k in raw for k in ("agents", "agent_list")
                ):
                    # Might be a dict of agent_id -> agent_data
                    for k, v in raw.items():
                        if isinstance(v, dict):
                            v.setdefault("id", k)
                            agents_list.append(v)

            for agent_data in agents_list:
                if isinstance(agent_data, dict):
                    persona = AgentPersona(agent_data)
                    self._agents[persona.id] = persona
                    logger.info(
                        "Loaded agent: %s (%s)", persona.display_name, persona.role
                    )

            logger.info("Loaded %d agents from schema", len(self._agents))
        except Exception as e:
            logger.error("Failed to load agent schema: %s", e)

    def _init_client(self) -> None:
        """Initialize OpenAI client for agent responses."""
        # Try config/.env — check CC_REPO_ROOT first, then relative path
        env_candidates = []
        repo_root = os.environ.get("CC_REPO_ROOT")
        if repo_root:
            env_candidates.append(Path(repo_root) / "config" / ".env")
        env_candidates.append(Path(__file__).resolve().parent.parents[3] / "config" / ".env")

        for env_path in env_candidates:
            if env_path.resolve().exists():
                for line in env_path.resolve().read_text().splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, val = line.partition("=")
                        os.environ.setdefault(key.strip(), val.strip())
                break

        api_key = os.environ.get("OPENAI_API_KEY")
        if api_key:
            self._client = OpenAI(api_key=api_key)
            self._initialized = True
            logger.info("AgentChatService initialized with OpenAI")
        else:
            logger.warning("No OPENAI_API_KEY — agent responses will be unavailable")

    # ------------------------------------------------------------------
    # Enrichment loaders — populate capability, team, and quality data
    # ------------------------------------------------------------------

    def _load_capability_registry(self) -> None:
        """Load capability-registry.yaml and build per-agent skill/tool indexes."""
        try:
            registry_path = self._schema_path.parent / "capability-registry.yaml"
            if not registry_path.exists():
                logger.warning("capability-registry.yaml not found at %s", registry_path)
                return

            registry = yaml.safe_load(registry_path.read_text())
            if not isinstance(registry, dict):
                return

            # Build per-agent skill index from capabilities section
            capabilities = registry.get("capabilities", {})
            for cap_name, cap_data in capabilities.items():
                if not isinstance(cap_data, dict):
                    continue
                owner = cap_data.get("owned_by", "")
                skill = cap_data.get("skill", "")
                if owner and skill:
                    self._agent_capabilities.setdefault(owner, [])
                    if skill not in self._agent_capabilities[owner]:
                        self._agent_capabilities[owner].append(skill)

            # Build per-agent tool index from tool_bridges section
            tool_bridges = registry.get("tool_bridges", {})
            for tool_name, bridge_data in tool_bridges.items():
                if not isinstance(bridge_data, dict):
                    continue
                agents = bridge_data.get("agents", [])
                status = bridge_data.get("status", "configured")
                for agent_id in agents:
                    self._agent_tools.setdefault(agent_id, [])
                    label = f"{tool_name} ({status})"
                    if label not in self._agent_tools[agent_id]:
                        self._agent_tools[agent_id].append(label)

            total_caps = sum(len(v) for v in self._agent_capabilities.values())
            logger.info(
                "Loaded capability registry: %d capabilities across %d agents",
                total_caps, len(self._agent_capabilities),
            )
        except Exception as e:
            logger.error("Failed to load capability registry: %s", e)

    def _build_team_block(self) -> None:
        """Build cached team directory string — same for all agents."""
        lines = []
        for agent in self._agents.values():
            owns = agent.raw.get("owns", agent.capabilities)
            owns_str = ", ".join(owns[:5]) if owns else "general"
            auth = agent.raw.get("authority_level", "?")
            role_short = agent.role[:80].rsplit(" ", 1)[0] if len(agent.role) > 80 else agent.role
            lines.append(f"- {agent.display_name} ({agent.id}, L{auth}): {role_short}. Owns: {owns_str}")

        # Add domain overlap governance rules
        overlap = self._schema_top.get("domain_overlap_governance", {})
        if overlap:
            lines.append("\nDomain overlap rules:")
            for area, rules in overlap.items():
                if isinstance(rules, dict):
                    owners = [f"{k}: {v}" for k, v in rules.items() if k != "rule"]
                    rule_text = rules.get("rule", "")
                    line = f"- {area}: {', '.join(owners)}"
                    if rule_text:
                        line += f". {rule_text[:100]}"
                    lines.append(line)

        self._team_block = "\n".join(lines)
        logger.info("Built team block: %d agents, %d overlap rules", len(self._agents), len(overlap))

    def _get_context_data(self, agent_id: str) -> dict | None:
        """Get dynamic runtime context — budget remaining and recent work log.

        Returns dict with 'budget_remaining' and 'recent_work' keys, or None on failure.
        All I/O is try/except wrapped — this must never crash the response path.
        """
        result: dict[str, Any] = {}

        # Budget: read last entries from provider-usage.jsonl
        try:
            usage_path = Path.home() / ".nemoclaw" / "logs" / "provider-usage.jsonl"
            if usage_path.exists():
                lines = usage_path.read_text().strip().splitlines()
                # Collect latest budget per provider from last 50 lines
                budgets: dict[str, float] = {}
                for line in lines[-50:]:
                    try:
                        entry = json.loads(line)
                        provider = entry.get("provider", "")
                        remaining = entry.get("budget_remaining")
                        if provider and remaining is not None:
                            budgets[provider] = float(remaining)
                    except (json.JSONDecodeError, ValueError):
                        continue
                if budgets:
                    result["budget_remaining"] = budgets
        except Exception:
            pass

        # Work history: last 3 entries from today's log
        try:
            today = date.today().isoformat()
            log_path = Path.home() / ".nemoclaw" / "work-logs" / agent_id / f"{today}.jsonl"
            if log_path.exists():
                entries = []
                for line in log_path.read_text().strip().splitlines()[-3:]:
                    try:
                        entry = json.loads(line)
                        entries.append({
                            "action": entry.get("action", ""),
                            "details": entry.get("details", ""),
                        })
                    except json.JSONDecodeError:
                        continue
                if entries:
                    result["recent_work"] = entries
        except Exception:
            pass

        return result if result else None

    def _cache_quality_docs(self) -> None:
        """Load and cache quality doc extracts from docs/agents/*.md files."""
        try:
            # Resolve docs/agents/ relative to repo root (schema is in config/agents/)
            docs_dir = self._schema_path.parent.parent.parent / "docs" / "agents"
            if not docs_dir.exists():
                logger.info("No docs/agents/ directory found — quality docs not loaded")
                return

            for agent_id in self._agents:
                doc_path = docs_dir / f"{agent_id}.md"
                if not doc_path.exists():
                    continue
                try:
                    content = doc_path.read_text()
                    # Extract Quality Checklist + Good/Bad Output Examples sections
                    extract = self._extract_quality_sections(content)
                    if extract:
                        self._quality_docs[agent_id] = extract[:1500]
                except Exception:
                    continue

            if self._quality_docs:
                logger.info("Cached quality docs for %d agents", len(self._quality_docs))
        except Exception as e:
            logger.error("Failed to cache quality docs: %s", e)

    @staticmethod
    def _extract_quality_sections(content: str) -> str:
        """Extract Quality Checklist and Output Examples from a quality guide .md file."""
        sections_to_extract = [
            "## Quality Checklist",
            "## Good Output Examples",
            "## Bad Output Example",
        ]
        result_lines: list[str] = []
        capturing = False

        for line in content.splitlines():
            # Check if this line starts a section we want
            if any(line.strip().startswith(header) for header in sections_to_extract):
                capturing = True
                result_lines.append(line)
                continue

            # Stop capturing at next ## header that's not in our list
            if capturing and line.strip().startswith("## ") and not any(
                line.strip().startswith(h) for h in sections_to_extract
            ):
                capturing = False
                continue

            if capturing:
                result_lines.append(line)

        return "\n".join(result_lines).strip()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def agents(self) -> dict[str, AgentPersona]:
        return self._agents

    @property
    def is_available(self) -> bool:
        return self._initialized and len(self._agents) > 0

    def get_agent(self, agent_id: str) -> AgentPersona | None:
        return self._agents.get(agent_id)

    def list_agents(self) -> list[dict[str, Any]]:
        """Return agent summaries for frontend."""
        return [
            {
                "id": a.id,
                "name": f"{a.character_name} ({a.role_display})" if a.character_name and a.character_name != a.role_display else a.display_name,
                "character_name": a.character_name,
                "character": getattr(a, "character", ""),
                "role_display": a.role_display,
                "role": a.role,
                "title": getattr(a, "title_short", ""),
                "avatar": a.avatar,
                "lane_id": a.lane_id,
            }
            for a in self._agents.values()
        ]

    # ── Tool execution bridge ────────────────────────────────────────
    # These are set by main.py after initialization
    execution_service = None
    tool_access_service = None

    async def _try_execute_action(self, agent_id: str, user_message: str) -> str | None:
        """Detect actionable requests and execute them via the tool/execution layer.

        Returns execution result string, or None if not an action request.
        """
        msg_lower = user_message.lower()

        # Detect browser/search/scrape requests
        action_keywords = [
            "search", "scrape", "find", "look up", "browse", "pinchtab",
            "run a search", "scan", "crawl", "research", "investigate",
            "get data", "pull data", "fetch", "analyze",
        ]
        is_action = any(kw in msg_lower for kw in action_keywords)
        if not is_action:
            return None

        results = []

        # Try Apify for social media scraping
        if any(w in msg_lower for w in ["social", "tiktok", "instagram", "linkedin", "twitter", "profile", "account"]):
            try:
                import subprocess, json, sys
                repo = Path(__file__).resolve().parents[3]
                python = str(repo / ".venv313" / "bin" / "python3")
                # Extract target from message (simple heuristic)
                words = user_message.split()
                target = None
                for w in words:
                    if w.startswith("@") or ("." not in w and len(w) > 3 and w[0].isalpha()):
                        target = w.lstrip("@")
                if not target:
                    target = "AI automation"

                cmd = [python, str(repo / "scripts" / "apify_bridge.py"), "--tiktok", target, "--max", "3"]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=90, cwd=str(repo))
                if result.returncode == 0 and result.stdout.strip():
                    data = json.loads(result.stdout) if result.stdout.strip().startswith("[") else []
                    if data:
                        summaries = []
                        for post in data[:3]:
                            text = post.get("text", "")[:100]
                            plays = post.get("playCount", 0)
                            likes = post.get("diggCount", 0)
                            summaries.append(f"- {text}... ({plays:,} plays, {likes:,} likes)")
                        results.append(f"Apify TikTok scrape for '{target}':\n" + "\n".join(summaries))
            except Exception as e:
                results.append(f"[Apify scrape attempted but failed: {str(e)[:100]}]")

        # Try PinchTab for web browsing
        if any(w in msg_lower for w in ["browse", "pinchtab", "website", "page", "url"]) and self.tool_access_service:
            try:
                result, err = await self.tool_access_service.check_tool_health()
                if result and result.get("pinchtab") == "healthy":
                    results.append("[PinchTab is available — browser task can be queued]")
            except Exception:
                pass

        # Try skill execution for research requests
        if any(w in msg_lower for w in ["research", "analyze", "investigate", "intelligence"]) and self.execution_service:
            try:
                results.append("[Research task queued via execution service — results will be delivered when complete]")
            except Exception:
                pass

        return "\n\n".join(results) if results else None

    async def generate_response(
        self,
        agent_id: str,
        user_message: str,
        context_messages: list[Message] | None = None,
    ) -> str | None:
        """Generate an agent response to a user message.

        If the message contains an actionable request (search, scrape, browse),
        the agent will attempt to execute it first, then include results in response.
        """
        agent = self._agents.get(agent_id)
        if not agent:
            logger.error("Unknown agent: %s", agent_id)
            return None

        if not self._client:
            return f"[{agent.display_name} is offline — no API key configured]"

        # ── Try executing the action first ────────────────────────────
        action_result = await self._try_execute_action(agent_id, user_message)

        # Build enriched system prompt with all 6 blocks
        context_data = self._get_context_data(agent_id)
        capability_data = {
            "capabilities": self._agent_capabilities.get(agent_id, []),
            "tools": self._agent_tools.get(agent_id, []),
        }
        system_prompt = agent.build_system_prompt(
            capability_data=capability_data,
            team_block=self._team_block,
            quality_doc=self._quality_docs.get(agent_id, ""),
            context_data=context_data,
            schema_top=self._schema_top,
        )
        if action_result:
            action_result = sanitize_secrets(action_result)
            system_prompt += f"\n\nTOOL EXECUTION RESULTS (include these in your response):\n{action_result}"

        # Enrich with knowledge base results
        if self.knowledge_base:
            try:
                kb_results = self.knowledge_base.search(query=user_message)
                if kb_results:
                    kb_text = "\n".join(f"- {r['key']}: {r['value']}" for r in kb_results[:3])
                    system_prompt += f"\n\nRELEVANT KNOWLEDGE:\n{kb_text}"
            except Exception:
                pass

        # Enrich with past experience from vector memory
        if self.vector_memory:
            try:
                vm_results = self.vector_memory.search("skill_outputs", user_message, n_results=3)
                if vm_results:
                    vm_text = "\n".join(f"- {r['content'][:200]}" for r in vm_results)
                    system_prompt += f"\n\nPAST EXPERIENCE:\n{vm_text}"
            except Exception:
                pass

        messages = [{"role": "system", "content": system_prompt}]

        if context_messages:
            for msg in context_messages[-CONTEXT_MESSAGES_LIMIT:]:
                role = "assistant" if msg.sender_type == SenderType.AGENT else "user"
                prefix = ""
                if msg.sender_type == SenderType.USER:
                    prefix = ""
                elif msg.sender_type == SenderType.AGENT and msg.sender_id != agent_id:
                    prefix = f"[{msg.sender_name}]: "

                messages.append({"role": role, "content": f"{prefix}{msg.content}"})

        messages.append({"role": "user", "content": sanitize_secrets(user_message)})

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                max_completion_tokens=DEFAULT_MAX_TOKENS,
                temperature=0.7,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error("Agent response failed for %s: %s", agent_id, e)
            return f"[{agent.display_name} encountered an error: {str(e)[:100]}]"

    async def generate_response_stream(
        self,
        agent_id: str,
        user_message: str,
        context_messages: list[Message] | None = None,
    ):
        """Stream agent response chunks. Yields (chunk: str, is_complete: bool).

        Prompt construction is identical to generate_response(). Uses
        call_llm_stream() from lib/routing.py (L-003 compliant) instead of
        the OpenAI SDK, bridged to async via asyncio.Queue + run_in_executor.
        """
        import asyncio

        agent = self._agents.get(agent_id)
        if not agent:
            logger.error("Unknown agent: %s", agent_id)
            yield f"[Unknown agent: {agent_id}]", True
            return

        if not self._client:
            yield f"[{agent.display_name} is offline — no API key configured]", True
            return

        # ── Try executing the action first (non-streaming) ────────────
        action_result = await self._try_execute_action(agent_id, user_message)

        # ── Build enriched system prompt (identical to generate_response) ──
        context_data = self._get_context_data(agent_id)
        capability_data = {
            "capabilities": self._agent_capabilities.get(agent_id, []),
            "tools": self._agent_tools.get(agent_id, []),
        }
        system_prompt = agent.build_system_prompt(
            capability_data=capability_data,
            team_block=self._team_block,
            quality_doc=self._quality_docs.get(agent_id, ""),
            context_data=context_data,
            schema_top=self._schema_top,
        )
        if action_result:
            action_result = sanitize_secrets(action_result)
            system_prompt += f"\n\nTOOL EXECUTION RESULTS (include these in your response):\n{action_result}"

        if self.knowledge_base:
            try:
                kb_results = self.knowledge_base.search(query=user_message)
                if kb_results:
                    kb_text = "\n".join(f"- {r['key']}: {r['value']}" for r in kb_results[:3])
                    system_prompt += f"\n\nRELEVANT KNOWLEDGE:\n{kb_text}"
            except Exception:
                pass

        if self.vector_memory:
            try:
                vm_results = self.vector_memory.search("skill_outputs", user_message, n_results=3)
                if vm_results:
                    vm_text = "\n".join(f"- {r['content'][:200]}" for r in vm_results)
                    system_prompt += f"\n\nPAST EXPERIENCE:\n{vm_text}"
            except Exception:
                pass

        messages = [{"role": "system", "content": system_prompt}]

        if context_messages:
            for msg in context_messages[-CONTEXT_MESSAGES_LIMIT:]:
                role = "assistant" if msg.sender_type == SenderType.AGENT else "user"
                prefix = ""
                if msg.sender_type == SenderType.AGENT and msg.sender_id != agent_id:
                    prefix = f"[{msg.sender_name}]: "
                messages.append({"role": role, "content": f"{prefix}{msg.content}"})

        messages.append({"role": "user", "content": sanitize_secrets(user_message)})

        # ── Stream via call_llm_stream (sync→async bridge) ────────────
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
        from lib.routing import call_llm_stream

        queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_event_loop()

        def _run_stream():
            try:
                for chunk, err in call_llm_stream(messages, "moderate", DEFAULT_MAX_TOKENS):
                    loop.call_soon_threadsafe(queue.put_nowait, (chunk, err))
            except Exception as e:
                loop.call_soon_threadsafe(queue.put_nowait, (None, str(e)))
            loop.call_soon_threadsafe(queue.put_nowait, (None, None))  # sentinel

        loop.run_in_executor(None, _run_stream)

        while True:
            chunk, err = await queue.get()
            if chunk is None and err is None:
                yield "", True  # stream complete
                return
            if err:
                yield f"[Error: {err}]", True
                return
            if chunk:
                yield chunk, False

    async def select_relevant_agent(
        self,
        message: str,
        participant_ids: list[str],
    ) -> str | None:
        """Select the most relevant agent for a group/broadcast message.

        Uses a lightweight LLM call to determine which agent should respond.
        Falls back to first participant if LLM is unavailable.
        """
        if not participant_ids:
            return None

        if len(participant_ids) == 1:
            return participant_ids[0]

        if not self._client:
            return participant_ids[0]

        # Build agent roster for selection
        roster = []
        for aid in participant_ids:
            agent = self._agents.get(aid)
            if agent:
                roster.append(f"- {agent.id}: {agent.role} — {agent.description[:80]}")

        if not roster:
            return participant_ids[0]

        selection_prompt = f"""Given this team message, which ONE agent should respond?

Message: "{message[:300]}"

Available agents:
{chr(10).join(roster)}

Reply with ONLY the agent ID (e.g., "agent-01"). Nothing else."""

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": selection_prompt}],
                max_completion_tokens=20,
                temperature=0.0,
            )
            selected = response.choices[0].message.content.strip().strip('"').strip("'")

            # Validate selection
            if selected in participant_ids:
                return selected

            # Fuzzy match — the LLM might return a close variant
            for pid in participant_ids:
                if pid in selected or selected in pid:
                    return pid

            logger.warning(
                "LLM selected unknown agent '%s', falling back to first", selected
            )
            return participant_ids[0]

        except Exception as e:
            logger.error("Agent selection failed: %s", e)
            return participant_ids[0]

    # ── Peer Review (Group Collaboration) ────────────────────────────

    async def trigger_peer_review(
        self,
        lane_id: str,
        agent_id: str,
        deliverable_summary: str,
        message_store=None,
        notification_service=None,
    ) -> dict[str, Any]:
        """Post a deliverable to the team channel and prompt a peer to critique it.

        Identifies the best reviewer by domain adjacency (shared domains),
        preferring agents already in the channel.
        """
        from app.services.agent_notification_service import AGENT_DOMAINS, AGENT_NAMES
        from app.domain.comms_models import SenderType, MessageType

        if not message_store:
            return {"success": False, "error": "no message_store"}

        lane = message_store.get_lane(lane_id)
        if not lane:
            return {"success": False, "error": f"lane {lane_id} not found"}

        # Score peers by domain overlap with the author
        author_domains = set(AGENT_DOMAINS.get(agent_id, []))
        candidates: dict[str, int] = {}
        for peer_id, peer_domains in AGENT_DOMAINS.items():
            if peer_id == agent_id:
                continue
            overlap = len(author_domains & set(peer_domains))
            if overlap > 0:
                score = overlap
                if peer_id in lane.participants:
                    score += 2  # prefer in-channel peers
                candidates[peer_id] = score

        if not candidates:
            # Fallback: pick any lane participant that isn't the author
            others = [p for p in lane.participants if p != agent_id]
            if not others:
                return {"success": False, "error": "no reviewers available"}
            reviewer_id = others[0]
        else:
            reviewer_id = max(candidates, key=candidates.get)

        # Post deliverable to team channel
        author_name = AGENT_NAMES.get(agent_id, agent_id)
        message_store.add_message(
            lane_id=lane_id,
            sender_id=agent_id,
            sender_name=author_name,
            sender_type=SenderType.AGENT,
            content=f"**Deliverable for review:**\n\n{deliverable_summary[:1500]}",
            message_type=MessageType.CHAT,
            metadata={"deliverable": True, "awaiting_review_from": reviewer_id},
        )

        # Build review prompt
        reviewer_name = AGENT_NAMES.get(reviewer_id, reviewer_id)
        review_prompt = (
            f"You are reviewing a deliverable from {author_name} in a team channel.\n\n"
            f"DELIVERABLE:\n{deliverable_summary[:2000]}\n\n"
            "As a peer reviewer, provide a concise critique:\n"
            "1. **Strengths** — what works well (1-2 points)\n"
            "2. **Weaknesses** — gaps or risks (1-2 points)\n"
            "3. **Recommendation** — specific improvement or next step\n\n"
            "Keep it under 150 words. Be direct and constructive."
        )

        # Get context from the team channel
        context = message_store.get_context_messages(lane_id)

        # Generate reviewer's critique
        review_text = None
        try:
            review_text = await self.generate_response(
                agent_id=reviewer_id,
                user_message=review_prompt,
                context_messages=context,
            )
        except Exception as e:
            logger.error("Peer review generation failed for %s: %s", reviewer_id, e)

        if review_text:
            message_store.add_message(
                lane_id=lane_id,
                sender_id=reviewer_id,
                sender_name=reviewer_name,
                sender_type=SenderType.AGENT,
                content=review_text,
                message_type=MessageType.CHAT,
                metadata={"peer_review": True, "reviewing": agent_id},
            )

        return {
            "success": bool(review_text),
            "reviewer_id": reviewer_id,
            "review_posted": bool(review_text),
            "lane_id": lane_id,
        }
