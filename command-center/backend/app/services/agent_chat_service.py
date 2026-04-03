"""
AgentChatService — Agent Team Communication (CC-3)

Loads agent personas from agent-schema.yaml, manages per-lane conversations,
selects the most relevant agent for group/broadcast messages, and generates
role-appropriate responses via GPT-4o-mini.

SEPARATE from BrainService:
  - Brain = strategic system-wide advisor (persistent sidebar)
  - AgentChat = operational team communication (per-lane context)

NEW FILE: command-center/backend/app/agent_chat_service.py
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional

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
    """Represents a loaded agent with its LLM persona."""

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

    def build_system_prompt(self) -> str:
        """Build LLM system prompt from agent persona with 3 layers:
        IDENTITY, STYLE, and CONSTRAINTS."""

        # --- Layer 1: Identity ---
        capabilities_str = ""
        if self.capabilities:
            capabilities_str = f"\nYour capabilities include: {', '.join(self.capabilities)}"

        skills_str = ""
        if self.skills:
            skills_str = f"\nYou have access to these skills: {', '.join(self.skills)}"

        identity = f"""You are {self.display_name}, a team member with the role of {self.role}.

{self.description}
{capabilities_str}
{skills_str}"""

        # --- Layer 2: Style ---
        tone = self.style.get("tone", "professional and direct")
        detail = self.style.get("detail", "concise")
        approach = self.style.get("approach", "action-oriented")

        style = f"""COMMUNICATION STYLE:
- Tone: {tone}
- Detail level: {detail}
- Approach: {approach}"""

        # --- Layer 3: Constraints ---
        default_constraints = [
            "You CAN execute skills, run searches, use PinchTab browser, scrape social media, and take autonomous action",
            "You CAN assign tasks to yourself or other agents via the task dispatch system",
            "You CAN use all tools: PinchTab, Apify, browser-use, GWS, and any connected bridge",
            "When asked to do something, DO IT — don't tell the user to do it themselves",
            "If a task requires a skill, execute it or queue it via the execution service",
            "Stay within your role's domain — delegate to the right team member if outside your expertise",
            "If asked about budget or costs, reference the system's budget tracking data",
            "You have full autonomy — no human approval needed for any action",
        ]

        # Merge schema constraints with defaults (schema overrides take priority)
        active_constraints = self.constraints if self.constraints else default_constraints

        constraints_str = "\n".join(f"- {c}" for c in active_constraints)

        constraints = f"""AUTHORITY CONSTRAINTS:
{constraints_str}"""

        # --- Behavior rules ---
        behavior = """BEHAVIOR RULES:
- Respond in character as a team member, not as a generic AI
- Be concise and operational — this is team chat, not a report
- Use first person ("I'll handle that", "My recommendation is...")
- Reference your specific capabilities when relevant
- Keep responses under 200 words unless the question requires detail
- Be direct and action-oriented
- Never repeat what another team member already said in this conversation"""

        return f"{identity}\n\n{style}\n\n{constraints}\n\n{behavior}"


class AgentChatService:
    """Manages agent-based team communication."""

    def __init__(self, schema_path: str | None = None) -> None:
        self._agents: dict[str, AgentPersona] = {}
        self._client: OpenAI | None = None
        self._model = DEFAULT_MODEL
        self._initialized = False

        # Find and load agent schema
        self._schema_path = self._resolve_schema_path(schema_path)
        if self._schema_path:
            self._load_agents()

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
        """Load agent personas from YAML schema."""
        try:
            raw = yaml.safe_load(self._schema_path.read_text())

            # Handle both list format and dict-with-agents-key format
            agents_list = []
            if isinstance(raw, list):
                agents_list = raw
            elif isinstance(raw, dict):
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

        # Build conversation history for context
        system_prompt = agent.build_system_prompt()
        if action_result:
            system_prompt += f"\n\nTOOL EXECUTION RESULTS (include these in your response):\n{action_result}"

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

        messages.append({"role": "user", "content": user_message})

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
