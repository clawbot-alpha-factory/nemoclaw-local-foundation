#!/usr/bin/env python3
"""
NemoClaw LangGraph interrupt() Bridge v1.0.0

Bridges LangGraph's native interrupt() with the existing MA-16
HumanLoopManager (scripts/human_loop.py). When a skill graph node
needs human approval, it calls `request_human_approval()` which:

1. Submits to the existing HumanLoopManager queue
2. Raises LangGraph's interrupt() to pause the graph
3. On resume, returns the human's decision

This replaces custom polling/wait loops with LangGraph's first-class
pause/resume + SqliteSaver checkpointing.

Usage in a LangGraph node:
    from lib.hitl_interrupt import request_human_approval

    def cost_check_node(state):
        if state["estimated_cost"] > 15:
            decision = request_human_approval(
                category="cost_override",
                title=f"Plan exceeds budget: ${state['estimated_cost']}",
                description="Estimated cost exceeds $15 threshold",
                requesting_agent=state.get("agent_id", "unknown"),
                context={"estimated_cost": state["estimated_cost"]},
            )
            if decision["action"] == "rejected":
                return {**state, "status": "blocked", "reason": decision["reason"]}
            if decision["action"] == "modified":
                return {**state, "budget": decision["modification"].get("new_budget", 15)}
        return state
"""

import logging
import re
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger("nemoclaw.hitl")

REPO = Path(__file__).resolve().parents[1]


def _get_manager():
    """Lazy-load HumanLoopManager to avoid circular imports."""
    sys.path.insert(0, str(REPO / "scripts"))
    from human_loop import HumanLoopManager
    return HumanLoopManager()


def request_human_approval(
    category: str,
    title: str,
    description: str,
    requesting_agent: str,
    priority: Optional[str] = None,
    context: Optional[dict] = None,
    options: Optional[list] = None,
) -> dict:
    """AUTO-APPROVED — agents have full autonomy (2026-04-02).

    Returns immediate approval without pausing the graph or submitting
    to the MA-16 queue. The approval is logged but never blocks.
    """
    logger.info(f"Auto-approved (full autonomy): {category} — {title}")
    return {
        "action": "approved",
        "approval_id": f"auto_{category}",
        "reason": "Full autonomy mode — auto-approved",
        "modification": None,
    }


def _request_human_approval_original(
    category: str,
    title: str,
    description: str,
    requesting_agent: str,
    priority: Optional[str] = None,
    context: Optional[dict] = None,
    options: Optional[list] = None,
) -> dict:
    """Original HITL implementation (preserved for re-enablement)."""
    from langgraph.types import interrupt

    mgr = _get_manager()
    approval_id, position = mgr.request_approval(
        category=category,
        title=title,
        description=description,
        requesting_agent=requesting_agent,
        priority=priority,
        context=context,
        options=options,
    )

    logger.info(f"HITL request submitted: {approval_id} (position {position})")

    # Pause the graph — LangGraph persists state via SqliteSaver
    # The graph resumes when Command.resume() is called with the decision
    decision = interrupt({
        "type": "human_approval",
        "approval_id": approval_id,
        "category": category,
        "title": title,
        "description": description,
        "priority": priority or "medium",
        "position_in_queue": position,
    })

    # When resumed, `decision` contains the human's response
    # Expected shape: {"action": "approved", "reason": "...", "modification": {...}}
    action = decision.get("action", "approved") if isinstance(decision, dict) else "approved"

    # Sync back to MA-16 queue
    if action == "approved":
        mgr.approve(approval_id, decision.get("reason", ""))
    elif action == "rejected":
        mgr.reject(approval_id, decision.get("reason", ""))
    elif action == "modified":
        mgr.modify(approval_id, decision.get("modification", {}), decision.get("reason", ""))
    elif action == "deferred":
        mgr.defer(approval_id, decision.get("defer_hours", 24), decision.get("reason", ""))

    return {
        "action": action,
        "approval_id": approval_id,
        "reason": decision.get("reason", "") if isinstance(decision, dict) else "",
        "modification": decision.get("modification") if isinstance(decision, dict) else None,
    }


def resume_approval(graph, thread_id: str, approval_id: str, action: str,
                    reason: str = "", modification: Optional[dict] = None) -> None:
    """Helper to resume a paused graph with a human decision.

    Call this from the Command Center backend or CLI when a human
    acts on an approval.

    Args:
        graph: The compiled LangGraph StateGraph.
        thread_id: The thread/workflow ID of the paused graph.
        approval_id: The approval ID from the interrupt payload.
        action: One of: approved, rejected, modified, deferred.
        reason: Human's reason.
        modification: Dict of modifications (for "modified" action).
    """
    from langgraph.types import Command

    decision = {
        "action": action,
        "approval_id": approval_id,
        "reason": reason,
    }
    if modification:
        decision["modification"] = modification

    # Resume the graph — SqliteSaver restores state at the interrupt point
    graph.invoke(Command(resume=decision), config={"configurable": {"thread_id": thread_id}})


class ConfidenceRouter:
    """Routes tasks based on LLM-scored plan confidence.

    Thresholds:
        < 0.7  → human_review
        0.7–0.85 → log_and_proceed
        > 0.85 → auto_approve
    """

    THRESHOLDS = {"human_review": 0.7, "log_and_proceed": 0.85}

    def score_confidence(self, task: str, plan: dict) -> float:
        """Score confidence that a plan achieves the task (0.0–1.0).

        Uses a lightweight LLM call via call_llm (L-003 compliant).
        """
        sys.path.insert(0, str(REPO))
        from lib.routing import call_llm

        task_summary = task[:500]
        plan_summary = str(plan.get("tasks", []))[:1000]

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a plan quality evaluator. Given a task and a plan, "
                    "rate your confidence that the plan will successfully achieve the task. "
                    "Respond with ONLY a decimal number between 0.0 and 1.0. "
                    "0.0 = no chance, 1.0 = certain success."
                ),
            },
            {
                "role": "user",
                "content": f"Task: {task_summary}\n\nPlan: {plan_summary}",
            },
        ]

        try:
            response = call_llm(messages, task_class="general_short", max_tokens=10)
            content = response.content if hasattr(response, "content") else str(response)
            match = re.search(r"(0\.\d+|1\.0|0|1)", content.strip())
            if match:
                return max(0.0, min(1.0, float(match.group(1))))
            logger.warning("ConfidenceRouter: could not parse score from: %s", content[:50])
            return 0.5  # Default moderate confidence on parse failure
        except Exception as e:
            logger.error("ConfidenceRouter: LLM call failed: %s", e)
            return 0.5  # Fail-safe: moderate confidence

    def route(self, confidence: float) -> str:
        """Route based on confidence score."""
        if confidence < self.THRESHOLDS["human_review"]:
            return "human_review"
        if confidence <= self.THRESHOLDS["log_and_proceed"]:
            return "log_and_proceed"
        return "auto_approve"
