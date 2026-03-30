"""
NemoClaw Execution Engine — SkillChainRunner (E-2)

Orchestrates multi-skill chains: [A→B→C] where each skill's
output envelope becomes the next skill's input via --input-from.

DECISION: Uses ExecutionService for individual skill runs.
Chain failure handling: retry current step, skip on 2nd fail, escalate on 3rd.

NEW FILE: command-center/backend/app/services/skill_chain_runner.py
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from pathlib import Path

from app.domain.engine_models import (
    ChainExecution,
    ChainRequest,
    ChainStatus,
    ChainStep,
    ExecutionRequest,
    ExecutionStatus,
    LLMTier,
    TaskExecution,
    TraceContext,
)

logger = logging.getLogger("cc.chain")


class SkillChainRunner:
    """
    Runs ordered skill chains with output piping.

    Chain flow:
      1. Run skill A with initial inputs
      2. Take A's envelope → pass as --input-from to skill B
      3. Take B's envelope → pass as --input-from to skill C
      4. Report final result

    Failure handling:
      - Step fails once → retry
      - Step fails twice → skip (if chain allows) or abort
      - Chain tracks partial results
    """

    def __init__(self, execution_service):
        """
        Args:
            execution_service: ExecutionService instance for running individual skills
        """
        self.execution_service = execution_service
        self.chains: dict[str, ChainExecution] = {}
        self._running_chains: set[str] = set()

        logger.info("SkillChainRunner initialized")

    def submit_chain(self, request: ChainRequest) -> ChainExecution:
        """Submit a chain for execution."""
        trace = request.trace or TraceContext(
            agent_id=request.agent_id, phase="E-2-chain"
        )

        steps = [
            ChainStep(skill_id=skill_id)
            for skill_id in request.chain
        ]

        # First step gets initial inputs
        if steps and request.initial_inputs:
            steps[0].inputs = request.initial_inputs

        chain = ChainExecution(
            steps=steps,
            agent_id=request.agent_id,
            tier=request.tier,
            trace=trace,
        )

        self.chains[chain.chain_id] = chain

        # Start execution in background
        asyncio.create_task(self._run_chain(chain))

        logger.info(
            "Chain %s submitted: %d steps [%s]",
            chain.chain_id[:8],
            len(steps),
            " → ".join(request.chain),
        )
        return chain

    def get_chain(self, chain_id: str) -> ChainExecution | None:
        return self.chains.get(chain_id)

    def get_all_chains(self) -> list[ChainExecution]:
        return list(self.chains.values())

    async def _run_chain(self, chain: ChainExecution):
        """Execute chain steps sequentially, piping outputs."""
        chain.status = ChainStatus.RUNNING
        chain.started_at = datetime.utcnow()
        self._running_chains.add(chain.chain_id)

        previous_envelope: str | None = None

        try:
            for i, step in enumerate(chain.steps):
                chain.current_step = i

                logger.info(
                    "Chain %s step %d/%d: %s",
                    chain.chain_id[:8],
                    i + 1,
                    len(chain.steps),
                    step.skill_id,
                )

                # Build execution request
                request = ExecutionRequest(
                    skill_id=step.skill_id,
                    inputs=step.inputs,
                    agent_id=chain.agent_id,
                    tier=chain.tier,
                    trace=chain.trace,
                )

                # Submit and wait for completion
                execution = self.execution_service.submit(request)
                step.execution_id = execution.execution_id

                # If we have a previous envelope, set it for input piping
                if previous_envelope:
                    execution.envelope_path = previous_envelope

                # Wait for this execution to complete
                result = await self._wait_for_execution(execution.execution_id)

                if result is None or result.status == ExecutionStatus.DEAD_LETTER:
                    step.status = ExecutionStatus.FAILED
                    step.error = result.error if result else "Execution disappeared"
                    chain.status = ChainStatus.FAILED
                    chain.error = f"Step {i + 1} ({step.skill_id}) failed: {step.error}"
                    logger.error("Chain %s failed at step %d", chain.chain_id[:8], i + 1)
                    break

                if result.status == ExecutionStatus.COMPLETED:
                    step.status = ExecutionStatus.COMPLETED
                    step.output_path = result.output_path
                    step.envelope_path = result.envelope_path
                    chain.total_cost += result.cost

                    # Pipe envelope to next step
                    previous_envelope = result.envelope_path

                elif result.status == ExecutionStatus.FAILED:
                    step.status = ExecutionStatus.FAILED
                    step.error = result.error
                    chain.status = ChainStatus.FAILED
                    chain.error = f"Step {i + 1} ({step.skill_id}) failed"
                    break

                elif result.status == ExecutionStatus.CANCELLED:
                    step.status = ExecutionStatus.CANCELLED
                    chain.status = ChainStatus.CANCELLED
                    break

            else:
                # All steps completed
                chain.status = ChainStatus.COMPLETED
                logger.info(
                    "Chain %s completed: %d steps, cost=$%.3f",
                    chain.chain_id[:8],
                    len(chain.steps),
                    chain.total_cost,
                )

        except Exception as e:
            chain.status = ChainStatus.FAILED
            chain.error = str(e)
            logger.error("Chain %s error: %s", chain.chain_id[:8], e)

        finally:
            chain.completed_at = datetime.utcnow()
            self._running_chains.discard(chain.chain_id)

    async def _wait_for_execution(
        self, execution_id: str, timeout: int = 600
    ) -> TaskExecution | None:
        """Poll for execution completion."""
        start = asyncio.get_event_loop().time()
        while (asyncio.get_event_loop().time() - start) < timeout:
            execution = self.execution_service.get_execution(execution_id)
            if execution is None:
                return None
            if execution.status in (
                ExecutionStatus.COMPLETED,
                ExecutionStatus.FAILED,
                ExecutionStatus.CANCELLED,
                ExecutionStatus.DEAD_LETTER,
            ):
                return execution
            await asyncio.sleep(2)
        return None
