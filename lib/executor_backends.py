"""
NemoClaw Executor Backends — Pluggable execution abstraction.

Unified ABC for subprocess, Claude Code CLI, and Codex CLI execution.
Each backend wraps a specific invocation pattern behind a common interface.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

logger = logging.getLogger("nemoclaw.executor_backends")

REPO = Path(__file__).resolve().parent.parent


class ExecutionBackend(ABC):
    """Abstract base for all execution backends."""

    name: str = "base"

    @abstractmethod
    async def execute(
        self,
        prompt: str,
        workdir: str | Path,
        model: str = "",
        max_turns: int = 10,
        timeout: int = 300,
    ) -> dict[str, Any]:
        """Run a prompt and return {success, output, error, cost}."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if the backend is available."""

    def get_cost_estimate(self, prompt_tokens: int = 0) -> float:
        """Rough cost estimate in USD. Override per backend."""
        return 0.0


# ── SubprocessBackend (skill-runner.py) ─────────────────────────────────────


class SubprocessBackend(ExecutionBackend):
    """Wraps the existing skill-runner.py subprocess pattern."""

    name = "subprocess"

    def __init__(
        self,
        python_path: str | Path | None = None,
        skill_runner_path: str | Path | None = None,
        repo_root: str | Path | None = None,
    ):
        self.repo_root = Path(repo_root) if repo_root else REPO
        self.python = Path(python_path) if python_path else self.repo_root / ".venv313" / "bin" / "python3"
        self.skill_runner = (
            Path(skill_runner_path) if skill_runner_path
            else self.repo_root / "skills" / "skill-runner.py"
        )

    async def execute(
        self,
        prompt: str,
        workdir: str | Path,
        model: str = "",
        max_turns: int = 10,
        timeout: int = 900,
    ) -> dict[str, Any]:
        """Execute a skill via skill-runner.py.

        prompt format: "skill_id key1=val1 key2=val2" or just skill_id.
        """
        parts = prompt.strip().split()
        skill_id = parts[0]
        cmd = [str(self.python), str(self.skill_runner), "--skill", skill_id]

        # Parse key=value inputs from prompt
        for part in parts[1:]:
            if "=" in part:
                k, v = part.split("=", 1)
                cmd.extend(["--input", k, v])

        env = {**os.environ, "PYTHONPATH": str(self.repo_root)}

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(workdir),
                env=env,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")

            if proc.returncode == 0:
                return {"success": True, "output": stdout_str, "error": None, "cost": 0.0}
            return {
                "success": False,
                "output": stdout_str,
                "error": stderr_str[:500] or stdout_str[:500] or f"Exit code {proc.returncode}",
                "cost": 0.0,
            }
        except asyncio.TimeoutError:
            return {"success": False, "output": "", "error": f"Timed out after {timeout}s", "cost": 0.0}
        except Exception as e:
            return {"success": False, "output": "", "error": str(e), "cost": 0.0}

    async def health_check(self) -> bool:
        return self.python.exists() and self.skill_runner.exists()

    def get_cost_estimate(self, prompt_tokens: int = 0) -> float:
        # skill-runner cost depends on the LLM alias routed at runtime
        return prompt_tokens * 0.000003  # ~$3/1M tokens average


# ── ClaudeCodeBackend ───────────────────────────────────────────────────────


class ClaudeCodeBackend(ExecutionBackend):
    """Wraps Claude Code CLI (`claude`) as an execution backend."""

    name = "claude_code"

    async def execute(
        self,
        prompt: str,
        workdir: str | Path,
        model: str = "sonnet",
        max_turns: int = 10,
        timeout: int = 300,
    ) -> dict[str, Any]:
        cmd = [
            "claude",
            "-p", prompt,
            "--output-format", "json",
            "--max-turns", str(max_turns),
            "--model", model,
            "--permission-mode", "acceptEdits",
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(workdir),
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")

            if proc.returncode == 0:
                # Parse JSON output from claude CLI
                try:
                    parsed = json.loads(stdout_str)
                    cost = parsed.get("cost_usd", 0.0)
                except (json.JSONDecodeError, TypeError):
                    parsed = None
                    cost = 0.0
                return {
                    "success": True,
                    "output": parsed.get("result", stdout_str) if parsed else stdout_str,
                    "error": None,
                    "cost": cost,
                }
            return {
                "success": False,
                "output": stdout_str,
                "error": stderr_str[:500] or f"Exit code {proc.returncode}",
                "cost": 0.0,
            }
        except asyncio.TimeoutError:
            return {"success": False, "output": "", "error": f"Timed out after {timeout}s", "cost": 0.0}
        except Exception as e:
            return {"success": False, "output": "", "error": str(e), "cost": 0.0}

    async def health_check(self) -> bool:
        return shutil.which("claude") is not None

    def get_cost_estimate(self, prompt_tokens: int = 0) -> float:
        return prompt_tokens * 0.000015  # Opus-tier pricing


# ── CodexBackend ────────────────────────────────────────────────────────────


class CodexBackend(ExecutionBackend):
    """Wraps Codex CLI (`codex`) as an execution backend."""

    name = "codex"

    async def execute(
        self,
        prompt: str,
        workdir: str | Path,
        model: str = "o4-mini",
        max_turns: int = 10,
        timeout: int = 300,
    ) -> dict[str, Any]:
        cmd = [
            "codex",
            "exec", prompt,
            "--model", model,
            "--full-auto",
            "--path", str(workdir),
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(workdir),
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")

            if proc.returncode == 0:
                return {"success": True, "output": stdout_str, "error": None, "cost": 0.0}
            return {
                "success": False,
                "output": stdout_str,
                "error": stderr_str[:500] or f"Exit code {proc.returncode}",
                "cost": 0.0,
            }
        except asyncio.TimeoutError:
            return {"success": False, "output": "", "error": f"Timed out after {timeout}s", "cost": 0.0}
        except Exception as e:
            return {"success": False, "output": "", "error": str(e), "cost": 0.0}

    async def health_check(self) -> bool:
        return shutil.which("codex") is not None

    def get_cost_estimate(self, prompt_tokens: int = 0) -> float:
        return prompt_tokens * 0.000001  # o4-mini pricing


# ── Backend Registry Helper ─────────────────────────────────────────────────


BACKEND_MAP: dict[str, type[ExecutionBackend]] = {
    "subprocess": SubprocessBackend,
    "claude_code": ClaudeCodeBackend,
    "codex": CodexBackend,
}


def get_backend(name: str, **kwargs) -> ExecutionBackend:
    """Factory: get a backend instance by name."""
    cls = BACKEND_MAP.get(name)
    if not cls:
        raise ValueError(f"Unknown backend: {name}. Available: {list(BACKEND_MAP.keys())}")
    return cls(**kwargs)
