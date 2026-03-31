"""
NemoClaw Execution Engine — Autonomous Scheduler (E-12)

Time-based job scheduler. All jobs auto-fire. No human trigger needed.
Every job wrapped in try/except → FailureRecoveryService.

NEW FILE: command-center/backend/app/services/autonomous_scheduler_service.py
"""
from __future__ import annotations
import asyncio, logging, time
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine

logger = logging.getLogger("cc.scheduler_auto")


class ScheduledJob:
    def __init__(self, name: str, interval_seconds: int, fn: Callable,
                 description: str = ""):
        self.name = name
        self.interval_seconds = interval_seconds
        self.fn = fn
        self.description = description
        self.last_run: str | None = None
        self.run_count: int = 0
        self.last_error: str | None = None
        self.enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name, "interval_seconds": self.interval_seconds,
            "description": self.description, "last_run": self.last_run,
            "run_count": self.run_count, "last_error": self.last_error,
            "enabled": self.enabled,
            "interval_human": self._human_interval(),
        }

    def _human_interval(self) -> str:
        s = self.interval_seconds
        if s < 60:
            return f"{s}s"
        if s < 3600:
            return f"{s // 60}m"
        if s < 86400:
            return f"{s // 3600}h"
        return f"{s // 86400}d"


class AutonomousSchedulerService:
    """
    Registers and runs scheduled jobs as asyncio background tasks.
    All jobs have try/except with failure recovery.
    """

    def __init__(self, failure_recovery=None):
        self.failure_recovery = failure_recovery
        self._jobs: dict[str, ScheduledJob] = {}
        self._tasks: list[asyncio.Task] = []
        self._running = False
        logger.info("AutonomousSchedulerService initialized")

    def register(self, name: str, interval_seconds: int, fn: Callable,
                 description: str = "") -> None:
        self._jobs[name] = ScheduledJob(name, interval_seconds, fn, description)

    async def start_all(self) -> None:
        self._running = True
        for name, job in self._jobs.items():
            if job.enabled:
                task = asyncio.create_task(self._run_job(job))
                self._tasks.append(task)
        logger.info("Scheduler started %d jobs", len(self._tasks))

    async def stop_all(self) -> None:
        self._running = False
        for task in self._tasks:
            task.cancel()
        self._tasks = []
        logger.info("Scheduler stopped")

    async def _run_job(self, job: ScheduledJob) -> None:
        # Initial delay to stagger jobs
        await asyncio.sleep(min(job.interval_seconds, 30))
        while self._running and job.enabled:
            try:
                result = job.fn()
                if asyncio.iscoroutine(result):
                    await result
                job.last_run = datetime.now(timezone.utc).isoformat()
                job.run_count += 1
                job.last_error = None
            except asyncio.CancelledError:
                break
            except Exception as e:
                job.last_error = str(e)[:200]
                logger.warning("Scheduled job '%s' failed: %s", job.name, e)
                if self.failure_recovery:
                    try:
                        await self.failure_recovery.handle_failure(
                            f"scheduler:{job.name}", str(e), "operations_lead"
                        )
                    except Exception:
                        pass
            await asyncio.sleep(job.interval_seconds)

    async def trigger_job(self, name: str) -> dict[str, Any]:
        job = self._jobs.get(name)
        if not job:
            return {"error": f"Job '{name}' not found"}
        try:
            result = job.fn()
            if asyncio.iscoroutine(result):
                await result
            job.last_run = datetime.now(timezone.utc).isoformat()
            job.run_count += 1
            return {"status": "triggered", "job": name}
        except Exception as e:
            return {"error": str(e)[:200]}

    def get_jobs(self) -> list[dict[str, Any]]:
        return [j.to_dict() for j in self._jobs.values()]

    def get_stats(self) -> dict[str, Any]:
        return {
            "total_jobs": len(self._jobs),
            "running": self._running,
            "jobs": self.get_jobs(),
        }
