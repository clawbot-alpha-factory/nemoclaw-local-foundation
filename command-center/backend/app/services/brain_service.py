"""
NemoClaw Command Center — AI Brain Service
LLM-powered strategic intelligence layer for system analysis and chat.

Reads routing-config.yaml to resolve provider/model, loads API key from
environment or config/.env, and provides async methods for:
  - User question answering (with conversation history)
  - Auto-insight generation (strategic system analysis)

Design constraints:
  - Brain chat is NOT part of SystemState (separate message stream)
  - All LLM calls wrapped in try/catch — brain failure never crashes dashboard
  - Budget-aware: reads budget-config.yaml to check spend limits
  - Session-only history (not persisted across restarts)
"""

import os
import yaml
import json
import logging
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("cc.brain")


class BrainService:
    """LLM integration service for the AI Brain sidebar."""

    def __init__(self, project_root: str, routing_alias: str = "balanced"):
        self.project_root = Path(project_root)
        self.routing_alias = routing_alias
        self._provider: Optional[str] = None
        self._model: Optional[str] = None
        self._api_key: Optional[str] = None
        self._client = None
        self._conversation_history: list[dict] = []
        self._last_insight: Optional[dict] = None
        self._available: bool = False

        self._resolve_routing()
        self._load_api_key()
        self._init_client()

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def _resolve_routing(self):
        """Read routing-config.yaml to resolve provider and model for alias."""
        candidates = [
            self.project_root / "config" / "routing-config.yaml",
            self.project_root / "config" / "routing" / "routing-config.yaml",
        ]

        for path in candidates:
            if path.exists():
                try:
                    with open(path) as f:
                        config = yaml.safe_load(f)

                    # Navigate flexible config structures
                    aliases = config
                    for key in ("routing", "aliases"):
                        if isinstance(aliases, dict) and key in aliases:
                            aliases = aliases[key]

                    # Also check 'providers' key (routing-config.yaml v4.0 format)
                    if isinstance(aliases, dict) and "providers" in aliases:
                        aliases = aliases["providers"]

                    if isinstance(aliases, dict) and self.routing_alias in aliases:
                        alias_cfg = aliases[self.routing_alias]
                        self._provider = alias_cfg.get("provider", "openai")
                        self._model = alias_cfg.get("model", "")
                        logger.info(
                            f"Brain routing: {self.routing_alias} → "
                            f"{self._provider}/{self._model} (from {path.name})"
                        )
                        return
                except Exception as e:
                    logger.warning(f"Failed to parse routing config {path}: {e}")

        # Fallback: resolve from routing config via lib.routing
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
            from lib.routing import resolve_alias
            self._provider, self._model, _ = resolve_alias("general_short")
        except Exception:
            self._provider = "openai"
            self._model = ""
        logger.info(f"Brain routing: fallback → {self._provider}/{self._model}")

    def _load_api_key(self):
        """Load API key from environment or config/.env."""
        env_map = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "google": "GOOGLE_API_KEY",
        }
        env_var = env_map.get(self._provider, "ANTHROPIC_API_KEY")

        # 1. Environment variable
        self._api_key = os.environ.get(env_var)

        # 2. config/.env file
        if not self._api_key:
            env_file = self.project_root / "config" / ".env"
            if env_file.exists():
                try:
                    for line in env_file.read_text().splitlines():
                        line = line.strip()
                        if line.startswith(f"{env_var}="):
                            val = line.split("=", 1)[1].strip().strip("\"'")
                            if val and not val.startswith("your-") and val != "":
                                self._api_key = val
                                break
                except Exception as e:
                    logger.warning(f"Failed to read .env: {e}")

        if self._api_key:
            masked = self._api_key[:8] + "..." + self._api_key[-4:]
            logger.info(f"Brain API key loaded for {self._provider}: {masked}")
        else:
            logger.warning(
                f"No API key found for {self._provider} ({env_var}) — "
                f"Brain will be unavailable. Set {env_var} in config/.env"
            )

    def _init_client(self):
        """Initialize the appropriate API client."""
        if not self._api_key:
            self._available = False
            return

        try:
            if self._provider == "anthropic":
                import anthropic
                self._client = anthropic.Anthropic(api_key=self._api_key)
                self._available = True
            elif self._provider == "openai":
                import openai
                self._client = openai.OpenAI(api_key=self._api_key)
                self._available = True
            elif self._provider == "google":
                import google.generativeai as genai
                genai.configure(api_key=self._api_key)
                self._client = genai
                self._available = True
            else:
                logger.warning(f"Unsupported provider: {self._provider}")
                self._available = False
        except ImportError as e:
            logger.warning(f"Provider SDK not installed: {e}")
            self._available = False
        except Exception as e:
            logger.error(f"Failed to initialize LLM client: {e}")
            self._available = False

        if self._available:
            logger.info(f"Brain online: {self._provider}/{self._model}")

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def provider_info(self) -> dict:
        return {
            "provider": self._provider or "none",
            "model": self._model or "none",
            "alias": self.routing_alias,
            "available": self._available,
        }

    # ------------------------------------------------------------------
    # System prompt construction
    # ------------------------------------------------------------------

    def _build_system_prompt(self, system_state: dict) -> str:
        """Build context-rich system prompt from current SystemState."""
        skills = system_state.get("skills", {})
        agents = system_state.get("agents", {})
        ma = system_state.get("ma_systems", {})
        bridges = system_state.get("bridges", {})
        budget = system_state.get("budget", {})
        health = system_state.get("health", {})
        validation = system_state.get("validation", {})
        narrative = system_state.get("narrative", [])
        git_info = system_state.get("git_info", {})
        frameworks = system_state.get("frameworks", {})

        # Extract skill details
        skill_items = skills.get("items", [])
        skill_families = set()
        for s in skill_items:
            fam = s.get("family", "")
            if fam:
                skill_families.add(fam)

        # Extract bridge details
        bridge_items = bridges.get("items", [])
        bridge_lines = []
        for b in bridge_items:
            name = b.get("name", b.get("id", "?"))
            status = b.get("status", "unknown")
            tests = b.get("test_count", 0)
            bridge_lines.append(f"  - {name}: {status}, {tests} tests")

        # Extract budget details
        budget_providers = budget.get("providers", [])
        budget_lines = []
        for p in budget_providers:
            prov = p.get("provider", p.get("name", "?"))
            spent = p.get("spent", p.get("current_spend", 0))
            limit = p.get("limit", p.get("monthly_limit", 30))
            pct = (spent / limit * 100) if limit > 0 else 0
            budget_lines.append(f"  - {prov}: ${spent:.2f} / ${limit:.2f} ({pct:.0f}%)")

        # Health domains
        health_domains = health.get("domains", health.get("items", []))
        health_lines = []
        for d in health_domains:
            name = d.get("name", d.get("domain", "?"))
            status = d.get("status", "unknown")
            msg = d.get("message", "")
            health_lines.append(f"  - {name}: {status}" + (f" — {msg}" if msg else ""))

        # Narrative
        narrative_lines = "\n".join(f"  - {n}" for n in narrative) if narrative else "  (none)"

        return f"""You are the NemoClaw AI Brain — a strategic intelligence layer embedded in the NemoClaw Command Center.

You have real-time access to the complete system state of a local AI skill execution platform running on MacBook M1.

## SYSTEM STATE SNAPSHOT

### Skills ({len(skill_items)} built, {skills.get('registered_count', 0)} registered awaiting build)
Families: {', '.join(sorted(skill_families)) or 'unknown'}
Built skills: {', '.join(s.get('id', '?') for s in skill_items[:15])}{'...' if len(skill_items) > 15 else ''}

### Agents: {agents.get('total', len(agents.get('items', [])))}
{', '.join(a.get('name', a.get('id', '?')) for a in agents.get('items', []))}

### Multi-Agent Systems: {ma.get('total', 0)} systems, {ma.get('total_tests', 0)} total tests

### Production Frameworks: {frameworks.get('total', 0)}

### Bridges (External Integrations)
{chr(10).join(bridge_lines) if bridge_lines else '  (none)'}

### Budget
{chr(10).join(budget_lines) if budget_lines else '  (not configured)'}

### Health Domains
{chr(10).join(health_lines) if health_lines else '  (none)'}

### Validation
Passed: {validation.get('passed', 0)}, Warnings: {validation.get('warnings', 0)}, Failed: {validation.get('failed', 0)}

### Current Alerts (System Narrative)
{narrative_lines}

### Git
Branch: {git_info.get('branch', 'unknown')}, Commit: {git_info.get('last_commit_short', git_info.get('last_commit', 'unknown'))}

## YOUR ROLE
1. Analyze system state and identify strategic priorities
2. Detect anomalies, risks, under-utilization, and opportunities
3. Provide concise, actionable recommendations
4. Answer questions about system capabilities, status, and architecture
5. Flag budget concerns when any provider exceeds 70%

## GUIDELINES
- Be concise and strategic. No filler.
- Reference specific numbers, skill IDs, agent names, and bridge statuses.
- When all bridges are mocked, note the integration gap and recommend prioritization.
- Track the gap between built and registered skills — registered skills represent growth capacity.
- Consider the MacBook M1 16GB hardware constraints in recommendations.
- Format insights as short bullet points for the sidebar display."""

    # ------------------------------------------------------------------
    # Core API methods
    # ------------------------------------------------------------------

    async def analyze(self, prompt: str, context: str = "general") -> str:
        """Analyze a prompt using LLM. Used by TaskWorkflowService for workflow phases.

        Args:
            prompt: The full prompt to send to the LLM
            context: Context hint (workflow_brainstorm, workflow_plan, workflow_validate)

        Returns:
            Raw LLM response text
        """
        if not self.is_available:
            raise RuntimeError("BrainService not available — no LLM provider configured")

        system_prompt = f"You are NemoClaw's AI brain. Context: {context}. Provide detailed, structured, actionable output."
        messages = [{"role": "user", "content": prompt}]
        return await self._call_llm(system_prompt, messages)

    async def ask(self, question: str, system_state: dict) -> dict:
        """Handle a user question with full system state context."""
        if not self._available:
            return {
                "role": "assistant",
                "content": (
                    "AI Brain is offline. To enable it:\n"
                    "1. Add your API key to config/.env\n"
                    "2. Restart the backend\n\n"
                    f"Expected variable: {self._get_env_var_name()}"
                ),
                "timestamp": datetime.now().isoformat(),
                "type": "error",
            }

        system_prompt = self._build_system_prompt(system_state)

        self._conversation_history.append({"role": "user", "content": question})

        # Keep conversation manageable (last 20 messages)
        if len(self._conversation_history) > 20:
            self._conversation_history = self._conversation_history[-20:]

        try:
            response_text = await self._call_llm(system_prompt, self._conversation_history)

            self._conversation_history.append({"role": "assistant", "content": response_text})

            return {
                "role": "assistant",
                "content": response_text,
                "timestamp": datetime.now().isoformat(),
                "type": "response",
            }
        except Exception as e:
            logger.error(f"Brain ask failed: {e}", exc_info=True)
            error_msg = str(e)
            if "authentication" in error_msg.lower() or "api key" in error_msg.lower():
                error_msg = "API key is invalid or expired. Check config/.env"
            return {
                "role": "assistant",
                "content": f"Brain error: {error_msg}",
                "timestamp": datetime.now().isoformat(),
                "type": "error",
            }

    async def generate_insight(self, system_state: dict) -> dict:
        """Generate strategic auto-insight from current system state."""
        if not self._available:
            return {
                "content": "AI Brain offline — configure API key to enable",
                "timestamp": datetime.now().isoformat(),
                "type": "insight",
                "available": False,
            }

        system_prompt = self._build_system_prompt(system_state)

        insight_messages = [
            {
                "role": "user",
                "content": (
                    "Generate a strategic briefing of the current system state. "
                    "Provide 3-5 bullet points covering:\n"
                    "1. Most critical priority right now\n"
                    "2. Any risks or anomalies detected\n"
                    "3. Resource utilization assessment\n"
                    "4. Recommended next action\n"
                    "5. (Optional) An opportunity or efficiency gain\n\n"
                    "Keep each point to 1-2 sentences. Be specific with numbers."
                ),
            }
        ]

        try:
            response_text = await self._call_llm(system_prompt, insight_messages)

            self._last_insight = {
                "content": response_text,
                "timestamp": datetime.now().isoformat(),
                "type": "insight",
                "available": True,
            }
            return self._last_insight

        except Exception as e:
            logger.error(f"Brain insight generation failed: {e}", exc_info=True)
            return {
                "content": f"Insight generation failed: {str(e)}",
                "timestamp": datetime.now().isoformat(),
                "type": "insight",
                "available": False,
            }

    # ------------------------------------------------------------------
    # LLM provider dispatch
    # ------------------------------------------------------------------

    async def _call_llm(self, system_prompt: str, messages: list[dict]) -> str:
        """Route LLM call to the configured provider."""
        if self._provider == "anthropic":
            return await self._call_anthropic(system_prompt, messages)
        elif self._provider == "openai":
            return await self._call_openai(system_prompt, messages)
        elif self._provider == "google":
            return await self._call_google(system_prompt, messages)
        else:
            raise ValueError(f"Unsupported provider: {self._provider}")

    async def _call_anthropic(self, system_prompt: str, messages: list[dict]) -> str:
        response = await asyncio.to_thread(
            self._client.messages.create,
            model=self._model,
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": m["role"], "content": m["content"]} for m in messages],
        )
        return response.content[0].text

    async def _call_openai(self, system_prompt: str, messages: list[dict]) -> str:
        all_msgs = [{"role": "system", "content": system_prompt}] + [
            {"role": m["role"], "content": m["content"]} for m in messages
        ]
        response = await asyncio.to_thread(
            self._client.chat.completions.create,
            model=self._model,
            max_completion_tokens=1024,
            messages=all_msgs,
        )
        return response.choices[0].message.content

    async def _call_google(self, system_prompt: str, messages: list[dict]) -> str:
        model = self._client.GenerativeModel(self._model)
        full_prompt = system_prompt + "\n\n"
        for msg in messages:
            label = "User" if msg["role"] == "user" else "Assistant"
            full_prompt += f"{label}: {msg['content']}\n\n"
        response = await asyncio.to_thread(model.generate_content, full_prompt)
        return response.text

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_env_var_name(self) -> str:
        env_map = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "google": "GOOGLE_API_KEY",
        }
        return env_map.get(self._provider, "ANTHROPIC_API_KEY")

    def clear_history(self):
        """Clear conversation history."""
        self._conversation_history = []
        logger.info("Brain conversation history cleared")

    def get_history(self) -> list[dict]:
        """Get conversation history (copy)."""
        return [
            {**msg, "timestamp": datetime.now().isoformat()}
            for msg in self._conversation_history
        ]
