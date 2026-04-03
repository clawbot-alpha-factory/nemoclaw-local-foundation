"""
Intent Classifier Service

LLM-powered intent classification replacing hardcoded keyword matching.
Uses call_llm_structured via lib/routing.py for validated Pydantic output.

NEW FILE: command-center/backend/app/services/intent_classifier.py
"""

from __future__ import annotations

import asyncio
import logging
import sys
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger("cc.intent_classifier")

# Ensure lib/ is importable
_REPO = Path(__file__).resolve().parents[4]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


class Intent(str, Enum):
    RUN_SKILL = "run_skill"
    CREATE_PROJECT = "create_project"
    RESEARCH = "research"
    DELEGATE = "delegate"
    CREATE_TEAM = "create_team"
    QUERY_KB = "query_kb"
    CHAT = "chat"


class IntentResult(BaseModel):
    """Structured output from the intent classifier."""

    intent: Intent = Field(description="The classified intent")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score 0-1")
    extracted_params: dict[str, Any] = Field(
        default_factory=dict,
        description="Extracted parameters relevant to the intent",
    )


SYSTEM_PROMPT = """You are an intent classifier for a multi-agent AI company.
Classify the user message into EXACTLY ONE intent.

Intents:
- run_skill: User wants a specific skill executed (e.g. "run the SEO keyword researcher", "generate a proposal")
- create_project: User wants a new project created (e.g. "start a new content campaign", "create a project for...")
- research: User wants research or analysis done (e.g. "research competitor pricing", "analyze market trends")
- delegate: User wants to hand off to a specific agent (e.g. "ask Bolt to fix the CI", "have Luna look at revenue")
- create_team: User wants a multi-agent collaboration (e.g. "create a team to build a landing page", "assemble a squad for...")
- query_kb: User wants information from the knowledge base (e.g. "what do we know about...", "find our notes on...")
- chat: Normal conversation, greeting, or unclear intent

For extracted_params, include relevant fields:
- run_skill: {"skill_id": "...", "topic": "..."}
- create_project: {"project_name": "...", "template": "...", "description": "..."}
- research: {"topic": "...", "depth": "quick|standard|deep"}
- delegate: {"agent_id": "...", "task": "..."}
- create_team: {"task_name": "...", "suggested_agents": [...]}
- query_kb: {"query": "..."}
- chat: {}

Agent IDs: executive_operator, strategy_lead, operations_lead, product_architect,
growth_revenue_lead, narrative_content_lead, engineering_lead, sales_outreach_lead,
marketing_campaigns_lead, client_success_lead, social_media_lead"""

FALLBACK = IntentResult(intent=Intent.CHAT, confidence=1.0, extracted_params={})


async def classify_intent(message: str, agent_id: str = "") -> IntentResult:
    """Classify user message intent using LLM.

    Returns IntentResult with intent, confidence, and extracted parameters.
    Falls back to CHAT intent on any error.
    """
    from lib.routing import call_llm_structured

    user_prompt = f"Agent context: {agent_id}\nMessage: {message}"
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    try:
        result, err = await asyncio.to_thread(
            call_llm_structured,
            messages,
            IntentResult,
            "structured_short",
            200,
        )
        if err or not result:
            logger.warning("Intent classification error: %s", err)
            return FALLBACK
        logger.info(
            "Intent classified: %s (%.2f) for: %.60s",
            result.intent.value,
            result.confidence,
            message,
        )
        return result
    except Exception as e:
        logger.error("Intent classification failed: %s", e)
        return FALLBACK
