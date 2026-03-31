"""
NemoClaw Execution Engine — CodeGenerationService (E-7b)

Generates Python/TypeScript code + acceptance tests using Opus.
4 generators: service, router, frontend, test.
Uses existing codebase patterns as few-shot examples.

Fix #1: Always generates acceptance tests with code.
Fix #6: Provides diff context for review.

NEW FILE: command-center/backend/app/services/code_generation_service.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("cc.codegen")


class GenerationJob:
    def __init__(self, task: str, target_files: list[str], context: str = ""):
        self.job_id = str(uuid.uuid4())[:8]
        self.task = task
        self.target_files = target_files
        self.context = context
        self.status = "queued"
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.completed_at: str | None = None
        self.generated_code: dict[str, str] = {}  # filepath → code
        self.generated_tests: dict[str, str] = {}  # filepath → test code
        self.diff_context: dict[str, dict[str, str]] = {}  # filepath → {new, existing}
        self.cost: float = 0.0
        self.error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "task": self.task,
            "target_files": self.target_files,
            "status": self.status,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "files_generated": list(self.generated_code.keys()),
            "tests_generated": list(self.generated_tests.keys()),
            "cost": self.cost,
            "error": self.error,
        }


class CodeGenerationService:
    """
    Generates code + tests using LLM (Opus for generation).

    Always produces:
      1. Implementation code (service/router/frontend)
      2. Acceptance tests for the generated code
      3. Diff context for code review

    Budget cap: $10 per generation cycle.
    """

    BUDGET_CAP_PER_CYCLE = 10.0

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.backend_dir = repo_root / "command-center" / "backend"
        self.jobs: dict[str, GenerationJob] = {}
        self._persist_path = Path.home() / '.nemoclaw' / 'codegen-jobs.json'
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info("CodeGenerationService initialized")

    def _save_jobs(self):
        """Persist job state to disk (survives restart)."""
        try:
            data = {jid: j.to_dict() for jid, j in self.jobs.items()}
            self._persist_path.write_text(json.dumps(data, indent=2, default=str))
        except Exception as e:
            logger.warning("Failed to persist codegen jobs: %s", e)

    def _read_existing_file(self, filepath: str) -> str:
        """Read existing file for diff context."""
        full_path = self.backend_dir / filepath
        if full_path.exists():
            return full_path.read_text()
        return ""

    def _get_codebase_examples(self) -> str:
        """Get existing code patterns as few-shot examples."""
        examples = []
        # Sample existing service
        exec_svc = self.backend_dir / "app" / "services" / "execution_service.py"
        if exec_svc.exists():
            content = exec_svc.read_text()
            examples.append(f"# Example service pattern (execution_service.py):\n{content[:1500]}")

        # Sample existing router
        exec_router = self.backend_dir / "app" / "api" / "routers" / "execution.py"
        if exec_router.exists():
            content = exec_router.read_text()
            examples.append(f"# Example router pattern (execution.py):\n{content[:1000]}")

        return "\n\n".join(examples)

    async def generate(self, task: str, target_files: list[str], context: str = "") -> GenerationJob:
        """Generate code + tests for a task."""
        job = GenerationJob(task=task, target_files=target_files, context=context)
        self.jobs[job.job_id] = job

        logger.info("CodeGen job %s: %s (%d files)", job.job_id, task[:50], len(target_files))
        asyncio.create_task(self._run_generation(job))
        return job

    async def _run_generation(self, job: GenerationJob):
        """Generate code and tests via LLM."""
        job.status = "generating"

        try:
            codebase_examples = self._get_codebase_examples()

            for filepath in job.target_files:
                if job.cost >= self.BUDGET_CAP_PER_CYCLE:
                    job.error = f"Budget cap reached (${job.cost:.2f})"
                    job.status = "failed"
                    return

                existing_code = self._read_existing_file(filepath)

                # Generate implementation
                code = await self._generate_file(
                    task=job.task,
                    filepath=filepath,
                    existing_code=existing_code,
                    codebase_examples=codebase_examples,
                    context=job.context,
                )

                if code:
                    job.generated_code[filepath] = code
                    job.diff_context[filepath] = {
                        "new_code": code,
                        "existing_code": existing_code,
                        "is_new_file": not bool(existing_code),
                    }
                    job.cost += 0.50  # Opus estimate

                    # Generate acceptance test (Fix #1)
                    test_code = await self._generate_test(
                        filepath=filepath,
                        implementation=code,
                        task=job.task,
                    )
                    if test_code:
                        test_path = filepath.replace(".py", "_test.py").replace("services/", "tests/")
                        job.generated_tests[test_path] = test_code
                        job.cost += 0.30  # Opus for test

            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc).isoformat()
            self._save_jobs()
            logger.info("CodeGen job %s completed: %d files, %d tests, $%.2f",
                        job.job_id, len(job.generated_code), len(job.generated_tests), job.cost)

        except Exception as e:
            job.status = "failed"
            job.error = str(e)
            self._save_jobs()
            logger.error("CodeGen job %s failed: %s", job.job_id, e)

    async def _generate_file(self, task: str, filepath: str, existing_code: str,
                              codebase_examples: str, context: str) -> str | None:
        """Generate a single file via LLM."""
        file_type = "service" if "services/" in filepath else "router" if "routers/" in filepath else "module"

        prompt = f"""You are the NemoClaw Engineering Lead. Generate a production-ready Python {file_type}.

TASK: {task}
TARGET FILE: {filepath}

EXISTING CODEBASE PATTERNS:
{codebase_examples[:2000]}

{"EXISTING CODE TO MODIFY:" + chr(10) + existing_code[:2000] if existing_code else "This is a NEW file."}

{"ADDITIONAL CONTEXT:" + chr(10) + context if context else ""}

REQUIREMENTS:
- Follow existing code patterns exactly (imports, logging, class structure)
- Use type hints on ALL public methods and function signatures (e.g., def method(self, param: str) -> dict[str, Any]:)
- Add docstrings to all classes and public methods
- Wrap ALL external calls (HTTP, file I/O, subprocess) in try/except with specific error types
- Every method that can fail must return an error dict, never raise unhandled
- Log important operations with logger.info/warning/error
- Keep under 3000 lines
- Use relative imports: from app.services.X import Y
- Include from __future__ import annotations at the top

Return ONLY the Python code. No markdown, no explanation."""

        try:
            from langchain_anthropic import ChatAnthropic
            llm = ChatAnthropic(model="claude-opus-4-6", max_tokens=32000)
            resp = await asyncio.to_thread(llm.invoke, [("human", prompt)])
            code = resp.content.strip()
            # Strip markdown fences if present
            if code.startswith("```python"):
                code = code[9:]
            if code.startswith("```"):
                code = code[3:]
            if code.endswith("```"):
                code = code[:-3]
            code = code.strip()

            # Validate compilation
            compile(code, filepath, "exec")
            return code

        except SyntaxError as e:
            logger.warning("Generated code for %s has syntax error: %s", filepath, e)
            return None
        except Exception as e:
            logger.error("LLM call failed for %s: %s", filepath, e)
            return None

    async def _generate_test(self, filepath: str, implementation: str, task: str) -> str | None:
        """Generate acceptance tests for the implementation (Fix #1)."""
        prompt = f"""Generate acceptance tests for this Python module.

FILE: {filepath}
TASK: {task}

IMPLEMENTATION:
{implementation[:3000]}

REQUIREMENTS:
- Use pytest
- Test all public methods
- Include at least:
  1. Import test (module importable)
  2. Instantiation test (class creates without error)
  3. Core functionality test (main method returns expected structure)
  4. Edge case tests:
     a. Empty/None input handling
     b. Invalid input (wrong type, malformed data)
     c. Network error simulation (mock requests to raise ConnectionError)
     d. Timeout handling
  5. Return type validation (assert isinstance(result, dict))
- Use assertions that verify CORRECTNESS, not just "no error"
- Example: assert "status" in result, assert result["count"] >= 0
- Mock all external dependencies (HTTP calls, file I/O)

Return ONLY the Python test code. No markdown."""

        try:
            from langchain_anthropic import ChatAnthropic
            llm = ChatAnthropic(model="claude-opus-4-6", max_tokens=16000)
            resp = await asyncio.to_thread(llm.invoke, [("human", prompt)])
            code = resp.content.strip()
            if code.startswith("```python"):
                code = code[9:]
            if code.startswith("```"):
                code = code[3:]
            if code.endswith("```"):
                code = code[:-3]
            code = code.strip()

            compile(code, filepath + "_test", "exec")
            return code

        except Exception as e:
            logger.warning("Test generation failed for %s: %s", filepath, e)
            return None

    def get_job(self, job_id: str) -> GenerationJob | None:
        return self.jobs.get(job_id)

    def list_jobs(self) -> list[dict[str, Any]]:
        return [j.to_dict() for j in self.jobs.values()]
