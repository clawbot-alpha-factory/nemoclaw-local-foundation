"""
NemoClaw Execution Engine — ContextService (E-4b)

Cross-agent context (#32): before skill invocation, gathers all prior
outputs from same trace_id/workflow and injects relevant context.

NEW FILE: command-center/backend/app/services/context_service.py
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("cc.context")


class ContextService:
    """
    Gathers prior outputs from a workflow/trace to inject into skill calls.

    Before a skill runs, the context service:
      1. Finds all completed executions with same trace_id
      2. Collects their output paths and key results
      3. Returns a context dict that can inform the next skill
    """

    def __init__(self, execution_service=None, workspace_service=None):
        self.execution_service = execution_service
        self.workspace_service = workspace_service
        logger.info("ContextService initialized")

    def gather_context(self, trace_id: str, workflow_id: str = "") -> dict[str, Any]:
        """Gather all prior context for a trace/workflow."""
        context: dict[str, Any] = {
            "trace_id": trace_id,
            "prior_outputs": [],
            "workspace_data": {},
        }

        # Gather prior execution outputs — only completed, recent, matching trace
        if self.execution_service:
            history = self.execution_service.get_history(limit=50)
            matching = []
            for ex in history:
                ex_dict = ex.model_dump() if hasattr(ex, "model_dump") else ex
                ex_trace = ex_dict.get("trace", {})
                if (
                    ex_trace.get("trace_id") == trace_id
                    and ex_dict.get("status") == "completed"
                    and ex_dict.get("output_path")
                ):
                    matching.append({
                        "skill_id": ex_dict.get("skill_id"),
                        "output_path": ex_dict.get("output_path"),
                        "status": ex_dict.get("status"),
                        "agent_id": ex_dict.get("agent_id"),
                        "completed_at": ex_dict.get("completed_at"),
                    })
            # Sort by recency, limit to 10
            matching.sort(key=lambda x: x.get("completed_at", ""), reverse=True)
            context["prior_outputs"] = matching[:10]

        # Gather workspace data
        if self.workspace_service and workflow_id:
            context["workspace_data"] = self.workspace_service.read_all(workflow_id)

        return context

    def get_prior_output_paths(self, trace_id: str) -> list[str]:
        """Get just the output file paths from prior executions."""
        context = self.gather_context(trace_id)
        return [
            o["output_path"]
            for o in context["prior_outputs"]
            if o.get("output_path")
        ]
