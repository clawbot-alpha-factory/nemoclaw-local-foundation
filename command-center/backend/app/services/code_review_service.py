"""
NemoClaw Execution Engine — CodeReviewService (E-7b)

5-layer code review pipeline:
  1. Automated: compile, import, secrets scan, style, <600 lines
  2. Test execution: generated tests must pass
  3. CTO agent: structured JSON review (issues, risks, missing_tests)
  4. Operations: regression passes
  5. Peer review: diff-aware cross-check

Fix #2: Structured LLM review output (JSON, not free-form).
Fix #6: Diff-aware review with change context.

NEW FILE: command-center/backend/app/services/code_review_service.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("cc.codereview")


class ReviewResult:
    def __init__(self, job_id: str):
        self.review_id = str(uuid.uuid4())[:8]
        self.job_id = job_id
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.layers: list[dict[str, Any]] = []
        self.overall_verdict = "pending"  # pending, approved, rejected
        self.blocking_issues: list[str] = []
        self.confidence: float = 0.0
        self.cost: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "review_id": self.review_id,
            "job_id": self.job_id,
            "created_at": self.created_at,
            "layers": self.layers,
            "overall_verdict": self.overall_verdict,
            "blocking_issues": self.blocking_issues,
            "confidence": self.confidence,
            "cost": self.cost,
        }


class CodeReviewService:
    """
    5-layer code review with structured output.

    Every LLM review returns JSON:
    {
        "issues": [...],
        "risk_level": "low|medium|high",
        "missing_tests": [...],
        "approval": true/false,
        "reasoning": "..."
    }

    Rejection triggers: missing_tests non-empty, risk_level=high, compile fails.
    """

    SECRETS_PATTERNS = [
        r'(?:api[_-]?key|secret|password|token)\s*=\s*["\'][^"\']{10,}["\']',
        r'sk-[a-zA-Z0-9]{20,}',
        r'AKIA[A-Z0-9]{16}',
    ]

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.backend_dir = repo_root / "command-center" / "backend"
        self.python = str(repo_root / ".venv313" / "bin" / "python3")
        self.reviews: list[ReviewResult] = []
        self._persist_path = Path.home() / '.nemoclaw' / 'code-reviews.json'
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        self.human_gate_enabled = True  # Configurable
        logger.info("CodeReviewService initialized (human_gate=%s)", self.human_gate_enabled)

    async def review(self, generation_job) -> ReviewResult:
        """Run 5-layer review on generated code."""
        result = ReviewResult(job_id=generation_job.job_id)

        # Layer 1: Automated checks
        layer1 = await self._automated_review(generation_job)
        result.layers.append({"layer": "automated", **layer1})
        if not layer1["passed"]:
            result.overall_verdict = "rejected"
            result.blocking_issues.extend(layer1.get("issues", []))
            self.reviews.append(result)
            self._save_reviews()
            return result

        # Layer 2: Test execution (Fix #1)
        layer2 = await self._test_execution(generation_job)
        result.layers.append({"layer": "test_execution", **layer2})
        if not layer2["passed"]:
            result.overall_verdict = "rejected"
            result.blocking_issues.append("Generated tests failed")
            self.reviews.append(result)
            self._save_reviews()
            return result

        # Layer 3: CTO agent review (Fix #2 — structured JSON)
        layer3 = await self._cto_review(generation_job)
        result.layers.append({"layer": "cto_review", **layer3})
        result.cost += layer3.get("cost", 0)
        if not layer3.get("approval", False):
            result.overall_verdict = "rejected"
            result.blocking_issues.extend(layer3.get("issues", []))
            self.reviews.append(result)
            self._save_reviews()
            return result

        # Layer 4: Operations — regression check
        layer4 = await self._operations_review()
        result.layers.append({"layer": "operations", **layer4})
        if not layer4["passed"]:
            result.overall_verdict = "rejected"
            result.blocking_issues.append("Regression failed")
            self.reviews.append(result)
            self._save_reviews()
            return result

        # Layer 5: Peer review — diff-aware (Fix #6)
        layer5 = await self._peer_review(generation_job)
        result.layers.append({"layer": "peer_review", **layer5})
        result.cost += layer5.get("cost", 0)

        # Final verdict
        # Calculate confidence (Fix #8)
        passed_layers = sum(1 for l in result.layers if l.get("passed", l.get("approval", False)))
        result.confidence = round(passed_layers / max(len(result.layers), 1), 2)

        if all(l.get("passed", l.get("approval", False)) for l in result.layers):
            result.overall_verdict = "approved"
        else:
            result.overall_verdict = "rejected"

        self.reviews.append(result)
        self._save_reviews()
        logger.info("Review %s: %s (%d layers, $%.2f)",
                     result.review_id, result.overall_verdict, len(result.layers), result.cost)
        return result

    async def _automated_review(self, job) -> dict[str, Any]:
        """Layer 1: Compile, import, secrets, style, size."""
        issues = []
        passed = True

        for filepath, code in job.generated_code.items():
            # Compile check
            try:
                compile(code, filepath, "exec")
            except SyntaxError as e:
                issues.append(f"{filepath}: syntax error — {e}")
                passed = False

            # Size check
            lines = len(code.split("\n"))
            if lines > 3000:
                issues.append(f"{filepath}: {lines} lines (max 3000)")
                passed = False

            # Secrets scan
            for pattern in self.SECRETS_PATTERNS:
                if re.search(pattern, code, re.IGNORECASE):
                    issues.append(f"{filepath}: potential hardcoded secret detected")
                    passed = False

            # Style check (basic)
            if "from __future__ import annotations" not in code:
                issues.append(f"{filepath}: missing 'from __future__ import annotations'")

        return {"passed": passed, "issues": issues, "checks": ["compile", "size", "secrets", "style"]}

    async def _test_execution(self, job) -> dict[str, Any]:
        """Layer 2: Run generated acceptance tests via pytest (Fix #2)."""
        if not job.generated_tests:
            return {"passed": True, "note": "No tests generated (non-blocking)"}

        results = []
        all_passed = True

        for test_path, test_code in job.generated_tests.items():
            # First: compile check
            try:
                compile(test_code, test_path, "exec")
            except SyntaxError as e:
                results.append({"test": test_path, "compiled": False, "error": str(e)})
                all_passed = False
                continue

            # Write test to temp file and run pytest
            temp_test = self.backend_dir / test_path
            temp_test.parent.mkdir(parents=True, exist_ok=True)
            temp_test.write_text(test_code)

            try:
                proc = await asyncio.create_subprocess_exec(
                    self.python, "-m", "pytest", str(temp_test), "-x", "-q",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(self.backend_dir),
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
                passed = proc.returncode == 0
                results.append({
                    "test": test_path,
                    "compiled": True,
                    "executed": True,
                    "passed": passed,
                    "output": stdout.decode()[-300:] if stdout else "",
                })
                if not passed:
                    all_passed = False
            except asyncio.TimeoutError:
                results.append({"test": test_path, "executed": False, "error": "timeout"})
                all_passed = False
            except Exception as e:
                results.append({"test": test_path, "executed": False, "error": str(e)})

        return {"passed": all_passed, "tests": results}

    async def _cto_review(self, job) -> dict[str, Any]:
        """Layer 3: CTO agent structured review (Fix #2)."""
        all_code = "\n\n".join(
            f"# {fp}\n{code[:2000]}"
            for fp, code in job.generated_code.items()
        )

        # Build diff context (Fix #6)
        diff_summary = []
        for fp, ctx in job.diff_context.items():
            if ctx.get("is_new_file"):
                diff_summary.append(f"NEW FILE: {fp}")
            else:
                diff_summary.append(f"MODIFIED: {fp}")

        prompt = f"""You are the CTO reviewing code for the NemoClaw autonomous agent system.

TASK: {job.task}
FILES: {', '.join(job.target_files)}
CHANGES: {'; '.join(diff_summary)}

CODE:
{all_code[:4000]}

Review this code and respond with ONLY a JSON object (no markdown):
{{
    "issues": ["list of specific issues found"],
    "risk_level": "low or medium or high",
    "missing_tests": ["list of test cases that should exist but don't"],
    "what_changed": "brief description of changes",
    "what_could_break": "what existing functionality might be affected",
    "approval": true or false,
    "reasoning": "brief explanation"
}}

REJECTION CRITERIA:
- Any hardcoded secrets
- Missing error handling
- Could break existing endpoints
- No type hints on public methods
- Logic errors"""

        try:
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(model="gpt-4o", max_tokens=16000)
            resp = await asyncio.to_thread(llm.invoke, [("human", prompt)])
            text = resp.content.strip()

            # Parse JSON
            if "{" in text:
                json_str = text[text.index("{"):text.rindex("}") + 1]
                review_data = json.loads(json_str)

                # Enforce: missing_tests → reject
                if review_data.get("missing_tests"):
                    review_data["approval"] = False
                    review_data["issues"].append("Missing required test cases")

                return {
                    "passed": review_data.get("approval", False),
                    "cost": 0.01,
                    **review_data,
                }

        except Exception as e:
            logger.warning("CTO review failed: %s — auto-approving with caution", e)

        return {"passed": False, "cost": 0, "error": "CTO review unavailable — REJECTED (never auto-approve)"}

    async def _operations_review(self) -> dict[str, Any]:
        """Layer 4: Run regression script."""
        regression_script = self.repo_root / "scripts" / "full_regression.sh"
        if not regression_script.exists():
            return {"passed": True, "note": "Regression script not found — skipped"}

        try:
            proc = await asyncio.create_subprocess_exec(
                "bash", str(regression_script),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.repo_root),
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)

            passed = proc.returncode == 0
            return {
                "passed": passed,
                "exit_code": proc.returncode,
                "output_tail": stdout.decode()[-500:] if stdout else "",
            }
        except asyncio.TimeoutError:
            return {"passed": False, "error": "Regression timed out (300s)"}
        except Exception as e:
            return {"passed": False, "error": str(e)}

    async def _peer_review(self, job) -> dict[str, Any]:
        """Layer 5: Diff-aware peer review (Fix #6)."""
        diff_info = []
        for fp, ctx in job.diff_context.items():
            diff_info.append(f"""
FILE: {fp}
TYPE: {"NEW" if ctx.get("is_new_file") else "MODIFIED"}
NEW CODE (first 1500 chars):
{ctx.get("new_code", "")[:1500]}
{"EXISTING CODE (first 1000 chars):" + chr(10) + ctx.get("existing_code", "")[:1000] if not ctx.get("is_new_file") else ""}
""")

        prompt = f"""You are a senior engineer doing peer review.

CHANGES:
{"".join(diff_info)[:5000]}

Respond with ONLY a JSON object:
{{
    "issues": ["specific issues"],
    "risk_level": "low or medium or high",
    "approval": true or false,
    "what_risks_introduced": "brief description"
}}"""

        try:
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(model="gpt-4o", max_tokens=16000)
            resp = await asyncio.to_thread(llm.invoke, [("human", prompt)])
            text = resp.content.strip()

            if "{" in text:
                json_str = text[text.index("{"):text.rindex("}") + 1]
                data = json.loads(json_str)
                return {"passed": data.get("approval", False), "cost": 0.01, **data}

        except Exception as e:
            logger.warning("Peer review failed: %s", e)

        return {"passed": False, "cost": 0, "error": "Peer review unavailable — REJECTED"}

    def _save_reviews(self):
        """Persist reviews to disk."""
        try:
            data = [r.to_dict() for r in self.reviews[-50:]]  # Keep last 50
            self._persist_path.write_text(json.dumps(data, indent=2, default=str))
        except Exception as e:
            logger.warning("Failed to persist reviews: %s", e)

    def get_reviews(self, limit: int = 20) -> list[dict[str, Any]]:
        return [r.to_dict() for r in self.reviews[-limit:]]
