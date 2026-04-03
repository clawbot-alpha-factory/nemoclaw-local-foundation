"""
NemoClaw Session Pool — Concurrency-limited backend session management.

Provides semaphore-gated access to execution backends so we never
exceed max concurrent processes per backend type.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from lib.executor_backends import ExecutionBackend, BACKEND_MAP, get_backend

logger = logging.getLogger("nemoclaw.session_pool")


@dataclass
class SessionHandle:
    """A leased session from the pool."""
    backend: ExecutionBackend
    backend_type: str
    acquired_at: float = field(default_factory=time.time)
    _pool: SessionPool | None = field(default=None, repr=False)

    async def execute(self, prompt: str, workdir: str, **kwargs) -> dict[str, Any]:
        """Convenience: execute via the leased backend."""
        return await self.backend.execute(prompt, workdir, **kwargs)

    async def release(self):
        """Return this session to the pool."""
        if self._pool:
            self._pool._release(self)


class SessionPool:
    """
    Manages concurrent access to execution backends.

    Each backend type gets its own semaphore to cap parallelism.
    """

    def __init__(
        self,
        max_claude: int = 3,
        max_codex: int = 3,
        max_subprocess: int = 6,
        idle_timeout: int = 300,
    ):
        self.idle_timeout = idle_timeout
        self._limits = {
            "claude_code": max_claude,
            "codex": max_codex,
            "subprocess": max_subprocess,
        }
        self._semaphores: dict[str, asyncio.Semaphore] = {}
        self._active: list[SessionHandle] = []
        self._backends: dict[str, ExecutionBackend] = {}

    def _get_semaphore(self, backend_type: str) -> asyncio.Semaphore:
        """Lazily create semaphores (must be created in event loop context)."""
        if backend_type not in self._semaphores:
            limit = self._limits.get(backend_type, 3)
            self._semaphores[backend_type] = asyncio.Semaphore(limit)
        return self._semaphores[backend_type]

    def _get_backend(self, backend_type: str) -> ExecutionBackend:
        """Get or create a backend instance."""
        if backend_type not in self._backends:
            self._backends[backend_type] = get_backend(backend_type)
        return self._backends[backend_type]

    async def acquire(self, backend_type: str, **backend_kwargs) -> SessionHandle:
        """Acquire a session handle, blocking until a slot is available."""
        sem = self._get_semaphore(backend_type)
        await sem.acquire()

        backend = self._get_backend(backend_type) if not backend_kwargs else get_backend(backend_type, **backend_kwargs)
        handle = SessionHandle(
            backend=backend,
            backend_type=backend_type,
            _pool=self,
        )
        self._active.append(handle)
        logger.debug("Acquired %s session (active=%d)", backend_type, len(self._active))
        return handle

    def _release(self, handle: SessionHandle):
        """Release a session back to the pool."""
        if handle in self._active:
            self._active.remove(handle)
        sem = self._semaphores.get(handle.backend_type)
        if sem:
            sem.release()
        logger.debug("Released %s session (active=%d)", handle.backend_type, len(self._active))

    async def health_check_all(self) -> dict[str, bool]:
        """Check health of all known backend types."""
        results = {}
        for name in BACKEND_MAP:
            try:
                backend = self._get_backend(name)
                results[name] = await backend.health_check()
            except Exception:
                results[name] = False
        return results

    def active_count(self, backend_type: str | None = None) -> int:
        """Count active sessions, optionally filtered by type."""
        if backend_type:
            return sum(1 for h in self._active if h.backend_type == backend_type)
        return len(self._active)

    def cleanup_idle(self):
        """Remove sessions that have been idle beyond timeout."""
        now = time.time()
        stale = [h for h in self._active if (now - h.acquired_at) > self.idle_timeout]
        for handle in stale:
            logger.warning("Force-releasing idle %s session (age=%.0fs)", handle.backend_type, now - handle.acquired_at)
            self._release(handle)
        return len(stale)
