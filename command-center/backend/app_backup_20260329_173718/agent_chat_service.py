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

from app.comms_models import Message, SenderType

logger = logging.getLogger("cc.agent_chat")

# Cost control: GPT-4o-mini for all agent responses
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_MAX_TOKENS = 800
CONTEXT_MESSAGES_LIMIT = 15


class AgentPersona:
    """Represents a loaded agent with its LLM persona."""

    def __init__(self, agent_data: dict[str, Any]) -> None:
        self.id: str = agent_data.get("id", agent_data.get("agent_id", "unknown"))
        self.name: str = agent_data.get("name", agent_data.get("display_name", self.id))
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
            "You cannot approve spending or budget allocation without escalation to the user",
            "You cannot execute skills directly — recommend them for the user to trigger",
            "Stay within your role's authority — don't make promises for other team members",
            "If asked about budget or costs, reference the system's budget tracking data",
            "If a request is outside your expertise, say so and suggest which team member handles it",
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
        # Try config/.env first, then environment
        env_path = Path(__file__).parent / "../../../config/.env"
        if env_path.resolve().exists():
            for line in env_path.resolve().read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    os.environ.setdefault(key.strip(), val.strip())

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
                "name": a.display_name,
                "role": a.role,
                "avatar": a.avatar,
                "lane_id": a.lane_id,
            }
            for a in self._agents.values()
        ]

    async def generate_response(
        self,
        agent_id: str,
        user_message: str,
        context_messages: list[Message] | None = None,
    ) -> str | None:
        """Generate an agent response to a user message."""
        agent = self._agents.get(agent_id)
        if not agent:
            logger.error("Unknown agent: %s", agent_id)
            return None

        if not self._client:
            return f"[{agent.display_name} is offline — no API key configured]"

        # Build conversation history for context
        messages = [{"role": "system", "content": agent.build_system_prompt()}]

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
                max_tokens=DEFAULT_MAX_TOKENS,
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
                max_tokens=20,
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
